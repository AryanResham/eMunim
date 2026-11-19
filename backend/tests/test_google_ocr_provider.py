import asyncio
import hashlib
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from config import Settings,settings
from services import ocr_service
from models.schemas import OCRResult,OCRWord


def test_google_is_the_only_configurable_provider(monkeypatch):
    assert Settings(OCR_PROVIDER='google_vision').OCR_PROVIDER=='google_vision'
    with pytest.raises(ValidationError):
        Settings(OCR_PROVIDER='rapidocr')


def test_google_provider_and_metadata_without_live_calls(monkeypatch):
    monkeypatch.setattr(settings,'GOOGLE_CLOUD_VISION_API_KEY','fixture-only')
    calls=[]
    async def vision(image):
        calls.append(image)
        return OCRResult(full_text='123',words=[OCRWord(text='123',bounding_box=[[0,0],[3,0],[3,2],[0,2]],confidence=.9)])
    monkeypatch.setattr(ocr_service,'run_vision_ocr',vision)
    result=asyncio.run(ocr_service.ocr_document(b'fixture'))
    assert calls==[b'fixture']
    assert result.metadata['provider']=='google_vision'
    assert result.metadata['version']==ocr_service.OCR_VERSION


def test_missing_google_key_does_not_use_local_fallback(monkeypatch):
    monkeypatch.setattr(settings,'GOOGLE_CLOUD_VISION_API_KEY','')
    async def forbidden(image):raise AssertionError('Provider must not run')
    monkeypatch.setattr(ocr_service,'run_vision_ocr',forbidden)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ocr_service.ocr_document(b'fixture'))
    assert exc.value.status_code==503
    assert exc.value.headers['X-OCR-Attempts']=='0'


def test_endpoint_ignores_historical_local_ocr_cache(tmp_path,monkeypatch):
    from routers import ocr
    image=b'fixture'
    monkeypatch.setattr(ocr,'load_image',lambda file_id:image)
    monkeypatch.setattr(ocr,'data_dir',lambda:tmp_path)
    cache=tmp_path/'ocr_cache';cache.mkdir()
    old_key=hashlib.sha256(image+b'rapidocr-caption-split-v2').hexdigest()
    (cache/(old_key+'.json')).write_text(json.dumps(dict(full_text='old-local',words=[])),encoding='utf-8')
    calls=[]
    async def vision(data):
        calls.append(data)
        return OCRResult(full_text='vision',words=[OCRWord(text='vision',bounding_box=[[0,0],[3,0],[3,2],[0,2]])])
    monkeypatch.setattr(ocr,'ocr_document',vision)
    result=asyncio.run(ocr.run_ocr(ocr.OCRRequest(file_id='fixture')))
    assert calls==[image]
    assert result.full_text=='vision'
    # A second request must reuse the Google-versioned cache.
    assert asyncio.run(ocr.run_ocr(ocr.OCRRequest(file_id='fixture'))).full_text=='vision'
    assert len(calls)==1
