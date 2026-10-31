"""Opt-in live smoke audit; uses configured keys and an isolated SQLite database.

Run from the repository root: python scripts/verify_system.py
Makes one OCR request and at most four hosted attempts across P2/P3.
Does not train, download, or modify LayoutLM checkpoints.
"""
import io
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import settings

OUT = ROOT / "backend/data/verification" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT.mkdir(parents=True, exist_ok=True)
REPORT = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": {},
          "limitations": ["Synthetic smoke fixture; not research accuracy evidence.",
                          "PostgreSQL and interactive browser behavior not tested.",
                          "Local inference smoke test covers GST_INVOICE only."]}


def redact(value):
    value = str(value)
    for secret in (settings.GROQ_API_KEY, settings.GOOGLE_CLOUD_VISION_API_KEY, settings.DATABASE_URL):
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def record(name, status, **details):
    REPORT["checks"][name] = dict(status=status, **details)
    (OUT / "report.json").write_text(redact(json.dumps(REPORT, indent=2)), encoding="utf-8")
    print(name + ": " + status, flush=True)


def command(name, argv, cwd):
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=300)
        (OUT / (name + ".log")).write_text(redact(result.stdout + result.stderr), encoding="utf-8")
        record(name, "passed" if result.returncode == 0 else "failed", exit_code=result.returncode)
    except Exception as exc:
        record(name, "failed", error=redact(exc))


def main():
    command("backend_tests", [sys.executable, "-m", "pytest", "backend/tests", "-q", "-p", "no:cacheprovider",
                              "--basetemp", str(OUT / "pytest_temp")], ROOT)
    command("frontend_lint", ["cmd.exe", "/d", "/c", "npm.cmd", "run", "lint"], ROOT / "Frontend")
    command("frontend_build", ["cmd.exe", "/d", "/c", "npm.cmd", "run", "build"], ROOT / "Frontend")

    from PIL import Image, ImageDraw, ImageFont
    from fastapi.testclient import TestClient
    from main import app
    settings.DATA_DIR = str(OUT / "isolated_data")
    settings.DATABASE_URL = "sqlite:///" + (OUT / "verification.db").as_posix()
    settings.HOSTED_VLM_CACHE = False
    settings.HOSTED_VLM_MAX_ATTEMPTS = 2
    settings.HOSTED_VLM_TIMEOUT_SECONDS = 45
    image = Image.new("RGB", (1200, 1500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
    lines = ["TAX INVOICE", "Example Office Supplies", "GSTIN: 27AAPFU0939F1ZV",
             "Invoice No: TEST-001", "Invoice Date: 16/10/2026", "Bill To: Demo Customer",
             "Description: Office paper", "Quantity: 10", "Unit price: 100.00",
             "Taxable Amount: INR 1000.00", "CGST 9%: INR 90.00", "SGST 9%: INR 90.00",
             "IGST: INR 0.00", "Total Amount: INR 1180.00"]
    for index, line in enumerate(lines):
        draw.text((60, 60 + index * 85), line, fill="black", font=font)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    with TestClient(app) as client:
        record("health", "passed" if client.get("/api/health").status_code == 200 else "failed")
        uploaded = client.post("/api/upload", files={"file": ("synthetic-invoice.png", stream.getvalue(), "image/png")})
        uploaded.raise_for_status()
        file_id = uploaded.json()[0]["file_id"]
        record("upload_and_source", "passed" if client.get("/api/files/" + file_id).status_code == 200 else "failed")
        ocr = None
        try:
            response = client.post("/api/ocr", json={"file_id": file_id})
            response.raise_for_status()
            ocr = response.json()
            assert ocr["words"] and "TEST" in ocr["full_text"]
            record("live_google_ocr", "passed", word_count=len(ocr["words"]))
            classified = client.post("/api/classify", json={"file_id": file_id, "ocr_text": ocr["full_text"]})
            classified.raise_for_status()
            record("classification", "passed" if classified.json()["type"] == "GST_INVOICE" else "failed",
                   predicted_type=classified.json()["type"])
        except Exception as exc:
            record("live_google_ocr", "failed", error=redact(exc))

        for pipeline in ("hosted_vlm", "ocr_layoutlm", "layoutlm_hosted_fallback"):
            if pipeline != "hosted_vlm" and ocr is None:
                record(pipeline, "blocked", reason="Live OCR failed")
                continue
            started = time.monotonic()
            try:
                response = client.post("/api/extract", json={"file_id": file_id, "doc_type": "GST_INVOICE",
                    "pipeline": pipeline, "ocr_result": ocr if pipeline != "hosted_vlm" else None})
                if response.status_code != 200:
                    raise RuntimeError(str(response.status_code) + " " + response.text[:1500])
                run = response.json()
                assert run["pipeline"] == pipeline and run["fields"] and run["run_id"]
                checked = client.post("/api/validate", json={"doc_type": "GST_INVOICE", "fields": run["fields"]})
                checked.raise_for_status()
                saved = client.post("/api/documents", json={"run_id": run["run_id"], "fields": run["fields"],
                    "confirmed": True, "override_reason": "Synthetic automated smoke test, not a real accounting record."})
                saved.raise_for_status()
                assert client.get("/api/documents/" + saved.json()["id"]).status_code == 200
                record(pipeline, "passed", elapsed_seconds=round(time.monotonic()-started, 2),
                       populated_fields=sum(bool(f.get("value")) for f in run["fields"]),
                       hosted_attempts=run["metadata"]["hosted"].get("attempts", 0),
                       degraded=run["metadata"].get("degraded"),
                       operational_reasons=run["metadata"].get("operational_reasons", []),
                       review_required=run["validation"].get("review_required"))
            except Exception as exc:
                record(pipeline, "failed", error=redact(exc))
        for name, url in (("record_list", "/api/documents"), ("summary", "/api/documents/summary"),
                          ("csv_export", "/api/documents/export/csv")):
            response = client.get(url)
            record(name, "passed" if response.status_code == 200 else "failed")
        from services.storage import database
        database.cache_clear()
        response = client.get("/api/documents")
        expected = sum(REPORT["checks"].get(p, {}).get("status") == "passed" for p in
                       ("hosted_vlm", "ocr_layoutlm", "layoutlm_hosted_fallback"))
        record("sqlite_reopen_persistence", "passed" if response.status_code == 200 and response.json()["total"] == expected else "failed", expected_records=expected)
    REPORT["finished_at"] = datetime.now(timezone.utc).isoformat()
    record("audit_complete", "passed")
    print("Report: " + str(OUT / "report.json"), flush=True)
    return int(any(c["status"] != "passed" or c.get("degraded") for c in REPORT["checks"].values()))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        record("audit_unexpected_error", "failed", error=redact(exc))
        sys.exit(1)
