"""layoutlm_llm_vlm cascade: routing by OCR evidence and tier order. Offline; hosted tiers stubbed."""
import io
import sys
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import settings
from models.schemas import Pipeline
from services.extractor import pipeline, layoutlm_extractor
from services.field_contract import canonical_fields, REQUIRED
from services.errors import HostedError

VALUES = {"consumer_no": "12345", "bill_date": "01/01/2025", "utility_provider": "Utility Ltd", "amount_due": "100.00"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "HOSTED_VLM_MODEL", "")
    monkeypatch.setattr(settings, "HOSTED_LLM_MODEL", "")


def utility(confidence=95, missing=(), source="layoutlm"):
    return canonical_fields("UTILITY_BILL", [{"key": k, "value": None if k in missing else v,
        "confidence": None if source != "layoutlm" else confidence, "source": source} for k, v in VALUES.items()])


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(output, format="JPEG")
    return output.getvalue()


def run(name="layoutlm_llm_vlm", text="Consumer No 12345 Amount 100.00 Date 01/01/2025"):
    return pipeline.run_pipeline(pipeline=name, image_bytes=image_bytes(), doc_type="UTILITY_BILL", image_width=60, image_height=80,
        ocr_result={"full_text": text, "words": [{"text": "Utility", "bounding_box": [[0, 0], [10, 0], [10, 10], [0, 10]]}]})


def stub(monkeypatch, local, llm=None, vlm=None):
    """Install local/tier stubs; a tier passed as None fails the test if it is called."""
    calls = []
    monkeypatch.setattr(layoutlm_extractor, "extract_fields", lambda **kw: local)
    def tier(name, result):
        def call(*a, **k):
            calls.append(name)
            if result is None:
                pytest.fail(name + " tier should not be called")
            if isinstance(result, Exception):
                raise result
            return {"fields": result, "metadata": {"attempts": 1, "logical_calls": 1}}
        return call
    monkeypatch.setattr(pipeline, "extract_hosted_llm", tier("llm", llm))
    monkeypatch.setattr(pipeline, "extract_hosted", tier("vlm", vlm))
    return calls


def value(result, key):
    return next(f for f in result["fields"] if f["key"] == key)


@pytest.mark.parametrize("fields", [utility(), utility(30), utility(missing=["consumer_no"]), utility(missing=["amount_due", "bill_date"])])
@pytest.mark.parametrize("text", ["Consumer No 12345 Total 100.00 01/01/2025", "Electricity bill"])
def test_router_partitions_exactly_the_hybrid_reasons(fields, text):
    plan = pipeline.route_fallback("UTILITY_BILL", fields, text)
    assert sorted(plan["llm"] + plan["vlm"]) == sorted(pipeline.routing_reasons("UTILITY_BILL", fields))


@pytest.mark.parametrize("text,tier", [("Consumer No: 1234567", "llm"), ("Electricity bill", "vlm")])
def test_missing_field_and_its_required_rule_route_by_evidence(text, tier):
    plan = pipeline.route_fallback("UTILITY_BILL", utility(missing=["consumer_no"]), text)
    other = "vlm" if tier == "llm" else "llm"
    assert plan[tier] == ["Missing core field: consumer_no", "Required: consumer_no: Required field is missing"]
    assert plan[other] == []


@pytest.mark.parametrize("key,present,absent", [
    ("vendor_gstin", "GSTIN 27ABCDE1234F1Z5", "GSTIN pending"),
    ("vendor_gstin", "27 ABCDE 1234 F1Z5", "GSTIN on file"),
    ("invoice_date", "Date 04/07/2024", "Date pending"),
    ("total_amount", "Total 1,250.00", "Total pending"),
    ("invoice_no", "Invoice INV-0042", "Invoice pending"),
])
def test_evidence_patterns(key, present, absent):
    assert pipeline.ocr_has_evidence(key, present)
    assert not pipeline.ocr_has_evidence(key, absent)


def test_clean_document_calls_no_hosted_tier(monkeypatch):
    stub(monkeypatch, utility())
    result = run()
    assert result["metadata"]["routing_reasons"] == [] and result["metadata"]["cascade"]["tiers"] == []


def test_tagging_problem_stops_at_llm(monkeypatch):
    calls = stub(monkeypatch, utility(30), llm=utility(source="hosted_llm"))
    result = run()
    assert calls == ["llm"] and result["metadata"]["cascade"]["escalated"] == []
    assert all(value(result, k)["source"] == "hosted_llm" for k in REQUIRED["UTILITY_BILL"])
    assert {d["tier"] for d in result["metadata"]["decisions"]} == {"llm"}


def test_unread_text_skips_llm_and_goes_to_vlm(monkeypatch):
    calls = stub(monkeypatch, utility(missing=["consumer_no"]), vlm=utility(source="hosted_vlm"))
    result = run(text="Electricity bill")
    assert calls == ["vlm"] and result["metadata"]["cascade"]["tiers"] == ["vlm"]
    assert value(result, "consumer_no")["value"] == "12345" and value(result, "consumer_no")["source"] == "hosted_vlm"


def test_field_llm_cannot_find_escalates_to_vlm(monkeypatch):
    calls = stub(monkeypatch, utility(missing=["consumer_no"]), llm=utility(missing=["consumer_no"], source="hosted_llm"),
                 vlm=utility(source="hosted_vlm"))
    result = run()
    assert calls == ["llm", "vlm"]
    assert result["metadata"]["cascade"]["escalated"] == ["Missing core field after LLM: consumer_no"]
    assert value(result, "consumer_no")["source"] == "hosted_vlm"


def test_llm_outage_falls_back_to_vlm_and_is_visible(monkeypatch):
    calls = stub(monkeypatch, utility(30), llm=HostedError("Quota unavailable", attempts=2), vlm=utility(source="hosted_vlm"))
    result = run()
    assert calls == ["llm", "vlm"] and result["metadata"]["degraded"]
    assert result["metadata"]["hosted_llm"]["error"] == "provider_error" and result["metadata"]["hosted_llm"]["attempts"] == 2


def test_existing_hybrid_never_calls_llm(monkeypatch):
    calls = stub(monkeypatch, utility(30), vlm=utility(source="hosted_vlm"))
    run("layoutlm_hosted_fallback")
    assert calls == ["vlm"]


def test_api_schema_accepts_cascade():
    assert "layoutlm_llm_vlm" in Pipeline.__args__ and "layoutlm_llm_vlm" in pipeline.PIPELINES
