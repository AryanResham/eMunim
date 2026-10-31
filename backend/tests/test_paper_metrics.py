"""Known-answer fixtures verify math; fixtures are never published as measurements."""
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research'))
from metric_math import calibration,edit_distance,wilson
from evaluate import evaluate
from paper_experiment import ocr_metrics
from services.field_contract import canonical_fields
from services.extractor.pipeline import PIPELINES
from services.storage import save_run
from config import settings
from main import app


def fields():
    return canonical_fields('UTILITY_BILL',[{'key':k,'value':v,'source':'layoutlm','confidence':90} for k,v in {
        'consumer_no':'C1','bill_date':'01/01/2025','utility_provider':'Fixture','amount_due':'100'}.items()])


def test_micro_scores_missing_wrong_extra_and_undetected_consistency_error():
    original=fields();predicted=fields()
    next(f for f in predicted if f['key']=='consumer_no').update(value='WRONG',confidence=10)
    next(f for f in predicted if f['key']=='due_date').update(value='01/02/2025',confidence=10,source='layoutlm')
    entry={'id':'fixture','doc_type':'UTILITY_BILL','fields':{f['key']:f['value'] for f in original}}
    predictions=[{'id':'fixture','pipelines':{p:{'fields':predicted,'metadata':{}} for p in PIPELINES}}]
    m=evaluate([entry],predictions)['pipelines']['ocr_layoutlm']
    assert m['micro_precision']==pytest.approx(3/5)
    assert m['micro_recall']==pytest.approx(3/4)
    assert m['micro_field_f1']==pytest.approx(6/9)
    assert m['errors']=={'missing':0,'wrong':1,'extra':1}
    assert m['review']['validation_review']['accepted_error_rate']==1
    assert m['review']['validation_confidence_review']['accepted_error_rate'] is None
    assert m['calibration']['brier_score']==pytest.approx(.01)
    assert m['calibration']['correctness_auroc']==1
    with pytest.raises(ValueError,match='Duplicate prediction'):
        evaluate([entry],predictions+predictions)


def test_calibration_undefined_classes_and_ties():
    assert calibration([])['brier_score'] is None
    assert calibration([(.9,1)])['correctness_auroc'] is None
    assert calibration([(.5,0),(.5,1)])['correctness_auroc']==.5
    assert calibration([(.1,0),(.9,1)])['ece_10_bins']==pytest.approx(.1)
    assert wilson(0,0) is None
    lower,upper=wilson(0,10)
    assert 0<=lower<upper<1


def test_ordered_ocr_errors_have_explicit_denominators():
    assert edit_distance('kitten','sitting')==3
    assert edit_distance(['a','b'],['a','c'])==1
    measured=ocr_metrics('ABC 123','ABC 124')
    assert measured['character_edits']==1 and measured['reference_characters']==7
    assert measured['word_edits']==1 and measured['reference_words']==2


def test_entity_report_preserves_counts_as_json_numbers():
    from checkpoint_eval import entity_report
    report=entity_report([['B-X','I-X']],[['B-X','I-X']])
    assert report['X']['support']==1 and report['X']['f1-score']==1
    assert json.loads(json.dumps(report))==report


def test_revalidation_retains_server_conflicts_and_ignores_forged_sources(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'DATA_DIR',str(tmp_path))
    run=save_run({'doc_type':'UTILITY_BILL','fields':fields(),'metadata':{'conflicts':['consumer_no'],'operational_reasons':[]}})
    submitted=[{**f,'source':'human','confidence':1} for f in fields()]
    with TestClient(app) as client:
        response=client.post('/api/validate',json={'run_id':run['run_id'],'doc_type':'UTILITY_BILL','fields':submitted})
        assert response.status_code==200 and response.json()['review_required']
        assert 'consumer_no' in response.json()['flagged_fields']
        next(f for f in submitted if f['key']=='consumer_no')['value']='CORRECTED'
        assert not client.post('/api/validate',json={'run_id':run['run_id'],'doc_type':'UTILITY_BILL','fields':submitted}).json()['review_required']
        assert client.post('/api/validate',json={'run_id':run['run_id'],'doc_type':'CREDIT_NOTE','fields':submitted}).status_code==422


def test_research_route_no_placeholder_numbers_and_safe_downloads(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'RESEARCH_REPORT_DIR',str(tmp_path))
    with TestClient(app) as client:
        empty=client.get('/api/research/latest').json()
        assert empty['status']=='not_started' and empty['pipelines']=={}
        (tmp_path/'fixture').mkdir();(tmp_path/'latest.json').write_text(json.dumps({'run_id':'fixture'}))
        (tmp_path/'fixture/summary.json').write_text(json.dumps({'status':'unit_test_fixture','pipelines':{},'files':['summary.json']}))
        assert client.get('/api/research/latest').json()['status']=='unit_test_fixture'
        assert client.get('/api/research/files/summary.json').status_code==200
        assert client.get('/api/research/files/config.py').status_code==404
