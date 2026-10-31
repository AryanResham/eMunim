"""Offline contract/integration tests; no models, API keys or network calls."""
import io
import json
import sys
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import settings
from services.extractor import pipeline, layoutlm_extractor, hosted_vlm
from services.field_contract import canonical_fields, keys_for
from services.errors import HostedError, ServiceUnavailable
from services.validator.rules_engine import review_document, parse_amount
from services import storage
from main import app

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_VISION_API_KEY", "")
    monkeypatch.setattr(settings, "HOSTED_VLM_MODEL", "")
    monkeypatch.setattr(settings, "LAYOUTLM_MODEL_ROOT", str(tmp_path / "missing-models"))

def image_bytes():
    output=io.BytesIO()
    Image.new("RGB",(60,80),"white").save(output,format="JPEG")
    return output.getvalue()

def utility(confidence=95):
    return canonical_fields("UTILITY_BILL", [{"key":key,"value":value,"confidence":confidence,"source":"layoutlm"} for key,value in {
        "consumer_no":"12345","bill_date":"01/01/2025","utility_provider":"Utility Ltd",
        "amount_due":"100.00"}.items()])

def arguments(name):
    return dict(pipeline=name,image_bytes=image_bytes(),doc_type="UTILITY_BILL",image_width=60,image_height=80,
                ocr_result={"full_text":"Utility bill","words":[{"text":"Utility","bounding_box":[[0,0],[10,0],[10,10],[0,10]]}]})

def stub_local(monkeypatch,fields=None):
    monkeypatch.setattr(layoutlm_extractor,"extract_fields",lambda **kw: fields if fields is not None else utility())

def test_local_never_calls_hosted(monkeypatch):
    stub_local(monkeypatch)
    monkeypatch.setattr(pipeline,"extract_hosted",lambda *a,**k: pytest.fail("Hosted called"))
    result=pipeline.run_pipeline(**arguments("ocr_layoutlm"))
    assert result["pipeline"]=="ocr_layoutlm"
    assert result["metadata"]["hosted"]["attempts"]==0

def test_hosted_needs_no_ocr_or_model(monkeypatch):
    monkeypatch.setattr(layoutlm_extractor,"extract_fields",lambda **kw: pytest.fail("Local called"))
    fields=[{**f,"source":"hosted_vlm","confidence":None} for f in utility()]
    monkeypatch.setattr(pipeline,"extract_hosted",lambda *a,**k: {"fields":fields,"metadata":{"attempts":1}})
    args=arguments("hosted_vlm");args["ocr_result"]=None
    result=pipeline.run_pipeline(**args)
    assert result["line_items"]==[]
    assert all(f["confidence"] is None for f in result["fields"])

def test_optional_absence_does_not_route(monkeypatch):
    stub_local(monkeypatch)
    monkeypatch.setattr(pipeline,"extract_hosted",lambda *a,**k: pytest.fail("Optional absence routed"))
    result=pipeline.run_pipeline(**arguments("layoutlm_hosted_fallback"))
    assert result["metadata"]["routing_reasons"]==[]

def test_hybrid_fills_gap_and_records_null_confidence(monkeypatch):
    fields=utility()
    fields[0]["value"]=None
    stub_local(monkeypatch,fields)
    remote=[{**f,"source":"hosted_vlm","confidence":None} for f in utility()]
    monkeypatch.setattr(pipeline,"extract_hosted",lambda *a,**k: {"fields":remote,"metadata":{"attempts":1}})
    result=pipeline.run_pipeline(**arguments("layoutlm_hosted_fallback"))
    assert result["fields"][0]["value"] is not None
    assert result["fields"][0]["confidence"] is None
    assert len(result["fields"])==len({f["key"] for f in result["fields"]})
    assert result["metadata"]["routing_reasons"]

def test_hybrid_outage_visible(monkeypatch):
    stub_local(monkeypatch,utility(30))
    def failure(*a,**kw): raise HostedError("Quota unavailable",attempts=2)
    monkeypatch.setattr(pipeline,"extract_hosted",failure)
    result=pipeline.run_pipeline(**arguments("layoutlm_hosted_fallback"))
    assert result["metadata"]["degraded"]
    assert result["validation"]["review_required"]
    assert result["metadata"]["hosted"]["attempts"]==2

def test_conflict_never_duplicates_key():
    remote=utility()
    remote[0]={**remote[0],"value":"different","source":"hosted_vlm","confidence":None}
    result,decisions,conflicts=pipeline.resolve_candidates("UTILITY_BILL",utility(),remote)
    assert len(result)==len({f["key"] for f in result})
    assert conflicts==["consumer_no"]

def test_review_ablations_do_not_change_values():
    fields=utility(30)
    before=json.dumps(fields)
    a=review_document("UTILITY_BILL",fields,"extraction_only")
    b=review_document("UTILITY_BILL",fields,"validation_review")
    c=review_document("UTILITY_BILL",fields,"validation_confidence_review")
    assert not a["review_required"] and not b["review_required"] and c["review_required"]
    assert json.dumps(fields)==before

def test_missing_taxes_not_zero():
    fields=canonical_fields("GST_INVOICE",[{"key":k,"value":v} for k,v in {"taxable_amount":"100","total_amount":"100"}.items()])
    result=review_document("GST_INVOICE",fields)
    check=next(r for r in result["rules"] if r["name"]=="Total reconciliation")
    assert check["passed"] is None
    assert parse_amount("NaN") is None
    assert parse_amount("₹1,000.00")==1000
    assert parse_amount("0")==0
    assert parse_amount(None) is None

def test_unavailable_weights_not_regex():
    with pytest.raises(ServiceUnavailable):
        layoutlm_extractor.extract_fields(image_bytes(),["word"],[[[0,0],[1,0],[1,1],[0,1]]],60,80,"UTILITY_BILL","word",strict=True)

def test_hosted_schema_and_cache(monkeypatch):
    import httpx
    monkeypatch.setattr(settings,"GROQ_API_KEY","test")
    monkeypatch.setattr(settings,"HOSTED_VLM_MODEL","fixture-model")
    client_type=httpx.Client
    calls=[]
    def respond(request):
        calls.append(request)
        values={k:None for k in keys_for("UTILITY_BILL")}
        values["amount_due"]="100"
        return httpx.Response(200,json={"id":"fixture","choices":[{"finish_reason":"stop","message":{"content":json.dumps({"fields":values})}}],"usage":{"total_tokens":5}})
    monkeypatch.setattr(hosted_vlm.httpx,"Client",lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    first=hosted_vlm.extract_hosted(image_bytes(),"UTILITY_BILL")
    second=hosted_vlm.extract_hosted(image_bytes(),"UTILITY_BILL",allow_network=False)
    assert len(calls)==1
    assert first["metadata"]["attempts"]==1
    assert second["metadata"]["cached"] and second["metadata"]["attempts"]==0
    assert all(f["confidence"] is None for f in first["fields"])

def test_provider_auth_error_no_retry(monkeypatch):
    import httpx
    monkeypatch.setattr(settings,"GROQ_API_KEY","test")
    monkeypatch.setattr(settings,"HOSTED_VLM_MODEL","fixture-model")
    client_type=httpx.Client;calls=[]
    def respond(request):
        calls.append(request);return httpx.Response(401,json={})
    monkeypatch.setattr(hosted_vlm.httpx,"Client",lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    with pytest.raises(HostedError) as exc:
        hosted_vlm.extract_hosted(image_bytes(),"UTILITY_BILL")
    assert exc.value.attempts==1 and len(calls)==1


@pytest.mark.parametrize("cooldown,expected_calls", [("7",2),("120",1)])
def test_provider_rate_limit_respects_cooldown_and_wait_bound(monkeypatch,cooldown,expected_calls):
    import httpx
    monkeypatch.setattr(settings,"GROQ_API_KEY","test")
    monkeypatch.setattr(settings,"HOSTED_VLM_MODEL","fixture-model")
    monkeypatch.setattr(settings,"HOSTED_VLM_MIN_INTERVAL_SECONDS",0)
    monkeypatch.setattr(settings,"HOSTED_VLM_MAX_RETRY_WAIT_SECONDS",30)
    client_type=httpx.Client;calls=[];sleeps=[]
    def respond(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(429,headers={"retry-after":cooldown})
        values={k:None for k in keys_for("UTILITY_BILL")}
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps({"fields":values})}}]})
    monkeypatch.setattr(hosted_vlm.httpx,"Client",lambda **kw: client_type(transport=httpx.MockTransport(respond)))
    monkeypatch.setattr(hosted_vlm.time,"sleep",sleeps.append)
    if expected_calls==1:
        with pytest.raises(HostedError) as exc:
            hosted_vlm.extract_hosted(image_bytes(),"UTILITY_BILL")
        assert exc.value.kind=="rate_limit" and exc.value.attempts==1
        assert sleeps==[]
    else:
        result=hosted_vlm.extract_hosted(image_bytes(),"UTILITY_BILL")
        assert result["metadata"]["retry_wait_seconds"]==7
        assert sleeps==[7]
    assert len(calls)==expected_calls

def test_upload_survives_memory_reset_and_rejects_bad_type():
    with TestClient(app) as client:
        assert client.post("/api/upload",files={"file":("bad.pdf",b"pdf","application/pdf")}).status_code==415
        response=client.post("/api/upload",files={"file":("invoice.jpg",image_bytes(),"image/jpeg")})
        assert response.status_code==200
        file_id=response.json()[0]["file_id"]
        from routers.upload import FILE_STORE
        FILE_STORE.clear()
        assert client.get("/api/files/"+file_id).status_code==200
        assert client.get("/api/files/../../config.py").status_code!=200

def test_edits_revalidated_and_persisted():
    run=storage.save_run({"file_id":"00000000-0000-0000-0000-000000000000","doc_type":"UTILITY_BILL","pipeline":"hosted_vlm",
        "fields":utility(),"line_items":[],"metadata":{"operational_reasons":[],"conflicts":[]}})
    fields=utility()
    fields[0]["value"]="corrected"
    next(f for f in fields if f["key"] == "amount_due")["value"]=None
    with TestClient(app) as client:
        invalid=client.post("/api/documents",json={"run_id":run["run_id"],"fields":fields,"confirmed":True})
        assert invalid.status_code==409
        fields=utility();fields[0]["value"]="corrected"
        saved=client.post("/api/documents",json={"run_id":run["run_id"],"fields":fields,"confirmed":True})
        assert saved.status_code==200
        record=saved.json()
        assert record["fields"][0]["source"]=="human" and record["fields"][0]["confidence"] is None
        assert record["original_fields"][0]["value"]=="12345"
        assert client.get("/api/documents/"+record["id"]).status_code==200
        assert client.get("/api/documents/summary").json()["count"]==1
        assert "corrected" in client.get("/api/documents/export/csv").text
        assert client.post("/api/documents",json={"run_id":run["run_id"],"fields":fields,"confirmed":True}).json()["id"]==record["id"]

def test_research_scoring_undefined_and_raw_accuracy():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"research"))
    from evaluate import evaluate
    fields=utility(20)
    entry={"id":"test","doc_type":"UTILITY_BILL","fields":{f["key"]:f["value"] for f in fields}}
    predictions=[{"id":"test","pipelines":{p:{"fields":fields,"metadata":{}} for p in pipeline.PIPELINES}}]
    report=evaluate([entry],predictions)
    local=report["pipelines"]["ocr_layoutlm"]
    assert local["complete_document_accuracy"]==1
    assert local["review"]["validation_confidence_review"]["accepted_error_rate"] is None
    assert local["review"]["validation_confidence_review"]["review_rate"]==1
