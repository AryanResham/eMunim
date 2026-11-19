import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from identifier_augmentation import split_identifiers
from common import validate_row,LABEL_SETS


def row(identity):
    return dict(id=identity,words=['Invoice:','INV/24-25/00410','02-Jul-2024'],
        boxes=[[0,0,100,20],[120,0,350,20],[400,0,500,20]],
        labels=['O','B-INVOICE_NO','B-INVOICE_DATE'],fields=dict(invoice_no='INV/24-25/00410',invoice_date='02-Jul-2024'),
        augmentation=dict(operations={}))


def test_identifier_splits_preserve_characters_boxes_bio_and_reference():
    found=0
    for index in range(20):
        original=row(str(index));result=split_identifiers(original)
        assert result==split_identifiers(original)
        validate_row(result,LABEL_SETS['GST_INVOICE'])
        assert result['fields']==original['fields']
        tokens=[(w,l) for w,l in zip(result['words'],result['labels']) if l.endswith('INVOICE_NO')]
        assert ''.join(w for w,_ in tokens)=='INV/24-25/00410'
        assert tokens[0][1]=='B-INVOICE_NO'
        assert all(l=='I-INVOICE_NO' for _,l in tokens[1:])
        found+=len(tokens)>1
    assert found>10


def test_split_dates_have_a_single_begin_label():
    for index in range(20):
        result=split_identifiers(row(str(index)))
        tags=[l for l in result['labels'] if l.endswith('INVOICE_DATE')]
        assert tags[0]=='B-INVOICE_DATE' and tags.count('B-INVOICE_DATE')==1
        assert ''.join(w for w,l in zip(result['words'],result['labels']) if l.endswith('INVOICE_DATE'))=='02-Jul-2024'
