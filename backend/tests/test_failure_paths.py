"""Failures must be bounded, visible, and unable to forge extraction provenance."""
import io
import json
import sys
from pathlib import Path
import pytest
import httpx
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from config import settings
from services import storage
from services.extractor import hosted_vlm
from services.errors import HostedError
from services.field_contract import canonical_fields


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings,"DATA_DIR",str(tmp_path))
    monkeypatch.setattr(settings,"DATABASE_URL","sqlite:///"+(tmp_path/"records.db").as_posix())
    monkeypatch.setattr(settings,"GROQ_API_KEY","fixture-private-key")
    monkeypatch.setattr(settings,"HOSTED_VLM_MODEL","fixture")
    monkeypatch.setattr(settings,"HOSTED_VLM_MAX_ATTEMPTS",2)
    monkeypatch.setattr(settings,"HOSTED_VLM_MIN_INTERVAL_SECONDS",0)


@pytest.mark.parametrize("content,finish", [
    ("not JSON","stop"),
    (json.dumps({"fields": {}}),"stop"),
    (json.dumps({"fields": {"amount_due": 100}}),"stop"),
    (json.dumps({"fields": {}}),"length"),
])
def test_invalid_provider_output_never_becomes_a_success(monkeypatch,content,finish):
    client_type = httpx.Client
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={"choices":[{"finish_reason":finish,"message":{"content":content}}]})
    monkeypatch.setattr(hosted_vlm.httpx,"Client",lambda **kwargs:client_type(transport=httpx.MockTransport(respond)))
    with pytest.raises(HostedError) as exc:
        hosted_vlm.extract_hosted(b"fixture","UTILITY_BILL")
    assert exc.value.attempts==2
    assert len(calls)==2
    assert not list((Path(settings.DATA_DIR)/"hosted_cache").glob("*.json"))
    assert settings.GROQ_API_KEY not in str(exc.value)


def test_network_failure_is_sanitized_and_retry_bounded(monkeypatch):
    client_type = httpx.Client
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ConnectError("fixture-private-key",request=request)
    monkeypatch.setattr(hosted_vlm.httpx,"Client",lambda **kwargs:client_type(transport=httpx.MockTransport(respond)))
    with pytest.raises(HostedError) as exc:
        hosted_vlm.extract_hosted(b"fixture","UTILITY_BILL")
    assert len(calls)==2 and exc.value.attempts==2
    assert settings.GROQ_API_KEY not in str(exc.value)


def test_save_confirmation_schema_and_source_are_server_enforced():
    fields=canonical_fields("UTILITY_BILL",[{"key":k,"value":v,"source":"layoutlm","confidence":90} for k,v in {
        "consumer_no":"=1+1","bill_date":"01/01/2025","utility_provider":"Fixture Utility","amount_due":"100"}.items()])
    run=storage.save_run({"file_id":"00000000-0000-0000-0000-000000000000","doc_type":"UTILITY_BILL","pipeline":"ocr_layoutlm","fields":fields,"line_items":[],"metadata":{}})
    with TestClient(app) as client:
        request={"run_id":run["run_id"],"fields":fields}
        assert client.post("/api/documents",json=request).status_code==422
        request["confirmed"]=True
        request["fields"]=[fields[0],*fields]
        assert client.post("/api/documents",json=request).status_code==422
        request["fields"]=[{**f,"source":"human","confidence":1} for f in fields]
        saved=client.post("/api/documents",json=request)
        assert saved.status_code==200
        assert all(f["source"]!="human" for f in saved.json()["fields"])
        assert "'=1+1" in client.get("/api/documents/export/csv").text


def test_upload_rejects_corrupt_and_oversize_images(monkeypatch):
    monkeypatch.setattr(settings,"MAX_UPLOAD_MB",1)
    with TestClient(app) as client:
        assert client.post("/api/upload",files={"file":("broken.png",b"not-an-image","image/png")}).status_code==422
        assert client.post("/api/upload",files={"file":("large.png",b"x"*(1024*1024+1),"image/png")}).status_code==413


def test_extraction_requires_ocr_for_local_and_valid_upload():
    stream=io.BytesIO()
    Image.new("RGB",(80,100)).save(stream,format="PNG")
    with TestClient(app) as client:
        file_id=client.post("/api/upload",files={"file":("invoice.png",stream.getvalue(),"image/png")}).json()[0]["file_id"]
        request={"file_id":file_id,"doc_type":"GST_INVOICE","pipeline":"ocr_layoutlm"}
        assert client.post("/api/extract",json=request).status_code==422
        request["file_id"]="00000000-0000-0000-0000-000000000000"
        assert client.post("/api/extract",json=request).status_code==404


@pytest.mark.parametrize('status,expected_attempts',[(429,2),(403,1)])
def test_google_ocr_retry_count_is_real_and_auth_is_not_retried(monkeypatch,status,expected_attempts):
    import asyncio
    from services import ocr_service
    from models.schemas import OCRResult
    monkeypatch.setattr(settings,'GOOGLE_CLOUD_VISION_API_KEY','fixture-private-key')
    monkeypatch.setattr(settings,'GOOGLE_VISION_MAX_ATTEMPTS',2)
    calls=[]
    async def provider(image):
        calls.append(image)
        if len(calls)==1:
            request=httpx.Request('POST','https://vision.googleapis.com/v1/images:annotate')
            response=httpx.Response(status,request=request)
            raise httpx.HTTPStatusError('private detail',request=request,response=response)
        return OCRResult(full_text='fixture',words=[])
    async def no_sleep(seconds):pass
    monkeypatch.setattr(ocr_service,'run_vision_ocr',provider)
    monkeypatch.setattr(ocr_service.asyncio,'sleep',no_sleep)
    if status==403:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:asyncio.run(ocr_service.ocr_document(b'fixture'))
        assert exc.value.headers['X-OCR-Attempts']=='1'
    else:
        result=asyncio.run(ocr_service.ocr_document(b'fixture'))
        assert result.metadata['attempts']==2
    assert len(calls)==expected_attempts
