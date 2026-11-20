"""Dashboard aggregation: direction, months, parties, taxes, due dates, corrections."""
import sys
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import settings
from routers.documents import document_amount
from services.dashboard import build


def record(doc_type, role="buyer", status="reviewed", changes=(), pipeline="ocr_layoutlm", **values):
    return {"id": doc_type + str(len(values)), "doc_type": doc_type, "status": status, "pipeline": pipeline,
            "fields": [{"key": k, "value": v} for k, v in values.items()],
            "metadata": {"business_identity": {"business_role": role}},
            "audit": [{"changes": [{"key": k} for k in changes]}]}


ROWS = [
    record("GST_INVOICE", role="vendor", invoice_date="05/01/2025", total_amount="1,180.00", buyer_name="Acme",
           cgst_amount="90.00", sgst_amount="90.00"),
    record("PURCHASE_BILL", bill_date="20/03/2025", total_amount="500", vendor_name="Bolt Ltd",
           status="reviewed_with_issues", changes=["bill_no", "total_amount"], due_date="10/04/2025"),
    record("UTILITY_BILL", bill_date="02/03/2025", amount_due="200.00", utility_provider="Power Co",
           due_date="25/03/2025", pipeline="layoutlm_llm_vlm"),
    record("CREDIT_NOTE", credit_note_date="15/02/2025", credit_amount="50.00", vendor_name="Bolt Ltd"),
    record("EXPENSE_RECEIPT", receipt_date="not a date", amount="unreadable", vendor_name="Cafe"),
]


def test_money_in_out_and_adjustments_stay_separate():
    totals = build(ROWS, document_amount, today=date(2025, 3, 30))["totals"]
    assert totals["billed_in"] == 1180.0 and totals["billed_out"] == 700.0 and totals["adjustments"] == 50.0
    assert totals["documents"] == 5 and totals["needs_review"] == 1 and totals["undated"] == 1
    assert totals["corrected_documents"] == 1


def test_months_are_continuous_and_carry_taxes():
    months = build(ROWS, document_amount)["months"]
    assert [m["month"] for m in months] == ["2025-01", "2025-02", "2025-03"]
    assert months[0]["in"] == 1180.0 and months[0]["cgst"] == 90.0 and months[0]["sgst"] == 90.0
    assert months[1]["adjustment"] == 50.0 and months[1]["in"] == 0
    assert months[2]["out"] == 700.0 and months[2]["documents"] == 2


def test_parties_due_dates_and_quality():
    result = build(ROWS, document_amount, today=date(2025, 3, 30))
    assert [p["name"] for p in result["top_vendors"]] == ["Bolt Ltd", "Power Co"]
    assert result["top_customers"] == [{"name": "Acme", "amount": 1180.0, "count": 1}]
    assert [(d["party"], d["days"]) for d in result["due"]] == [("Bolt Ltd", 11), ("Power Co", -5)]
    assert {f["key"] for f in result["quality"]["corrected_fields"]} == {"bill_no", "total_amount"}
    assert {p["name"]: p["count"] for p in result["quality"]["pipelines"]} == {"ocr_layoutlm": 4, "layoutlm_llm_vlm": 1}
    local = next(p for p in result["quality"]["pipelines"] if p["name"] == "ocr_layoutlm")
    assert local["corrections"] == 2 and local["corrections_per_document"] == 0.5


def test_empty_database_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///" + str(tmp_path / "dash.db"))
    from main import app
    body = TestClient(app).get("/api/documents/dashboard").json()
    assert body["totals"]["documents"] == 0 and body["months"] == [] and body["note"]
