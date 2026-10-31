import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_msme import score


def record():
    return dict(id='repeated', image='fixture', words=['100', '100'],
                gold_tags=['B-TOTAL_AMOUNT', 'B-TOTAL_AMOUNT'],
                predicted_fields={'total_amount': '100'})


def test_identical_printed_totals_are_one_semantic_value():
    result = score([record()], 'GST_INVOICE')
    assert result['field_f1'] == result['complete_document_accuracy'] == 1
    assert result['repeated_gold_fields'] == {'total_amount': 1}


def test_extra_prediction_is_penalized_even_for_absent_fields():
    row = record()
    row['predicted_fields']['vendor_name'] = 'extra'
    result = score([row], 'GST_INVOICE')
    assert result['fp'] == 1
    assert result['complete_document_accuracy'] == 0


def test_conflicting_gold_values_cannot_be_silently_collapsed():
    row = record()
    row['words'][1] = '200'
    with pytest.raises(ValueError, match='Conflicting gold'):
        score([row], 'GST_INVOICE')
