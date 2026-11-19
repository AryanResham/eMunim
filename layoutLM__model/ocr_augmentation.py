"""Deterministic OCR-like inputs from generator annotations; no OCR inference."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import re
import statistics

from common import ROOT, HERE, LABEL_SETS, digest, read_rows, write_json, write_rows, validate_row
from ocr_aligned import source_targets, source_fields

VERSION='ocr-augmentation-v1'


def stable_rng(identity):
    return random.Random(int(hashlib.sha256((VERSION+identity).encode()).hexdigest()[:16],16))


def fit_profile():
    """Only cached training Vision outputs; never read held-out test OCR."""
    from PIL import Image
    cache=HERE/'runs/ocr-retrain-20261118'
    plan=json.loads((cache/'plan.json').read_text(encoding='utf-8'))
    records=[]; offsets=[]; split_hits=split_total=0
    for entry in plan['documents']:
        if entry['split']!='train':continue
        path=cache/'ocr'/(entry['id']+'.json')
        if not path.exists():continue
        if digest(entry['annotation'])!=entry['annotation_sha256'] or digest(entry['image'])!=entry['image_sha256']:
            raise ValueError('Changed profile source')
        ocr=json.loads(path.read_text(encoding='utf-8'))
        snapshot=cache/'images'/(entry['id']+'.jpg')
        if digest(snapshot)!=ocr['image_sha256']:raise ValueError('OCR snapshot mismatch')
        width,height=Image.open(snapshot).size
        annotation=json.loads(Path(entry['annotation']).read_text(encoding='utf-8'))
        gold=source_targets(annotation,entry['doc_type'])
        unique=Counter(w['text'] for w in ocr['words'])
        source_unique=Counter(gold['words'])
        by_text={w['text']:w for w in ocr['words'] if unique[w['text']]==1}
        for text,box in zip(gold['words'],gold['boxes']):
            if text.endswith(':') and len(text)>1:
                split_total+=1
                split_hits+=int(unique[text[:-1]]>0 and unique[':']>0)
            if text not in by_text or source_unique[text]!=1:continue
            vertices=by_text[text]['bounding_box']
            actual=[min(v[0] for v in vertices)*1000/width,min(v[1] for v in vertices)*1000/height,
                    max(v[0] for v in vertices)*1000/width,max(v[1] for v in vertices)*1000/height]
            delta=[a-b for a,b in zip(actual,box)]
            if max(abs(d) for d in delta)<=15:offsets.append(delta)
        records.append(dict(id=entry['id'],doc_type=entry['doc_type'],split=entry['split'],
            ocr_sha256=digest(path),annotation_sha256=entry['annotation_sha256']))
    if not records or not offsets:raise ValueError('No usable training-only OCR calibration data')
    return dict(version=VERSION,seed=42,cloud_calls=0,profile_documents=len(records),
        profile_types=dict(Counter(r['doc_type'] for r in records)),profile_inputs=records,
        colon_split_observed=split_hits/max(1,split_total),colon_split_counts=[split_hits,split_total],
        box_offset_samples=offsets,box_offset_medians=[statistics.median(d[i] for d in offsets) for i in range(4)],
        presets=dict(clean_training_fraction=.5,page_order_probability=.75,amount_split_probability=.2,
            same_span_merge_probability=.05,character_confusion_probability=.001,currency_drop_probability=.1),
        limitations='Training Vision cache covers GST only. Box offsets and caption splits are empirical; other rates are explicitly engineering presets, not estimated distributions. Generated boxes are approximate. Test OCR never used to fit this profile.')


def page_order(tokens):
    """Group by vertical center, then left to right; preserve boxes, span identity."""
    rows=[]
    for token in sorted(tokens,key=lambda t:((t['box'][1]+t['box'][3])/2,t['box'][0])):
        center=(token['box'][1]+token['box'][3])/2
        height=max(1,token['box'][3]-token['box'][1])
        if rows and abs(center-rows[-1][0])<=height*.45:
            rows[-1][1].append(token)
        else:rows.append((center,[token]))
    return [token for _,row in rows for token in sorted(row,key=lambda t:t['box'][0])]


def render_row(gold, identity, image, group, kind, profile, augmented):
    rng=stable_rng(identity)
    tokens=[]; previous=None;span=-1
    for text,box,target in zip(gold['words'],gold['boxes'],gold['targets']):
        if target!=previous:span+=1
        tokens.append(dict(text=text,box=list(box),target=target,span=span))
        previous=target
    operations=Counter()
    if augmented:
        config=profile['presets']
        if rng.random()<config['page_order_probability']:
            tokens=page_order(tokens);operations['page_order']+=1
        expanded=[]
        for token in tokens:
            text=token['text'];parts=[text]
            if text in ('₹','Rs.','INR') and rng.random()<config['currency_drop_probability']:
                operations['currency_drop']+=1;continue
            if text.endswith(':') and len(text)>1 and rng.random()<profile['colon_split_observed']:
                parts=[text[:-1],':'];operations['caption_split']+=1
            elif re.fullmatch(r'[₹$]?\d[\d,.]*',text) and rng.random()<config['amount_split_probability']:
                parts=re.findall(r'\d+|[^\d]',text);operations['amount_split']+=1
            offset=profile['box_offset_samples'][rng.randrange(len(profile['box_offset_samples']))]
            x0,y0,x1,y1=token['box'];length=max(1,len(text));position=0
            for part in parts:
                box=[round(x0+(x1-x0)*position/length+offset[0]),round(y0+offset[1]),
                     round(x0+(x1-x0)*(position+len(part))/length+offset[2]),round(y1+offset[3])]
                position+=len(part)
                box=[min(1000,max(0,x)) for x in box]
                box[2]=max(box[0],box[2]);box[3]=max(box[1],box[3])
                altered=[]
                for char in part:
                    if char in '0O1I' and rng.random()<config['character_confusion_probability']:
                        char={'0':'O','O':'0','1':'I','I':'1'}[char];operations['character_confusion']+=1
                    altered.append(char)
                expanded.append(dict(token,text=''.join(altered),box=box))
        tokens=[]
        for token in expanded:
            if tokens and token['target'] and token['span']==tokens[-1]['span'] and token['target']==tokens[-1]['target'] and rng.random()<config['same_span_merge_probability']:
                before=tokens[-1];a,b=before['box'],token['box']
                before['text']+=token['text'];before['box']=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
                operations['same_span_merge']+=1
            else:tokens.append(token)
    labels=[];previous=None
    for token in tokens:
        current=(token['target'],token['span']) if token['target'] else None
        labels.append(('I-' if current==previous else 'B-')+token['target'] if current else 'O')
        previous=current
    row=dict(id=identity,image=str(image),group=group,words=[t['text'] for t in tokens],boxes=[t['box'] for t in tokens],
        labels=labels,fields=source_fields(gold,kind),supervision='generated_ocr_augmentation' if augmented else 'generator_clean',
        augmentation=dict(version=VERSION,operations=dict(operations),approximate_boxes=augmented))
    validate_row(row,LABEL_SETS[kind])
    return row


def prepare(run):
    dataset=ROOT/'indian_erp_doc_generator/indian_erp_doc_generator/msme_6000'
    profile=fit_profile()
    write_json(run/'augmentation_profile.json',profile)
    manifests=read_rows(dataset/'manifest.jsonl')
    identities={};parties={};seen=set();groups={};counts={};source_hashes=[]
    for entry in manifests:
        if entry['sample_id'] in seen:raise ValueError('Duplicate sample identity')
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
        groups.setdefault((kind,split),[]).append(row)
        source_hashes.append(dict(id=entry['sample_id'],annotation_sha256=digest(annotation),image_sha256=digest(image)))
        if split=='development':
            groups.setdefault((kind,'clean_development'),[]).append(render_row(gold,entry['sample_id'],image,entry['base_document_id'],kind,profile,False))
        if len(source_hashes)%300==0:print('Prepared',len(source_hashes),'/5400',flush=True)
    for kind in LABEL_SETS:
        counts[kind]={}
        for split in ('train','development','clean_development'):
            rows=groups[kind,split];expected=800 if split=='train' else 100
            if len(rows)!=expected:raise ValueError('Unexpected split count')
            write_rows(run/'data'/kind.lower()/(split+'.jsonl'),rows)
            counts[kind][split]=dict(documents=len(rows),augmented=sum(r['supervision']=='generated_ocr_augmentation' for r in rows))
    write_json(run/'dataset_audit.json',dict(source=str(dataset),manifest_sha256=digest(dataset/'manifest.jsonl'),
        profile_sha256=digest(run/'augmentation_profile.json'),cloud_calls=0,test_inputs_used=False,
        per_type=counts,source_hashes=source_hashes))
    return profile
