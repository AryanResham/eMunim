"""Small end-to-end offline API and manifest checks."""
import io
import sys
import json
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"research"))
from main import app
from config import settings
from services.extractor import pipeline
from services.field_contract import canonical_fields, keys_for
from run import load_manifest

def test_hosted_upload_extract_edit_validate_save_retrieve(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"DATA_DIR",str(tmp_path))
    monkeypatch.setattr(settings,"DATABASE_URL","sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(settings,"GOOGLE_CLOUD_VISION_API_KEY","")
    monkeypatch.setattr(settings,"LAYOUTLM_MODEL_ROOT",str(tmp_path/"no-models"))
    fields=canonical_fields("EXPENSE_RECEIPT",[
        {"key":"receipt_date","value":"01/01/2025","source":"hosted_vlm"},
        {"key":"vendor_name","value":"Fixture supplier","source":"hosted_vlm"},
        {"key":"amount","value":"250.00","source":"hosted_vlm"}])
    monkeypatch.setattr(pipeline,"extract_hosted",lambda *a,**kw:dict(fields=fields,metadata={"attempts":1,"logical_calls":1,"model":"fixture"}))
    buf=io.BytesIO();Image.new("RGB",(60,80),"white").save(buf,format="PNG")
    with TestClient(app) as client:
        client.put('/api/business-profile',json={'legal_name':'Offline fixture','gstins':[]}).raise_for_status()
        uploaded=client.post("/api/upload",files={"file":("image.png",buf.getvalue(),"image/png")}).json()[0]
        result=client.post("/api/extract",json={"file_id":uploaded["file_id"],"doc_type":"EXPENSE_RECEIPT","pipeline":"hosted_vlm","classification_confirmed":True})
        assert result.status_code==200
        run=result.json()
        next(f for f in run["fields"] if f["key"]=="amount")["value"]="275.50"
        validation=client.post("/api/validate",json={"doc_type":"EXPENSE_RECEIPT","fields":run["fields"]})
        assert validation.json()["overall_passed"]
        saved=client.post("/api/documents",json={"run_id":run["run_id"],"fields":run["fields"],"confirmed":True,"override_reason":"Offline fixture: business identity manually reviewed"})
        assert saved.status_code==200
        assert next(f for f in saved.json()["fields"] if f["key"]=="amount")["source"]=="human"
        assert client.get("/api/documents").json()["total"]==1
        assert client.get("/api/documents/summary").json()["by_type"]["EXPENSE_RECEIPT"]["printed_amount_total"]=="275.50"
        assert client.get("/api/files/"+uploaded["file_id"]).status_code==200

def test_manifest_rejects_group_leakage(tmp_path):
    for name in ("a","b"):
        (tmp_path/(name+".png")).write_bytes(name.encode())
    fields={k:None for k in keys_for("GST_INVOICE")}
    entries=[{"id":"a","image":"a.png","group":"same-vendor","split":"development","doc_type":"GST_INVOICE","fields":fields},
             {"id":"b","image":"b.png","group":"same-vendor","split":"test","doc_type":"GST_INVOICE","fields":fields}]
    path=tmp_path/"manifest.json";path.write_text(json.dumps({"documents":entries}))
    with pytest.raises(ValueError,match="crosses splits"):
        load_manifest(path)

def test_offline_cli_generates_comparison_report(tmp_path):
    import hashlib
    import subprocess
    from services.validator.rules_engine import review_document
    manifest=tmp_path/"manifest.json"
    (tmp_path/"invoice.png").write_bytes(b"fixture-image-not-used-for-inference")
    fields=canonical_fields("EXPENSE_RECEIPT",[
        {"key":"receipt_date","value":"01/01/2025","source":"layoutlm","confidence":95},
        {"key":"vendor_name","value":"Fixture","source":"layoutlm","confidence":95},
        {"key":"amount","value":"10","source":"layoutlm","confidence":95}])
    entry={"id":"one","image":"invoice.png","group":"independent","split":"test",
           "doc_type":"EXPENSE_RECEIPT","fields":{f["key"]:f["value"] for f in fields}}
    manifest.write_text(json.dumps({"documents":[entry]}))
    policy=tmp_path/"policy.json"
    policy.write_text(json.dumps({"version":"policy-v1","selected_on":"development","status":"frozen","review_threshold":75,"fallback_threshold":60}))
    predictions=tmp_path/"predictions.json"
    predictions.write_text(json.dumps({"manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "policy_sha256":hashlib.sha256(policy.read_bytes()).hexdigest(),"split":"test",
        "predictions":[{"id":"one","pipelines":{p:{"fields":fields,"metadata":{"elapsed_ms":1}}
            for p in pipeline.PIPELINES}}]}))
    report=tmp_path/"report.json"
    result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[2]/"research/run.py"),
        "score","--manifest",str(manifest),"--split","test","--policy",str(policy),
        "--predictions",str(predictions),"--out",str(report)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert report.with_suffix(".md").exists()
    assert len(json.loads(report.read_text())["pipelines"])==3

def test_research_budget_covers_both_hosted_tiers(monkeypatch):
    import run
    from services.errors import HostedError
    monkeypatch.setattr(settings,"HOSTED_VLM_MAX_ATTEMPTS",2)
    assert set(run.HOSTED_TIERS)=={"extract_hosted","extract_hosted_llm"}
    assert all(hasattr(pipeline,name) for name in run.HOSTED_TIERS)
    payload={"calls_used":0}
    def tier(*a,allow_network=True,**kw):
        if not allow_network: raise HostedError("No cache",kind="network_disabled")
        return {"metadata":{"attempts":1}}
    bounded=run.budgeted(tier,payload,True,3)
    bounded()
    assert payload["calls_used"]==1
    with pytest.raises(HostedError) as exc:
        bounded();bounded()
    assert exc.value.kind=="budget" and payload["calls_used"]==2
