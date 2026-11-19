"""Three extraction engines; review policies are independent, read-only evaluations."""
import time
from services.errors import HostedError, ServiceUnavailable
from services.field_contract import keys_for, canonical_fields, REQUIRED
from services.extractor.hosted_vlm import extract_hosted
from services.validator.rules_engine import review_document
from config import settings

PIPELINES = ["ocr_layoutlm", "hosted_vlm", "layoutlm_hosted_fallback"]
DEFAULT_PIPELINE = "ocr_layoutlm"

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
    meta = {"pipeline_version": "pipelines-v2", "schema_version": "fields-v1", "conflict_policy": policy,
            "fallback_threshold": settings.FALLBACK_THRESHOLD if fallback_threshold is None else fallback_threshold,
            "threshold_status": "development setting; not calibrated", "routing_reasons": [],
            "conflicts": [], "operational_reasons": [], "hosted": {"attempts": 0, "logical_calls": 0},
            "local_fields": [], "hosted_fields": [], "decisions": []}
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
            meta["operational_reasons"].append("OCR exceeds LayoutLM token window; verify unseen content.")
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
    validation = review_document(doc_type, fields, review_policy, meta["operational_reasons"], meta["conflicts"], review_threshold)
    meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    meta["degraded"] = bool(meta["operational_reasons"])
    return {"fields": fields, "line_items": line_items, "pipeline": pipeline, "metadata": meta, "validation": validation}
