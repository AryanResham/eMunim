from fastapi.testclient import TestClient
from main import app
from config import settings
from services import model_registry
from services.extractor.field_mapper import DOC_TYPE_TO_MODEL


def test_ready_requires_loaded_models_and_google_configuration(monkeypatch):
    monkeypatch.setattr(model_registry,'status',dict(extractors={kind:'ready' for kind in DOC_TYPE_TO_MODEL}))
    monkeypatch.setattr(settings,'GOOGLE_CLOUD_VISION_API_KEY','fixture')
    client=TestClient(app)
    assert client.get('/api/ready').status_code==200
    model_registry.status['extractors']['GST_INVOICE']='missing'
    assert client.get('/api/ready').status_code==503
    assert client.get('/api/ready').json()['unavailable_models']==['GST_INVOICE']
    assert client.get('/api/health').status_code==200
    monkeypatch.setattr(settings,'GOOGLE_CLOUD_VISION_API_KEY','')
    assert client.get('/api/ready').json()['ocr_configured'] is False
