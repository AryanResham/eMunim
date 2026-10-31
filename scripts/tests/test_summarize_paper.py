"""Known-answer supplementary analysis fixture; never a benchmark result."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_paper import analyze
from services.field_contract import canonical_fields


def test_improvement_regression_and_added_review_counts():
    truth = canonical_fields('UTILITY_BILL', [dict(key=k, value=v, source='layoutlm', confidence=99)
        for k, v in dict(consumer_no='C1', bill_date='01/01/2025',
                         utility_provider='Fixture', amount_due='100').items()])
    entries = [dict(id=str(i), doc_type='UTILITY_BILL', fields={f['key']: f['value'] for f in truth}) for i in range(2)]
    rows = []
    for i in range(2):
        local, hybrid = copy.deepcopy(truth), copy.deepcopy(truth)
        if i == 0:
            next(f for f in local if f['key'] == 'consumer_no').update(value='WRONG', confidence=10)
        else:
            next(f for f in hybrid if f['key'] == 'amount_due').update(value='200')
        remote = [{**f, 'source': 'hosted_vlm', 'confidence': None} for f in hybrid]
        rows.append(dict(id=str(i), pipelines={name: dict(fields=fields, metadata={})
            for name, fields in [('ocr_layoutlm', local), ('hosted_vlm', remote),
                                 ('layoutlm_hosted_fallback', hybrid)]}))
    result = analyze(entries, rows, 95)
    assert result['hybrid_field_changes']['improvements'] == 1
    assert result['hybrid_field_changes']['regressions'] == 1
    assert result['hybrid_field_changes']['wrong_to_different_wrong'] == 0
    assert result['incremental_C_vs_B']['ocr_layoutlm'] == dict(additional_reviewed=1,
        additional_incorrect_detected=1, additional_correct_reviewed=0, B_flags_removed_by_C=0)
    assert result['confidently_wrong_examples'][0]['prediction'] == '200'
    assert result['by_type']['UTILITY_BILL']['pipelines']['ocr_layoutlm']['documents'] == 2
    assert result['common_success']['documents'] == 2
    rows[0]['pipelines']['hosted_vlm']['error'] = 'Fixture provider failure'
    conditional = analyze(entries, rows, 95)
    assert conditional['common_success']['ids'] == ['1']
    assert conditional['by_type']['UTILITY_BILL']['pipelines']['hosted_vlm']['documents'] == 2
    assert conditional['by_type']['UTILITY_BILL']['pipelines']['hosted_vlm']['failures'] == 1
