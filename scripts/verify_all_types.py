"""Bounded live comparison on six generated documents with known printed truth.

This is a synthetic integration diagnostic, never a real-data paper benchmark.
Run: python scripts/verify_all_types.py --live
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "research")]
from config import settings
from services.extractor.field_mapper import FIELD_META
from services.field_contract import keys_for
from services.storage import write_json
from utils.image_utils import normalize_image

VALUES = {
    "GST_INVOICE": {"invoice_no":"TEST-GST-001", "invoice_date":"16/10/2026", "vendor_name":"Example Office Supplies", "vendor_gstin":"27AAPFU0939F1ZV", "buyer_name":"Demo Customer", "buyer_gstin":None, "taxable_amount":"1000.00", "cgst_amount":"90.00", "sgst_amount":"90.00", "igst_amount":"0.00", "total_amount":"1180.00", "due_date":"30/10/2026", "po_number":"PO-001"},
    "PURCHASE_BILL": {"bill_no":"TEST-PB-001", "bill_date":"16/10/2026", "vendor_name":"Example Office Supplies", "vendor_gstin":"27AAPFU0939F1ZV", "subtotal":"1000.00", "tax_amount":"180.00", "total_amount":"1180.00", "payment_terms":"Due in 14 days"},
    "EXPENSE_RECEIPT": {"vendor_name":"Example Cafe", "receipt_date":"16/10/2026", "receipt_no":"TEST-ER-001", "amount":"210.00", "tax_amount":"10.00", "payment_mode":"Cash", "category":"Meals"},
    "UTILITY_BILL": {"consumer_no":"UTIL-1001", "bill_date":"16/10/2026", "due_date":"30/10/2026", "billing_period":"October 2026", "units_consumed":"100", "amount_due":"500.00", "utility_provider":"Example Electricity Services", "account_name":"Demo Customer"},
    "CREDIT_NOTE": {"credit_note_no":"TEST-CN-001", "credit_note_date":"16/10/2026", "original_invoice_no":"TEST-GST-001", "vendor_name":"Example Office Supplies", "vendor_gstin":"27AAPFU0939F1ZV", "buyer_name":"Demo Customer", "reason":"Returned goods", "credit_amount":"118.00", "tax_credit":"18.00"},
    "DEBIT_NOTE": {"debit_note_no":"TEST-DN-001", "debit_note_date":"16/10/2026", "original_invoice_no":"TEST-GST-001", "vendor_name":"Example Office Supplies", "vendor_gstin":"27AAPFU0939F1ZV", "reason":"Additional goods", "debit_amount":"118.00", "tax_amount":"18.00"},
}


def fixtures(out):
    from PIL import Image, ImageDraw, ImageFont
    documents = []
    for doc_type, values in VALUES.items():
        # Use the canonical schema even when a type has fewer fields than another.
        values = {k: values.get(k) for k in keys_for(doc_type)}
        image = Image.new("RGB", (1400, 1800), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
        lines = [doc_type.replace("_", " ")] + [FIELD_META[k]["label"] + ": " + v for k, v in values.items() if v is not None]
        words = []
        for n, line in enumerate(lines):
            x, y = 60, 60 + n * 95
            for token in line.split():
                bounds = draw.textbbox((x, y), token, font=font)
                draw.text((x, y), token, font=font, fill="black")
                x0, y0, x1, y1 = map(int, bounds)
                words.append({"text":token,"confidence":1.0,"bounding_box":[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]})
                x += draw.textlength(token + " ", font=font)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        identity = doc_type.lower()
        source = out / "images" / (identity + ".png")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(stream.getvalue())
        normalized = normalize_image(source.read_bytes())
        exact = out / "ocr" / (identity + ".corrected.json")
        write_json(exact, {"full_text":"\n".join(lines),"words":words,"page_count":1,
                          "verified":True,"provenance":"generator_exact_not_human",
                          "image_sha256":hashlib.sha256(normalized).hexdigest()})
        documents.append({"id":identity,"image":source.relative_to(out).as_posix(),
            "sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"doc_type":doc_type,
            "split":"development","group":"generated-diagnostic", "fields":values,
            "ocr_corrected":exact.relative_to(out).as_posix(), "annotation_source":"generator_programmatic_truth"})
    write_json(out / "manifest.json", {"documents":documents,"cohort":"generated_integration_fixtures_not_real_benchmark"})
    write_json(out / "policy.json", {"version":"policy-v1","selected_on":"development","status":"uncalibrated-development-diagnostic",
        "review_threshold":settings.REVIEW_THRESHOLD,"fallback_threshold":settings.FALLBACK_THRESHOLD})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow at most six Google calls and 24 hosted attempts")
    args = parser.parse_args()
    out = ROOT / "backend/data/verification" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-all-types")
    out.mkdir(parents=True, exist_ok=True)
    fixtures(out)
    # Keep hosted cache across both variants. P2 is identical image-only input.
    env = {**os.environ,"DATA_DIR":str(out / "isolated_data"),"HOSTED_VLM_CACHE":"true",
           "HOSTED_VLM_MAX_ATTEMPTS":"2","HOSTED_VLM_MIN_INTERVAL_SECONDS":"20",
           "HOSTED_VLM_MAX_RETRY_WAIT_SECONDS":"30","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4"}
    report = {"cohort":"six_generated_documents", "limitations":["Not a real-data benchmark", "Thresholds are uncalibrated", "Exact OCR is generated, not human transcription"],"checks":{}}
    write_json(out / "report.json", report)

    def command(name, arguments):
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            done = subprocess.run([sys.executable, *arguments],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        report["checks"][name] = {"passed":done.returncode==0,"exit_code":done.returncode}
        write_json(out / "report.json", report)
        print(name + (": passed" if done.returncode==0 else ": failed"), flush=True)
        if done.returncode:
            raise RuntimeError("Check failed; inspect local log: " + name)

    manifest, policy = str(out / "manifest.json"), str(out / "policy.json")
    command("manifest", ["research/run.py","validate","--manifest",manifest])
    if args.live:
        command("google_inputs", ["research/ocr_inputs.py","--manifest",manifest,"--live","--max-calls","6"])
        from fastapi.testclient import TestClient
        from main import app
        classification = []
        for document in json.loads((out / "manifest.json").read_text())["documents"]:
            text = json.loads((out / document["ocr_google"]).read_text())["full_text"]
            with TestClient(app) as client:
                response = client.post("/api/classify",json={"file_id":document["id"],"ocr_text":text})
            classification.append({"id":document["id"],"expected":document["doc_type"],
                                   "status_code":response.status_code,"result":response.json()})
        write_json(out / "classification.json", classification)
        report["checks"]["classification"] = {"passed":all(r["status_code"]==200 and r["result"].get("type")==r["expected"] for r in classification)}
        write_json(out / "report.json", report)
    for variant in ("google", "corrected"):
        arguments = ["research/run.py","run","--manifest",manifest,"--policy",policy,"--split","development","--out",str(out / (variant + ".json")),"--ocr-variant",variant,"--release-models"]
        if args.live:
            arguments += ["--live","--max-calls","12"]
        command(variant + "_run", arguments)
        command(variant + "_score", ["research/run.py","score","--manifest",manifest,"--policy",policy,"--split","development","--predictions",str(out / (variant + ".json")),"--out",str(out / (variant + "-scores.json"))])
    command("paired_ocr", ["research/compare_ocr.py","--manifest",manifest,"--google",str(out / "google.json"),"--corrected",str(out / "corrected.json"),"--out",str(out / "paired-ocr.json")])
    failures = []
    for variant in ("google", "corrected"):
        payload = json.loads((out / (variant + ".json")).read_text())
        for row in payload["predictions"]:
            for pipeline, run in row["pipelines"].items():
                if run.get("error") or run.get("metadata", {}).get("degraded"):
                    failures.append({"variant":variant,"id":row["id"],"pipeline":pipeline,"error":run.get("error"),"reasons":run.get("metadata", {}).get("operational_reasons")})
    report.update(operational_failures=failures,completed_at=datetime.now(timezone.utc).isoformat())
    write_json(out / "report.json", report)
    print("Report: " + str(out / "report.json"), flush=True)
    return int(bool(failures) or any(not c["passed"] for c in report["checks"].values()))


if __name__ == "__main__":
    sys.exit(main())
