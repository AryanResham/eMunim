"""Regression checks for real currency text and explicit resolver policies."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.validator.rules_engine import parse_amount, parse_date, review_document
from services.extractor.pipeline import resolve_candidates
from services.field_contract import canonical_fields

@pytest.mark.parametrize('text,expected',[
    ('\u20b91,250.00','1250'),('Rs . 1,250.00','1250'),
    ('INR\u00a01,250.00','1250'),('(\u20b9 1,250.00)','-1250'),
    ('\u20b9 (1,250.00)','-1250'),('0','0'),
])
def test_currency_and_ocr_spacing(text,expected):
    assert parse_amount(text)==Decimal(expected)

@pytest.mark.parametrize('text',['NaN','Infinity','INV1250','12.30.00','(-1250)'])
def test_invalid_amounts_not_silently_repaired(text):
    assert parse_amount(text) is None

@pytest.mark.parametrize('text',['04-Jul-2024','04/07/24','04.07.2024'])
def test_printed_date_variants(text):
    assert parse_date(text)==date(2024,7,4)

def test_policy_replaces_confident_wrong_value_and_preserves_review():
    local=canonical_fields('UTILITY_BILL',[dict(key='amount_due',value='100',confidence=99,source='layoutlm')])
    remote=canonical_fields('UTILITY_BILL',[dict(key='amount_due',value='120',confidence=None,source='hosted_vlm')])
    kept,_,_=resolve_candidates('UTILITY_BILL',local,remote,conflict_policy='keep_local')
    chosen,decisions,conflicts=resolve_candidates('UTILITY_BILL',local,remote,conflict_policy='prefer_hosted')
    assert next(f for f in kept if f['key']=='amount_due')['value']=='100'
    actual=next(f for f in chosen if f['key']=='amount_due')
    assert actual['value']=='120' and actual['confidence'] is None and actual['source']=='hosted_vlm'
    assert 'amount_due' in conflicts
    assert any(d['action']=='conflict_prefer_hosted_review' for d in decisions)
    assert review_document('UTILITY_BILL',chosen,conflicts=conflicts)['review_required']
    assert next(f for f in local if f['key']=='amount_due')['value']=='100'

def test_empty_hosted_value_never_erases_local_value():
    local=canonical_fields('UTILITY_BILL',[dict(key='amount_due',value='100',confidence=99)])
    chosen,_,_=resolve_candidates('UTILITY_BILL',local,[],conflict_policy='prefer_hosted')
    assert next(f for f in chosen if f['key']=='amount_due')['value']=='100'

def test_checkpoint_root_change_cannot_reuse_previous_weights(tmp_path,monkeypatch):
    from config import settings
    from services.extractor import layoutlm_extractor as local
    first=str((tmp_path/'first').resolve())
    monkeypatch.setattr(local,'_models',{})
    monkeypatch.setattr(settings,'LAYOUTLM_MODEL_ROOT',first)
    monkeypatch.setattr(local,'_folder_has_weights',lambda folder: local._model_root()==first)
    marker=object()
    monkeypatch.setattr(local,'_load_model',lambda folder: marker)
    assert local._get_model_for_doc_type('GST_INVOICE') is marker
    monkeypatch.setattr(settings,'LAYOUTLM_MODEL_ROOT',str(tmp_path/'missing'))
    assert local._get_model_for_doc_type('GST_INVOICE') is None
    monkeypatch.setattr(settings,'LAYOUTLM_MODEL_ROOT',first)
    assert local._get_model_for_doc_type('GST_INVOICE') is marker

def test_pipeline_records_effective_hosted_policy_and_conflicts(monkeypatch):
    from services.extractor import pipeline,layoutlm_extractor
    fields=canonical_fields('UTILITY_BILL',[dict(key='amount_due',value='100',confidence=99,source='layoutlm')])
    remote=canonical_fields('UTILITY_BILL',[dict(key='amount_due',value='120',confidence=None,source='hosted_vlm')])
    monkeypatch.setattr(layoutlm_extractor,'extract_fields',lambda **kwargs:fields)
    monkeypatch.setattr(pipeline,'extract_hosted',lambda *a,**k:dict(fields=remote,metadata=dict(attempts=0,cached=True)))
    result=pipeline.run_pipeline(pipeline='layoutlm_hosted_fallback',image_bytes=b'unused',
        ocr_result=dict(full_text='Amount 100',words=[dict(text='100',bounding_box=[[0,0],[5,0],[5,5],[0,5]])]),
        doc_type='UTILITY_BILL',image_width=10,image_height=10,conflict_policy='prefer_hosted')
    assert result['metadata']['conflict_policy']=='prefer_hosted'
    assert 'amount_due' in result['metadata']['conflicts']
    assert next(f for f in result['fields'] if f['key']=='amount_due')['value']=='120'
    assert result['validation']['review_required']
