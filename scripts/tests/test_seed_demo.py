"""Demo seeding goes through the real save path; prediction mistakes become recorded corrections."""
import io
import json
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seed_demo
from config import settings
from routers.documents import document_amount
from services.dashboard import build
from services.storage import list_records

LINES = {"supplier.name": "Power Co", "buyer.name": "Demo MSME", "date": "02/03/2025",
         "extra.consumer_number": "5783072623", "totals.grand_total": "200.00", "extra.due_date": "25/03/2025"}


def generator_folder(root):
    (root / "images").mkdir(parents=True)
    (root / "annotations").mkdir()
    image = io.BytesIO()
    Image.new("RGB", (40, 50), "white").save(image, format="JPEG")
    (root / "images" / "u1.jpg").write_bytes(image.getvalue())
    annotation = {"document": {"supplier": {"gstin": None}},
                  "ocr": {"lines": [{"field": f, "role": "value", "text": t} for f, t in LINES.items()]}}
    (root / "annotations" / "u1.json").write_text(json.dumps(annotation), encoding="utf-8")
    (root / "manifest.jsonl").write_text(json.dumps({"sample_id": "u1", "document_type": "utility_bill",
        "image": "images/u1.jpg", "annotation": "annotations/u1.json"}), encoding="utf-8")


def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///" + str(tmp_path / "seed.db"))


def test_seeding_saves_reviewed_values_and_is_idempotent(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    generator_folder(tmp_path / "gen")
    assert seed_demo.seed(tmp_path / "gen", 20) == 1
    assert seed_demo.seed(tmp_path / "gen", 20) == 0
    [record] = list_records()
    values = {f["key"]: f["value"] for f in record["fields"]}
    assert values["consumer_no"] == "5783072623" and values["amount_due"] == "200.00"
    assert record["pipeline"] == "demo_seed" and record["audit"][0]["changes"] == []
    assert record["metadata"]["business_identity"]["business_role"] == "buyer"
    assert (tmp_path / "data" / "raw_invoices" / (record["file_id"] + ".jpg")).exists()


def test_prediction_mistakes_become_corrections_on_the_dashboard(tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    generator_folder(tmp_path / "gen")
    (tmp_path / "pred" / "docs").mkdir(parents=True)
    wrong = {"consumer_no": "00000 42178", "amount_due": "200.00", "bill_date": "02/03/2025"}
    (tmp_path / "pred" / "docs" / "u1.json").write_text(json.dumps({"arms": {"layoutlm_llm_vlm": {
        "status": "ok", "fields": wrong, "sources": {k: "hosted_llm" for k in wrong}}}}), encoding="utf-8")
    seed_demo.seed(tmp_path / "gen", 20, tmp_path / "pred")
    [record] = list_records()
    assert record["pipeline"] == "layoutlm_llm_vlm"
    assert {c["key"] for c in record["audit"][0]["changes"]} >= {"consumer_no", "utility_provider"}
    quality = build(list_records(), document_amount)["quality"]
    assert quality["pipelines"][0]["name"] == "layoutlm_llm_vlm" and quality["pipelines"][0]["corrections"] >= 2


def test_captions_printed_inside_value_lines_are_not_saved():
    assert seed_demo.clean("vendor_gstin", "GSTIN: 07HQMXR3352D1Z0") == "07HQMXR3352D1Z0"
    assert seed_demo.clean("reason", "Reason: Goods returned - damaged packing") == "Goods returned - damaged packing"
    assert seed_demo.clean("billing_period", "Billing period: 23-03-2024 to 21-04-2024") == "23-03-2024 to 21-04-2024"
    assert seed_demo.clean("invoice_no", "INV/24-25/00001") == "INV/24-25/00001"
