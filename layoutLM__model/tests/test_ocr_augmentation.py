import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ocr_augmentation as aug
from common import LABEL_SETS,validate_row,digest


def profile():
    return dict(colon_split_observed=1,box_offset_samples=[[-2,-1,2,1]],presets=dict(
        clean_training_fraction=.5,page_order_probability=1,amount_split_probability=1,
        same_span_merge_probability=1,character_confusion_probability=0,currency_drop_probability=0))


def gold():
    return dict(words=['Total:','1250.00','Vendor','Acme','Services'],
        boxes=[[0,100,70,115],[100,100,180,115],[0,0,70,15],[100,0,160,15],[165,0,220,15]],
        targets=[None,'AMOUNT',None,'VENDOR_NAME','VENDOR_NAME'])


def test_deterministic_bounded_and_valid_after_reorder_split_merge():
    a=aug.render_row(gold(),'sample','image.jpg','group','EXPENSE_RECEIPT',profile(),True)
    b=aug.render_row(gold(),'sample','image.jpg','group','EXPENSE_RECEIPT',profile(),True)
    assert a==b
    validate_row(a,LABEL_SETS['EXPENSE_RECEIPT'])
    assert a['words'][0]=='Vendor'
    assert a['fields']['amount']=='1250.00'
    assert a['fields']['vendor_name']=='Acme Services'
    assert a['augmentation']['operations']['caption_split']==1
    # A merged entity may concatenate words, but never incorporates its caption.
    assert a['words'][1]=='AcmeServices'
    assert a['labels'][1]=='B-VENDOR_NAME'
    assert all(not (label!='O' and 'Total' in word) for word,label in zip(a['words'],a['labels']))


def test_clean_variant_preserves_generator_inputs_and_references():
    g=gold();r=aug.render_row(g,'clean','image.jpg','group','EXPENSE_RECEIPT',profile(),False)
    assert r['words']==g['words'] and r['boxes']==g['boxes']
    assert r['labels']==['O','B-AMOUNT','O','B-VENDOR_NAME','I-VENDOR_NAME']


def test_forced_character_corruption_keeps_original_reference():
    p=profile();p['presets'].update(character_confusion_probability=1,same_span_merge_probability=0)
    r=aug.render_row(gold(),'noise','image.jpg','group','EXPENSE_RECEIPT',p,True)
    assert r['fields']['amount']=='1250.00'
    assert r['augmentation']['operations']['character_confusion']>0


def test_profile_excludes_even_present_test_caches(tmp_path,monkeypatch):
    from PIL import Image
    root=tmp_path/'runs/ocr-retrain-20261118';(root/'ocr').mkdir(parents=True);(root/'images').mkdir()
    image=root/'images/train.jpg';Image.new('RGB',(8,8),'white').save(image)
    annotation=tmp_path/'train.json'
    annotation.write_text(json.dumps(dict(document=dict(supplier={}),ocr=dict(words=[dict(text='Vendor',bbox_1000=[0,0,500,500],field='supplier.name',role='caption')]))),encoding='utf-8')
    entry=dict(id='train',split='train',doc_type='EXPENSE_RECEIPT',image=str(image),annotation=str(annotation),image_sha256=digest(image),annotation_sha256=digest(annotation))
    (root/'plan.json').write_text(json.dumps(dict(documents=[entry,dict(id='test',split='test')])) ,encoding='utf-8')
    (root/'ocr/train.json').write_text(json.dumps(dict(image_sha256=digest(image),words=[dict(text='Vendor',bounding_box=[[0,0],[4,0],[4,4],[0,4]])])),encoding='utf-8')
    (root/'ocr/test.json').write_text('INVALID IF READ',encoding='utf-8')
    monkeypatch.setattr(aug,'HERE',tmp_path)
    p=aug.fit_profile()
    assert p['profile_documents']==1
    assert p['profile_inputs'][0]['split']=='train'
