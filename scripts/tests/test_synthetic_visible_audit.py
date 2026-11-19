"""Printed-value audit table: a newer arm adds a column; older result sets render unchanged."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import synthetic_visible_audit as audit

TYPES = ['GST_INVOICE', 'PURCHASE_BILL', 'EXPENSE_RECEIPT', 'UTILITY_BILL', 'CREDIT_NOTE', 'DEBIT_NOTE']


def fixture(out, arms):
    documents = [dict(id='d%d' % i, doc_type=kind, fields={'vendor_name': 'Acme'}) for i, kind in enumerate(TYPES)]
    (out / 'documents').mkdir(parents=True)
    (out / 'rendered_reference.json').write_text(json.dumps(dict(provenance='fixture', documents=documents,
        printed_values_missing_from_bio=[])), encoding='utf-8')
    for document in documents:
        result = {'pipelines': {arm: {'status': 'ok', 'result': {'fields': [{'key': 'vendor_name', 'value': 'Acme'}]}} for arm in arms}}
        (out / 'documents' / (document['id'] + '.json')).write_text(json.dumps(result), encoding='utf-8')


def header(out):
    lines = (out / 'PRINTED_VALUE_REPORT.md').read_text(encoding='utf-8').splitlines()
    return next(line for line in lines if line.startswith('| Type'))


def test_older_result_sets_render_exactly_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, 'OUT', tmp_path)
    fixture(tmp_path, audit.ARMS)
    audit.report()
    assert header(tmp_path) == '| Type | Images | OCR + regex | OCR + LayoutLM | Hosted VLM | Hybrid |'


def test_cascade_arm_gets_its_own_column(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, 'OUT', tmp_path)
    fixture(tmp_path, audit.ARMS + ['layoutlm_llm_vlm'])
    audit.report()
    assert header(tmp_path).endswith('| Hybrid | LLM/VLM cascade |')
    scores = json.loads((tmp_path / 'rendered_summary.json').read_text(encoding='utf-8'))['scores']
    cascade = [s for s in scores if s['pipeline'] == 'layoutlm_llm_vlm']
    assert len(cascade) == 6 and all(s['checked_value_accuracy'] == 1 for s in cascade)
