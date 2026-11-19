import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ocr_aligned import project_tokens, source_targets, source_fields

def word(text,box):
    x0,y0,x1,y1=box
    return dict(text=text,bounding_box=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]])

def test_split_amount_tokens_keep_vision_order_and_get_contiguous_bio():
    gold=dict(words=['Total:','1,250.00'],boxes=[[0,0,100,20],[200,0,400,20]],targets=[None,'TOTAL_AMOUNT'])
    ocr=dict(words=[word('Total',[0,0,80,20]),word(':',[80,0,100,20]),
        word('1,250',[200,0,340,20]),word('.',[340,0,350,20]),word('00',[350,0,400,20])])
    aligned,audit=project_tokens(gold,ocr,1000,1000)
    assert audit['accepted'] and audit['positive_word_coverage']==1
    assert aligned['words']==['Total',':','1,250','.','00']
    assert aligned['labels']==['O','O','B-TOTAL_AMOUNT','I-TOTAL_AMOUNT','I-TOTAL_AMOUNT']

def test_reading_order_is_not_replaced_with_generator_order():
    gold=dict(words=['A','100'],boxes=[[0,0,50,20],[200,0,250,20]],targets=['VENDOR_NAME','TOTAL_AMOUNT'])
    aligned,audit=project_tokens(gold,dict(words=[word('100',[200,0,250,20]),word('A',[0,0,50,20])]),1000,1000)
    assert audit['accepted']
    assert aligned['words']==['100','A']
    assert aligned['labels']==['B-TOTAL_AMOUNT','B-VENDOR_NAME']

def test_key_value_merge_is_rejected_instead_of_training_wrong_labels():
    gold=dict(words=['Total','100'],boxes=[[0,0,50,20],[50,0,100,20]],targets=[None,'TOTAL_AMOUNT'])
    _,audit=project_tokens(gold,dict(words=[word('Total100',[0,0,100,20])]),1000,1000)
    assert not audit['accepted'] and audit['ambiguous']

def test_missing_gold_value_is_rejected():
    gold=dict(words=['100'],boxes=[[0,0,50,20]],targets=['TOTAL_AMOUNT'])
    _,audit=project_tokens(gold,dict(words=[word('unrelated',[200,0,250,20])]),1000,1000)
    assert not audit['accepted'] and audit['missing_source_indices']==[0]

def test_wrong_image_coordinates_are_rejected():
    with pytest.raises(ValueError,match='outside'):
        project_tokens(dict(boxes=[],targets=[]),dict(words=[word('X',[0,0,1001,20])]),1000,1000)

def test_composite_registration_and_consumption_are_not_left_unlabelled():
    annotation=dict(document=dict(supplier=dict(gstin='09ABCDE1234F1Z0')),ocr=dict(words=[
        dict(text='GSTIN:',field='supplier.registration',role='value',bbox_1000=[0,0,30,20]),
        dict(text='09ABCDE1234F1Z0',field='supplier.registration',role='value',bbox_1000=[40,0,140,20])]))
    assert source_targets(annotation,'PURCHASE_BILL')['targets']==[None,'VENDOR_GSTIN']
    annotation['ocr']['words']=[
        dict(text='Used:',field='extra.meter_readings',role='value',bbox_1000=[0,0,30,20]),
        dict(text='32',field='extra.meter_readings',role='value',bbox_1000=[40,0,60,20])]
    assert source_targets(annotation,'UTILITY_BILL')['targets']==[None,'UNITS_CONSUMED']

def test_repeated_identical_field_values_collapse_and_conflicts_fail():
    gold=dict(words=['100','X','100'],targets=['TOTAL_AMOUNT',None,'TOTAL_AMOUNT'])
    assert source_fields(gold,'GST_INVOICE')['total_amount']=='100'
    gold['words'][-1]='200'
    with pytest.raises(ValueError,match='Conflicting'):
        source_fields(gold,'GST_INVOICE')

def test_source_test_record_cannot_be_relabelled_as_training(tmp_path):
    import json
    from ocr_aligned import load_plan, digest
    source=tmp_path/'source';source.mkdir()
    original=dict(sample_id='test1',split='test',document_type='gst_invoice',image='x.jpg',annotation='x.json')
    (source/'manifest.jsonl').write_text(json.dumps(original)+'\n',encoding='utf-8')
    run=tmp_path/'run';run.mkdir()
    (run/'plan.json').write_text(json.dumps(dict(source=str(source),source_manifest_sha256=digest(source/'manifest.jsonl'),
        documents=[dict(id='test1',split='train',doc_type='GST_INVOICE')])),encoding='utf-8')
    with pytest.raises(ValueError,match='not in source training'):
        load_plan(run)

def test_unreviewed_projection_cannot_start_training(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    import ocr_aligned as module
    monkeypatch.setattr(module,'load_plan',lambda run:dict(documents=[dict(id='x',doc_type='GST_INVOICE',split='train')]))
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:pytest.fail('Unreviewed data started training'))
    (tmp_path/'alignment_audit.json').write_text(json.dumps(dict(records=[dict(id='x',accepted=True)])),encoding='utf-8')
    (tmp_path/'review.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='not manually approved'):
        module.train(SimpleNamespace(),tmp_path)

def test_automatic_training_excludes_failed_alignment_and_uses_fresh_heads(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    import ocr_aligned as module
    entries=[];audits=[]
    (tmp_path/'projected').mkdir();(tmp_path/'ocr').mkdir()
    image=tmp_path/'image.jpg';image.write_bytes(b'fixture')
    for kind in module.LABEL_SETS:
        for index in range(10):
            identity=kind+str(index)
            entries.append(dict(id=identity,doc_type=kind,split='development' if index==9 else 'train'))
            ocr=tmp_path/'ocr'/(identity+'.json');ocr.write_text('{}',encoding='utf-8')
            path=tmp_path/'projected'/(identity+'.json')
            path.write_text(json.dumps(dict(id=identity,image=str(image),image_sha256=module.digest(image),ocr_sha256=module.digest(ocr))),encoding='utf-8')
            audits.append(dict(id=identity,accepted=index!=0,issues=[] if index else ['missing positive word'],projection_sha256=module.digest(path)))
    (tmp_path/'plan.json').write_text('{}',encoding='utf-8')
    (tmp_path/'alignment_audit.json').write_text(json.dumps(dict(records=audits)),encoding='utf-8')
    (tmp_path/'review.json').write_text('{}',encoding='utf-8')
    monkeypatch.setattr(module,'load_plan',lambda run:dict(documents=entries))
    commands=[]
    monkeypatch.setattr(module.subprocess,'run',lambda command,**kwargs:commands.append(command))
    module.train(SimpleNamespace(source_root=tmp_path/'sroie',run_id='fixture',annotation_policy='automatic_strict',fresh_head=True,shared_source=True,selection_metric='entity_f1'),tmp_path)
    assert len(commands)==6 and all('--keep-head' not in c for c in commands)
    assert all(c[c.index('--source')+1]==str((tmp_path/'sroie').resolve()) for c in commands)
    assert all(c[c.index('--selection-metric')+1]=='entity_f1' for c in commands)
    supervision=json.loads((tmp_path/'supervision.json').read_text(encoding='utf-8'))
    assert not supervision['human_verified'] and supervision['excluded']==6
    assert all(v==dict(train=8,development=1) for v in supervision['counts'].values())
    assert json.loads((tmp_path/'review.json').read_text(encoding='utf-8'))=={}

def test_ocr_tag_selection_can_use_entity_f1_without_changing_legacy_default():
    from train_stage import selection_score
    scores=dict(entity_f1=.9,field_f1=.2)
    assert selection_score(scores)==.2
    assert selection_score(scores,'entity_f1')==.9
