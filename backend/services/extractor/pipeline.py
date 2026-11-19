"""Extraction engines and cascades; review policies are independent, read-only evaluations."""
import re
import time
from services.errors import HostedError, ServiceUnavailable
from services.field_contract import keys_for, canonical_fields, REQUIRED, AMOUNT_KEYS, DATE_KEYS
from services.extractor.hosted_vlm import extract_hosted
from services.extractor.hosted_llm import extract_hosted_llm
from services.validator.rules_engine import review_document
from config import settings

PIPELINES = ["ocr_layoutlm", "hosted_vlm", "layoutlm_hosted_fallback", "layoutlm_llm_vlm"]
DEFAULT_PIPELINE = "ocr_layoutlm"
TRUNCATION_REASON = "OCR exceeds LayoutLM token window; verify unseen content."

_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]")
_DATE = re.compile(r"\b(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[\s-][A-Za-z]{3,9}[\s,-]+\d{2,4})\b")
_AMOUNT = re.compile(r"\d[\d,]*\.\d{2}(?!\d)|\d{1,3}(?:,\d{2,3})+(?![\d.])")
_IDENTIFIER = re.compile(r"\b(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9][A-Za-z0-9/-]{2,}\b")

def ocr_has_evidence(key, text):
    """Is a value of this field's kind printed anywhere OCR read? Names and free text have no reliable pattern.

    Errors are safe both ways: a false "present" costs one LLM call before the post-LLM check
    escalates to the VLM; a false "absent" sends the field straight to the VLM, which can still read it.
    """
    if key.endswith("gstin"):
        return bool(_GSTIN.search(re.sub(r"\s+", "", text.upper())))
    if key in DATE_KEYS or key.endswith("_date"):
        return bool(_DATE.search(text))
    if key in AMOUNT_KEYS:
        return bool(_AMOUNT.search(text))
    if key.endswith("_no") or key == "po_number":
        return bool(_IDENTIFIER.search(text))
    return bool(text.strip())

def routing_reasons(doc_type, fields, threshold=None):
    limit = settings.FALLBACK_THRESHOLD if threshold is None else threshold
    reasons = []
    for field in fields:
        if field["key"] in REQUIRED[doc_type] and not field.get("value"):
            reasons.append("Missing core field: " + field["key"])
        elif field.get("value") and field.get("confidence") is not None and field["confidence"] < limit:
            reasons.append("Low model confidence: " + field["key"])
    validation = review_document(doc_type, fields)
    reasons.extend(rule["name"] + ": " + rule["message"] for rule in validation["rules"] if rule["passed"] is False)
    return list(dict.fromkeys(reasons))

def route_fallback(doc_type, fields, ocr_text, threshold=None, truncated=False):
    """Split routing_reasons by remedy: text OCR read but LayoutLM mis-tagged -> LLM; text OCR never read -> VLM."""
    limit = settings.FALLBACK_THRESHOLD if threshold is None else threshold
    plan, missing = {"llm": [], "vlm": []}, {}
    for field in fields:
        if field["key"] in REQUIRED[doc_type] and not field.get("value"):
            missing[field["key"]] = "llm" if ocr_has_evidence(field["key"], ocr_text) else "vlm"
            plan[missing[field["key"]]].append("Missing core field: " + field["key"])
        elif field.get("value") and field.get("confidence") is not None and field["confidence"] < limit:
            plan["llm"].append("Low model confidence: " + field["key"])
    for rule in review_document(doc_type, fields)["rules"]:
        if rule["passed"] is False:
            # A rule failing only because a field is absent ("Required: x") shares that field's remedy.
            plan["vlm" if any(missing.get(key) == "vlm" for key in rule["fields"]) else "llm"].append(rule["name"] + ": " + rule["message"])
    if truncated:
        # The LLM tier sees every OCR token, so content past LayoutLM's window is a tagging problem.
        plan["llm"].append(TRUNCATION_REASON)
    return {tier: list(dict.fromkeys(reasons)) for tier, reasons in plan.items()}

def resolve_candidates(doc_type, local, hosted, threshold=None, conflict_policy=None):
    policy = settings.HYBRID_CONFLICT_POLICY if conflict_policy is None else conflict_policy
    if policy not in ("keep_local", "prefer_hosted"):
        raise ValueError("Unknown hybrid conflict policy")
    limit = settings.FALLBACK_THRESHOLD if threshold is None else threshold
    remote = {f["key"]: f for f in hosted}
    merged, decisions, conflicts = [], [], []
    for field in local:
        other = remote.get(field["key"])
        chosen = field
        action = "keep_local"
        if other and other.get("value"):
            if not field.get("value") or (field.get("confidence") is not None and field["confidence"] < limit):
                chosen, action = other, "hosted_gap_or_uncertainty"
            elif str(field["value"]).strip().casefold() != str(other["value"]).strip().casefold():
                conflicts.append(field["key"])
                if policy == "prefer_hosted":
                    chosen, action = other, "conflict_prefer_hosted_review"
                else:
                    action = "conflict_keep_local_review"
        merged.append(chosen)
        decisions.append({"key": field["key"], "action": action})
    return canonical_fields(doc_type, merged), decisions, conflicts

def _merge_tier(meta, tier, doc_type, fields, other, threshold, policy):
    merged, decisions, conflicts = resolve_candidates(doc_type, fields, other, threshold, policy)
    meta["decisions"].extend({**decision, "tier": tier} for decision in decisions)
    meta["conflicts"] = list(dict.fromkeys(meta["conflicts"] + conflicts))
    meta["cascade"]["tiers"].append(tier)
    return merged

def _cascade(meta, doc_type, fields, words, ocr_text, image_bytes, width, height, truncated, threshold, policy, allow_network):
    """Tier 2 fixes tagging (LLM over OCR tokens); tier 3 recovers unread text (VLM over pixels)."""
    plan = route_fallback(doc_type, fields, ocr_text, threshold, truncated)
    meta["routing_reasons"] = plan["llm"] + plan["vlm"]
    meta["cascade"] = {"plan": plan, "tiers": [], "escalated": []}
    escalate = list(plan["vlm"])
    if plan["llm"]:
        try:
            llm = extract_hosted_llm([w["text"] for w in words], [w["bounding_box"] for w in words],
                                     doc_type, width, height, allow_network=allow_network)
            meta["hosted_llm"], meta["llm_fields"] = llm["metadata"], llm["fields"]
            fields = _merge_tier(meta, "llm", doc_type, fields, llm["fields"], threshold, policy)
            # The LLM saw every OCR token; a core field it still cannot find was most likely never read.
            escalate += ["Missing core field after LLM: " + key for key in REQUIRED[doc_type]
                         if not next((f.get("value") for f in fields if f["key"] == key), None)
                         and "Missing core field: " + key not in plan["vlm"]]
        except HostedError as exc:
            meta["operational_reasons"].append(str(exc))
            meta["hosted_llm"] = {"attempts": exc.attempts, "logical_calls": 1, "error": exc.kind, "usage": {}}
            escalate += plan["llm"]
    meta["cascade"]["escalated"] = escalate = list(dict.fromkeys(escalate))
    if escalate:
        try:
            vlm = extract_hosted(image_bytes, doc_type, allow_network=allow_network)
            meta["hosted"], meta["hosted_fields"] = vlm["metadata"], vlm["fields"]
            fields = _merge_tier(meta, "vlm", doc_type, fields, vlm["fields"], threshold, policy)
        except HostedError as exc:
            meta["operational_reasons"].append(str(exc))
            meta["hosted"] = {"attempts": exc.attempts, "logical_calls": 1, "error": exc.kind, "usage": {}}
    return fields

def run_pipeline(*, pipeline, image_bytes, ocr_result, doc_type, image_width, image_height,
                 review_policy="validation_review", allow_network=True, fallback_threshold=None, review_threshold=None,
                 conflict_policy=None):
    if pipeline not in PIPELINES:
        raise ValueError("Unsupported pipeline; use " + ", ".join(PIPELINES))
    keys_for(doc_type)
    started = time.perf_counter()
    policy = settings.HYBRID_CONFLICT_POLICY if conflict_policy is None else conflict_policy
    if policy not in ("keep_local", "prefer_hosted"):
        raise ValueError("Unknown hybrid conflict policy")
    meta = {"pipeline_version": "pipelines-v3", "schema_version": "fields-v1", "conflict_policy": policy,
            "fallback_threshold": settings.FALLBACK_THRESHOLD if fallback_threshold is None else fallback_threshold,
            "threshold_status": "development setting; not calibrated", "routing_reasons": [],
            "conflicts": [], "operational_reasons": [], "hosted": {"attempts": 0, "logical_calls": 0},
            "hosted_llm": {"attempts": 0, "logical_calls": 0},
            "local_fields": [], "hosted_fields": [], "llm_fields": [], "decisions": []}
    ocr_result = ocr_result or {"words": [], "full_text": ""}
    if pipeline == "hosted_vlm":
        hosted = extract_hosted(image_bytes, doc_type, allow_network=allow_network)
        fields = hosted["fields"]
        meta["hosted"], meta["hosted_fields"] = hosted["metadata"], fields
        line_items = []
    else:
        words = ocr_result.get("words", [])
        if not words or not ocr_result.get("full_text", "").strip():
            raise ValueError("Run OCR first; LayoutLM requires nonempty text and word boxes.")
        from services.extractor.layoutlm_extractor import extract_fields
        diagnostics = {}
        raw = extract_fields(image_bytes=image_bytes, words=[w["text"] for w in words],
            bboxes_raw=[w["bounding_box"] for w in words], image_width=image_width,
            image_height=image_height, doc_type=doc_type, ocr_text=ocr_result["full_text"],
            strict=True, diagnostics=diagnostics)
        fields = canonical_fields(doc_type, raw)
        meta["local_fields"], meta["layoutlm"] = fields, diagnostics
        if diagnostics.get("truncated"):
            meta["operational_reasons"].append(TRUNCATION_REASON)
        from services.extractor.table_parser import parse_line_items
        line_items = parse_line_items(words)
        if pipeline == "layoutlm_hosted_fallback":
            meta["routing_reasons"] = routing_reasons(doc_type, fields, fallback_threshold)
            if meta["operational_reasons"]:
                meta["routing_reasons"].extend(meta["operational_reasons"])
            if meta["routing_reasons"]:
                try:
                    hosted = extract_hosted(image_bytes, doc_type, allow_network=allow_network)
                    meta["hosted"], meta["hosted_fields"] = hosted["metadata"], hosted["fields"]
                    fields, meta["decisions"], meta["conflicts"] = resolve_candidates(doc_type, fields, hosted["fields"], fallback_threshold, policy)
                except HostedError as exc:
                    meta["operational_reasons"].append(str(exc))
                    meta["hosted"] = {"attempts": exc.attempts, "logical_calls": 1, "error": exc.kind, "usage": {}}
        elif pipeline == "layoutlm_llm_vlm":
            fields = _cascade(meta, doc_type, fields, words, ocr_result["full_text"], image_bytes, image_width,
                              image_height, bool(diagnostics.get("truncated")), fallback_threshold, policy, allow_network)
    validation = review_document(doc_type, fields, review_policy, meta["operational_reasons"], meta["conflicts"], review_threshold)
    meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    meta["degraded"] = bool(meta["operational_reasons"])
    return {"fields": fields, "line_items": line_items, "pipeline": pipeline, "metadata": meta, "validation": validation}
