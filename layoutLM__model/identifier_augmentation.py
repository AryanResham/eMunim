"""Second augmentation version: OCR-split compound IDs and dates, correct BIO."""
import json
import re
from common import HERE,ROOT,LABEL_SETS,read_rows,write_json,write_rows,digest,validate_row
from ocr_aligned import source_targets
from ocr_augmentation import render_row,stable_rng
from services.extractor.ocr_compounds import _IDENTIFIER,_DATE

VERSION='identifier-augmentation-v2'


def split_identifiers(row):
    rng=stable_rng(VERSION+row['id'])
    words=[];boxes=[];labels=[];operations={'identifier_split':0,'date_split':0}
    for text,box,label in zip(row['words'],row['boxes'],row['labels']):
        is_id=bool(_IDENTIFIER.fullmatch(text));is_date=bool(_DATE.fullmatch(text))
        parts=[text]
        if (is_id or is_date) and rng.random()<.85:
            if is_id and rng.random()<.75:
                parts=[p for p in re.split(r'(/)',text) if p]
            else:parts=re.findall(r'[^/-]+|[/-]',text)
            operations['identifier_split' if is_id else 'date_split']+=1
        position=0
        for index,part in enumerate(parts):
            x0,y0,x1,y1=box
            left=round(x0+(x1-x0)*position/len(text));position+=len(part)
            right=round(x0+(x1-x0)*position/len(text))
            words.append(part);boxes.append([left,y0,right,y1])
            labels.append(label if index==0 or label=='O' else 'I-'+label[2:])
    result=dict(row,words=words,boxes=boxes,labels=labels)
    result['augmentation']=dict(row['augmentation'],identifier_version=VERSION,
        operations={**row['augmentation']['operations'],**operations})
    return result


def prepare(run):
    previous=HERE/'runs/ocr-augmented-20261119'
    profile=json.loads((previous/'augmentation_profile.json').read_text(encoding='utf-8'))
    # Calibration remains exactly the same 105 training extracts, never test OCR.
    write_json(run/'augmentation_profile.json',dict(base_profile=profile,identifier_version=VERSION,
        rates=dict(compound_split=.85,identifier_slash_only_fraction=.75),
        rates_status='Engineering presets frozen before validation or test comparison.'))
    dataset=ROOT/'indian_erp_doc_generator/indian_erp_doc_generator/msme_6000'
    original=json.loads((previous/'dataset_audit.json').read_text(encoding='utf-8'))
    if digest(dataset/'manifest.jsonl')!=original['manifest_sha256']:raise ValueError('Source manifest changed')
    identities={};parties={};groups={};seen=set();hashes=[]
    for entry in read_rows(dataset/'manifest.jsonl'):
        if entry['sample_id'] in seen:raise ValueError('Duplicate ID')
        seen.add(entry['sample_id'])
        for identifier,registry in [(entry['base_document_id'],identities),(entry['supplier_id'],parties),(entry['buyer_id'],parties)]:
            if registry.setdefault(identifier,entry['split'])!=entry['split']:raise ValueError('Split leakage')
        if entry['split']=='test':continue
        kind=entry['document_type'].upper();split='development' if entry['split']=='val' else 'train'
        annotation=dataset/entry['annotation'];image=(dataset/entry['image']).resolve()
        data=json.loads(annotation.read_text(encoding='utf-8'))
        if data['sample_id']!=entry['sample_id'] or data['split']!=entry['split']:raise ValueError('Annotation identity mismatch')
        gold=source_targets(data,kind)
        augmented=split=='development' or stable_rng('mixture:'+entry['sample_id']).random()>=.5
        row=render_row(gold,entry['sample_id'],image,entry['base_document_id'],kind,profile,augmented)
        if augmented:row=split_identifiers(row)
        validate_row(row,LABEL_SETS[kind]);groups.setdefault((kind,split),[]).append(row)
        if split=='development':
            groups.setdefault((kind,'clean_development'),[]).append(render_row(gold,entry['sample_id'],image,entry['base_document_id'],kind,profile,False))
        hashes.append(dict(id=entry['sample_id'],annotation_sha256=digest(annotation),image_sha256=digest(image)))
        if len(hashes)%600==0:print('Generated',len(hashes),'/5400',flush=True)
    counts={}
    for kind in LABEL_SETS:
        counts[kind]={}
        for split in ('train','development','clean_development'):
            rows=groups[kind,split]
            if len(rows)!=(800 if split=='train' else 100):raise ValueError('Unexpected split size')
            write_rows(run/'data'/kind.lower()/(split+'.jsonl'),rows)
            counts[kind][split]=len(rows)
    write_json(run/'dataset_audit.json',dict(version=VERSION,per_type=counts,source_hashes=hashes,
        source_manifest_sha256=digest(dataset/'manifest.jsonl'),cloud_calls=0,test_inputs_used=False))
