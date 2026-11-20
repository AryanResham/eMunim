"""Preload demo records into the local database through the app's real save path.

Documents come from a generator folder (images + answer keys). Each record is saved with the
answer-key values, as if a reviewer had checked it. With --predictions (pipeline outputs for the
same documents, as written by a pipeline check run), those outputs become the extracted values,
so the dashboard's correction statistics show real model mistakes; pipelines rotate across
documents for comparison. Without it, extracted and saved values are identical.

All demo data is synthetic. Re-running skips documents already seeded.

  python scripts/seed_demo.py --data indian_erp_doc_generator/indian_erp_doc_generator/msme_check_120
"""
import argparse
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "layoutLM__model")]
from train_msme import field_map
from services.business_profile import BusinessProfile, load_profile, save_profile
from services.field_contract import canonical_fields, keys_for
from services.storage import data_dir, list_records, save_run
from services.validator.rules_engine import review_document
from utils.image_utils import normalize_image
from routers.documents import SaveRequest, save_document

TYPES = ["GST_INVOICE", "PURCHASE_BILL", "EXPENSE_RECEIPT", "UTILITY_BILL", "CREDIT_NOTE", "DEBIT_NOTE"]
DEFAULT_ARMS = ["ocr_layoutlm", "layoutlm_llm_vlm", "hosted_vlm"]
REASON = "Preloaded demo data (synthetic)"
GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]")
CAPTION = re.compile(r"^(?:reason|billing\s+period)\s*:\s*", re.I)


def clean(key, text):
    """Some templates print the caption inside the value line; keep only the value."""
    if key.endswith("gstin"):
        match = GSTIN.search(re.sub(r"\s+", "", text.upper()))
        return match.group(0) if match else text
    return CAPTION.sub("", text)


def answer_key(annotation, doc_type):
    """Printed value per field from the generator's labelled lines (rule of synthetic_visible_audit)."""
    mapping, keys = field_map(doc_type), keys_for(doc_type)
    values = {}
    for line in annotation["ocr"]["lines"]:
        key = (mapping.get(line["field"]) or "").lower()
        if line["role"] == "value" and key in keys:
            values.setdefault(key, clean(key, line["text"]))
        if line["field"] == "supplier.registration" and "vendor_gstin" in keys:
            gstin = annotation["document"]["supplier"].get("gstin")
            if gstin and gstin in line["text"]:
                values.setdefault("vendor_gstin", gstin)
        if doc_type == "UTILITY_BILL" and line["field"] == "extra.meter_readings":
            match = re.search(r"\bUsed:\s*([\d,.]+)", line["text"])
            if match:
                values.setdefault("units_consumed", match.group(1))
    return values


def prediction(predictions, sample_id, arms, turn):
    """The turn-th usable arm's fields for this document, rotating so pipelines are compared."""
    path = predictions / "docs" / (sample_id + ".json") if predictions else None
    if not path or not path.exists():
        return None, None
    runs = json.loads(path.read_text(encoding="utf-8")).get("arms", {})
    usable = [a for a in arms if runs.get(a, {}).get("status") == "ok"]
    if not usable:
        return None, None
    arm = usable[turn % len(usable)]
    sources = runs[arm].get("sources", {})
    return arm, [{"key": k, "value": v, "confidence": None, "source": sources.get(k, "missing")}
                 for k, v in runs[arm]["fields"].items() if v]


def seed(data, per_type, predictions=None, arms=DEFAULT_ARMS):
    if load_profile() is None:
        save_profile(BusinessProfile(legal_name="Demo MSME Pvt Ltd", trade_name="Demo MSME", address="Demo data"))
        print("Created a demo business profile.")
    seeded = {r.get("metadata", {}).get("demo_sample_id") for r in list_records()}
    rows = [json.loads(line) for line in (data / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    added = 0
    for doc_type in TYPES:
        for index, row in enumerate([r for r in rows if r["document_type"].upper() == doc_type][:per_type]):
            if row["sample_id"] in seeded:
                continue
            truth = answer_key(json.loads((data / row["annotation"]).read_text(encoding="utf-8")), doc_type)
            arm, extracted = prediction(predictions, row["sample_id"], arms, index)
            if extracted is None:
                extracted = [{"key": k, "value": v, "confidence": None, "source": "demo_seed"} for k, v in truth.items()]
            original = canonical_fields(doc_type, extracted)
            # Alternate GST invoices between issued (money in) and received (money out).
            role = "vendor" if doc_type == "GST_INVOICE" and index % 2 == 0 else "buyer"
            file_id = str(uuid.uuid4())
            target = data_dir() / "raw_invoices" / (file_id + ".jpg")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(normalize_image((data / row["image"]).read_bytes()))
            run = save_run({"file_id": file_id, "doc_type": doc_type, "pipeline": arm or "demo_seed",
                            "fields": original, "line_items": [], "review_policy": "validation_review",
                            "validation": review_document(doc_type, original),
                            "metadata": {"business_identity": {"business_role": role, "matched": True, "reasons": []},
                                         "conflicts": [], "operational_reasons": [], "demo_sample_id": row["sample_id"]}})
            final = canonical_fields(doc_type, [{"key": k, "value": v} for k, v in truth.items()])
            save_document(SaveRequest(run_id=run["run_id"], fields=final, confirmed=True, override_reason=REASON))
            added += 1
    print(f"Seeded {added} demo records ({len(seeded - {None})} were already present).")
    return added


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True, help="generator output folder containing manifest.jsonl")
    parser.add_argument("--per-type", type=int, default=20)
    parser.add_argument("--predictions", type=Path, help="pipeline check output folder with docs/<sample_id>.json")
    parser.add_argument("--arms", nargs="+", default=DEFAULT_ARMS)
    args = parser.parse_args()
    seed(args.data, args.per_type, args.predictions, args.arms)
