"""Offline identity, model retention and extraction confirmation checks."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from main import app
from config import settings
from services.business_profile import BusinessProfile, assess_parties
from services.extractor import layoutlm_extractor as local


def test_profile_is_durable_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get('/api/business-profile').json() is None
    response = client.put('/api/business-profile', json={"legal_name": "My business", "gstins": []})
    assert response.status_code == 200
    assert client.get('/api/business-profile').json()['legal_name'] == 'My business'
    with pytest.raises(ValidationError):
        BusinessProfile(legal_name='Business', gstins=['invalid'])


def test_extract_requires_confirmation_and_onboarding(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    client = TestClient(app)
    body = {"file_id": "not-used", "doc_type": "GST_INVOICE"}
    assert 'Confirm' in client.post('/api/extract', json=body).json()['detail']
    body['classification_confirmed'] = True
    assert 'onboarding' in client.post('/api/extract', json=body).json()['detail']


def test_party_conflict_is_flagged_without_swapping_values():
    fields = [{"key": "vendor_gstin", "value": "27ABCDE1234F1Z0"}]
    result = assess_parties(fields, {"gstins": ['27ABCDE1234F1Z0']}, 'buyer')
    assert not result['matched']
    assert 'appears as vendor' in result['reasons'][0]
    assert fields[0]['value'] == '27ABCDE1234F1Z0'


def test_per_type_models_are_retained(monkeypatch):
    monkeypatch.setattr(local, '_models', {})
    monkeypatch.setattr(local, '_folder_has_weights', lambda folder: True)
    loaded = []
    def load(folder):
        loaded.append(folder)
        return (folder, object(), [])
    monkeypatch.setattr(local, '_load_model', load)
    first = local._get_model_for_doc_type('GST_INVOICE')
    local._get_model_for_doc_type('CREDIT_NOTE')
    assert local._get_model_for_doc_type('GST_INVOICE') is first
    assert len(loaded) == 2
