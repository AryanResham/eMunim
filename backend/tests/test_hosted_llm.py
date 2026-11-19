"""Hosted token-tagging tier: offline, mocked transport, no keys or network."""
import json
import sys
from pathlib import Path
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import settings
from services.extractor import hosted_llm
from services.field_contract import keys_for
from services.errors import HostedError

WORDS = ["Bill", "No:", "INV/2024-25/", "0042", "Amount", "Due:", "1,250.00"]
BOXES = [[[x, y], [x + w, y], [x + w, y + 20], [x, y + 20]] for x, y, w in
         [(10, 10, 30), (45, 10, 30), (80, 10, 90), (172, 10, 40), (10, 60, 60), (75, 60, 40), (120, 60, 70)]]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test")
    monkeypatch.setattr(settings, "HOSTED_LLM_MODEL", "fixture-text-model")
    monkeypatch.setattr(settings, "HOSTED_VLM_MIN_INTERVAL_SECONDS", 0)


def mock(monkeypatch, fields_for):
    calls = []
    client_type = httpx.Client
    def respond(request):
        calls.append(json.loads(request.content))
        values = {k: None for k in keys_for("UTILITY_BILL")}
        values.update(fields_for(calls[-1]))
        return httpx.Response(200, json={"id": "fixture", "choices": [{"finish_reason": "stop",
            "message": {"content": json.dumps({"fields": values})}}], "usage": {"total_tokens": 9}})
    monkeypatch.setattr(hosted_llm.httpx, "Client", lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    return calls


def token_id(prompt, text):
    lines = json.loads(prompt)["lines"]
    return next(token[0] for line in lines for token in line if token[1] == text)


def test_serialization_rejoins_split_ids_and_keeps_reading_order():
    tokens, lines = hosted_llm.serialize_tokens(WORDS, BOXES, 1000, 1000)
    assert "INV/2024-25/0042" in tokens
    assert [len(line) for line in lines] == [3, 3]
    assert [token[0] for line in lines for token in line] == list(range(len(tokens)))
    assert all(len(token) == 6 for line in lines for token in line)


def test_text_only_request_and_values_come_from_ocr_tokens(monkeypatch):
    calls = mock(monkeypatch, lambda body: {"amount_due": [token_id(body["messages"][0]["content"], "1,250.00")]})
    result = hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    message = calls[0]["messages"][0]["content"]
    assert isinstance(message, str) and "image_url" not in json.dumps(calls[0])
    field = next(f for f in result["fields"] if f["key"] == "amount_due")
    assert field["value"] == "1,250.00" and field["source"] == "hosted_llm" and field["confidence"] is None
    assert result["metadata"]["rejected_fields"] == {}


def test_invented_token_id_rejects_only_that_field(monkeypatch):
    mock(monkeypatch, lambda body: {"amount_due": [999], "consumer_no": [token_id(body["messages"][0]["content"], "INV/2024-25/0042")]})
    result = hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    values = {f["key"]: f["value"] for f in result["fields"]}
    assert values["amount_due"] is None and values["consumer_no"] == "INV/2024-25/0042"
    assert result["metadata"]["rejected_fields"] == {"amount_due": [999]}


@pytest.mark.parametrize("bad", ["1,250.00", [1.5], [True], {"id": 1}])
def test_written_values_or_non_integer_ids_fail_schema(monkeypatch, bad):
    mock(monkeypatch, lambda body: {"amount_due": bad})
    with pytest.raises(HostedError) as exc:
        hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    assert exc.value.kind == "invalid_or_unavailable"


def test_cached_response_needs_no_network(monkeypatch):
    calls = mock(monkeypatch, lambda body: {})
    hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    again = hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000, allow_network=False)
    assert len(calls) == 1 and again["metadata"]["cached"] and again["metadata"]["attempts"] == 0


def test_missing_model_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_LLM_MODEL", "")
    with pytest.raises(HostedError) as exc:
        hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    assert exc.value.kind == "configuration"
