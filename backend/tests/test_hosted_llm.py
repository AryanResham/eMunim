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
    monkeypatch.setattr(settings, "HOSTED_LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "HOSTED_LLM_API_KEY", "")
    monkeypatch.setattr(settings, "HOSTED_LLM_MIN_INTERVAL_SECONDS", None)
    monkeypatch.setattr(settings, "HOSTED_LLM_REASONING_EFFORT", "")


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


def parsed(lines):
    return [part.split(":", 1) for line in lines for part in line.split() if part != "||"]


def token_id(prompt, text):
    return next(int(i) for i, t in parsed(json.loads(prompt)["lines"]) if t == text)


def test_serialization_rejoins_split_ids_and_keeps_reading_order():
    tokens, lines = hosted_llm.serialize_tokens(WORDS, BOXES, 1000, 1000)
    assert "INV/2024-25/0042" in tokens
    assert lines == ["0:Bill 1:No: 2:INV/2024-25/0042", "3:Amount 4:Due: 5:1,250.00"]
    assert [int(i) for i, _ in parsed(lines)] == list(range(len(tokens)))


def test_wide_gap_is_marked_as_column_break():
    boxes = [[[x, 10], [x + 30, 10], [x + 30, 30], [x, 30]] for x in (10, 45, 600)]
    _, lines = hosted_llm.serialize_tokens(["Bill", "To", "GSTIN"], boxes, 1000, 1000)
    assert lines == ["0:Bill 1:To || 2:GSTIN"]


def test_request_too_large_is_explicit_and_not_retried(monkeypatch):
    calls = []
    client_type = httpx.Client
    def respond(request):
        calls.append(request)
        return httpx.Response(413, json={"error": {"code": "rate_limit_exceeded"}})
    monkeypatch.setattr(hosted_llm.httpx, "Client", lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    with pytest.raises(HostedError) as exc:
        hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    assert exc.value.kind == "too_large" and len(calls) == 1


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


def test_second_provider_gets_its_own_url_and_key(monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setattr(settings, "HOSTED_LLM_API_KEY", "gemini-test-key")
    seen = []
    client_type = httpx.Client
    def respond(request):
        seen.append((str(request.url), request.headers["authorization"]))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
            {"fields": {k: None for k in keys_for("UTILITY_BILL")}})}}]})
    monkeypatch.setattr(hosted_llm.httpx, "Client", lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    result = hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    assert seen == [("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "Bearer gemini-test-key")]
    assert result["metadata"]["provider"] == "generativelanguage.googleapis.com"


def test_pacing_follows_the_provider(monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_VLM_MIN_INTERVAL_SECONDS", 20)
    assert hosted_llm.provider()[2] == 20  # same provider as the VLM: share its spacing
    monkeypatch.setattr(settings, "HOSTED_LLM_BASE_URL", "https://other.example/v1")
    assert hosted_llm.provider()[2] == 0  # different provider, nothing set: no spacing
    monkeypatch.setattr(settings, "HOSTED_LLM_MIN_INTERVAL_SECONDS", 4)
    assert hosted_llm.provider()[2] == 4


def test_providers_do_not_wait_on_each_other(monkeypatch):
    from services.extractor import hosted_vlm
    sleeps = []
    monkeypatch.setattr(hosted_vlm.time, "sleep", sleeps.append)
    monkeypatch.setattr(hosted_vlm, "_next_request_at", {})
    hosted_vlm.pace("https://a.example", 30)
    hosted_vlm.pace("https://b.example", 30)
    assert sleeps == []
    hosted_vlm.pace("https://a.example", 30)
    assert len(sleeps) == 1 and 25 < sleeps[0] <= 30


def test_reasoning_effort_is_sent_only_when_configured(monkeypatch):
    calls = mock(monkeypatch, lambda body: {})
    hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    monkeypatch.setattr(settings, "HOSTED_LLM_REASONING_EFFORT", "none")
    hosted_llm.extract_hosted_llm(WORDS, BOXES, "UTILITY_BILL", 1000, 1000)
    assert "reasoning_effort" not in calls[0] and calls[1]["reasoning_effort"] == "none"
    assert len(calls) == 2  # a different effort is a different cache entry
