"""Prepare, capture and review an OCR-aligned pilot before isolated fine-tuning.

No test images enter this workflow. Capture requires --live and an explicit
physical-call budget. Training requires reviewed, hash-matched projections.
"""
import argparse
import asyncio
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import random
import re
import subprocess
import sys

from common import HERE, ROOT, LABEL_SETS, DOC_TYPE_TO_MODEL, digest, read_rows, write_json, write_rows, validate_row
from train_msme import field_map


def source_targets(annotation, kind):
    """Read visible source words; recover composite registration/consumption tags."""
    mapping = field_map(kind)
    words, boxes, targets = [], [], []
    source = annotation['ocr']['words']
    supplier_gstin = annotation['document']['supplier'].get('gstin')
    previous = None
    for word in source:
        target = mapping.get(word['field']) if word['role'] == 'value' else None
        text = word['text']
        if kind != 'UTILITY_BILL' and kind != 'EXPENSE_RECEIPT' and word['field'] == 'supplier.registration':
            if text == supplier_gstin:
                target = 'VENDOR_GSTIN'
        if kind == 'UTILITY_BILL' and word['field'] == 'extra.meter_readings':
            if previous and previous['field'] == word['field'] and previous['text'].casefold().rstrip(':') == 'used':
                if re.fullmatch(r'[\d,.]+', text):
                    target = 'UNITS_CONSUMED'
        # Renderer composite lines include these captions inside value regions.
        if word['field'] == 'extra.reason' and text.casefold().rstrip(':') == 'reason':
            target = None
        if word['field'] == 'extra.billing_period' and text.casefold().rstrip(':') in ('billing', 'period'):
            target = None
        words.append(text)
        boxes.append(word['bbox_1000'])
        targets.append(target)
        previous = word
    return dict(words=words, boxes=boxes, targets=targets)


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    minimum = min(max(0, a[2]-a[0])*max(0, a[3]-a[1]), max(0, b[2]-b[0])*max(0, b[3]-b[1]))
    return intersection/minimum if minimum else 0


def project_tokens(gold, ocr, width, height):
    """Keep OCR segmentation/order/boxes; reject ambiguous or lost supervision."""
    from common import normalize_box
    words, boxes, labels = [], [], []
    ambiguous = []
    matched = set()
    previous = None
    for index, word in enumerate(ocr['words']):
        vertices = word['bounding_box']
        if len(vertices) != 4 or any(len(v) != 2 or not (0 <= v[0] <= width and 0 <= v[1] <= height) for v in vertices):
            raise ValueError('OCR box lies outside its normalized image')
        if not word['text'].strip():
            raise ValueError('Empty OCR word')
        box = normalize_box([min(v[0] for v in vertices), min(v[1] for v in vertices),
                             max(v[0] for v in vertices), max(v[1] for v in vertices)], width, height)
        hits = [i for i, source_box in enumerate(gold['boxes']) if overlap(box, source_box) >= .5]
        # An OCR word spanning a key and value or two fields cannot receive a safe tag.
        targets = {gold['targets'][i] for i in hits}
        if len(targets) > 1:
            ambiguous.append(dict(index=index, text=word['text'], candidates=sorted(t or 'O' for t in targets)))
            target = None
        else:
            target = next(iter(targets), None)
            matched.update(i for i in hits if gold['targets'][i])
        labels.append(('I-' if previous == target else 'B-')+target if target else 'O')
        words.append(word['text'])
        boxes.append(box)
        previous = target
    required = {i for i,t in enumerate(gold['targets']) if t}
    optional_currency = set()
    if ocr.get('metadata',{}).get('provider') == 'rapidocr' and ocr.get('metadata',{}).get('optional_missing_currency') is True:
        # Missing standalone currency markers do not erase a numeric amount.
        # Keep their labels if detected, but require every non-currency value word.
        optional_currency = {i for i in required if gold['words'][i].strip() in ('₹','INR','Rs','Rs.','$')}
        required -= optional_currency
    missing = sorted(required-matched)
    coverage = len(required & matched)/len(required) if required else 0
    issues = []
    if ambiguous: issues.append('Ambiguous OCR words cross supervision boundaries')
    if missing: issues.append('Some labelled source words have no matched OCR word')
    if not required: issues.append('No positive source supervision')
    if not words: issues.append('No OCR words')
    return dict(words=words, boxes=boxes, labels=labels), dict(
        accepted=not issues, issues=issues, positive_word_coverage=coverage,
        missing_source_indices=missing, ambiguous=ambiguous,
        optional_missing_currency_indices=sorted(optional_currency-matched))


def source_fields(gold, kind):
    """Collapse repeated identical spans, preserving true printed field references."""
    sys.path.insert(0, str(ROOT/'research'))
    from evaluate import normalize
    spans = defaultdict(list)
    active, tokens = None, []
    for text, target in zip(gold['words']+[''], gold['targets']+[None]):
        if target != active:
            if active: spans[active.lower()].append(' '.join(tokens))
            active, tokens = target, []
        if target: tokens.append(text)
    fields = {}
    for tag in LABEL_SETS[kind]:
        if not tag.startswith('B-'): continue
        key = tag[2:].lower()
        values = spans[key]
        if len({normalize(key,v) for v in values}) > 1:
            raise ValueError('Conflicting repeated source values: '+key)
        fields[key] = values[0] if values else None
    return fields


def prepare(args, run):
    source = args.dataset.resolve()
    manifest_path = source/'manifest.jsonl'
    entries = read_rows(manifest_path)
    if len({e['sample_id'] for e in entries})!=len(entries):
        raise ValueError('Duplicate source sample IDs')
    groups, parties = {}, {}
    for item in entries:
        for identity in [item['base_document_id']]:
            if groups.setdefault(identity,item['split']) != item['split']:
                raise ValueError('Document group crosses splits')
        for identity in [item['supplier_id'],item['buyer_id']]:
            if parties.setdefault(identity,item['split']) != item['split']:
                raise ValueError('Party crosses splits')
    selected = []
    rng = random.Random(42)
    for kind in LABEL_SETS:
        for split, count in [('train',args.train_per_type),('val',args.development_per_type)]:
            available = sorted([e for e in entries if e['document_type'].upper()==kind and e['split']==split], key=lambda e:e['sample_id'])
            if not 1 <= count <= len(available): raise ValueError('Invalid pilot sample size')
            for item in rng.sample(available,count):
                image, annotation = source/item['image'], source/item['annotation']
                selected.append(dict(id=item['sample_id'], doc_type=kind, split='development' if split=='val' else split,
                    image=str(image),annotation=str(annotation),image_sha256=digest(image),annotation_sha256=digest(annotation),group=item['base_document_id']))
    plan = dict(version='ocr-aligned-v1',seed=42,source_manifest_sha256=digest(manifest_path),
        source=str(source),selected=len(selected),documents=selected,
        protocol='Source train/development only. Google OCR on exact normalized images. Preserve OCR tokenization/order/boxes; bbox label projection requires manual review. Ambiguous/missing positive supervision blocks training. Test data is excluded.')
    path = run/'plan.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8')) != plan:
        raise ValueError('Existing pilot plan differs; use a new run ID')
    write_json(path,plan)
    print(f"Prepared {len(selected)} images; no OCR calls or training. Plan: {path}")


def load_plan(run, progress=None):
    plan=json.loads((run/'plan.json').read_text(encoding='utf-8'))
    source=Path(plan['source'])
    if digest(source/'manifest.jsonl')!=plan['source_manifest_sha256']:
        raise ValueError('Source dataset manifest changed')
    source_entries={e['sample_id']:e for e in read_rows(source/'manifest.jsonl')}
    if len({e['id'] for e in plan['documents']})!=len(plan['documents']):
        raise ValueError('Duplicate pilot IDs')
    if any(e['split'] not in ('train','development') for e in plan['documents']):
        raise ValueError('Test data must never enter OCR-aligned training')
    for index,entry in enumerate(plan['documents'],1):
        original=source_entries.get(entry['id'])
        if not original or original['split'] not in ('train','val'):
            raise ValueError('Pilot record is not in source training/development data')
        expected_split='development' if original['split']=='val' else original['split']
        if entry['split']!=expected_split or entry['doc_type']!=original['document_type'].upper():
            raise ValueError('Pilot source split/type changed')
        if Path(entry['image']).resolve()!=(source/original['image']).resolve() or Path(entry['annotation']).resolve()!=(source/original['annotation']).resolve():
            raise ValueError('Pilot image/annotation differs from source manifest')
        if digest(entry['image'])!=entry['image_sha256'] or digest(entry['annotation'])!=entry['annotation_sha256']:
            raise ValueError('Source changed: '+entry['id'])
        if progress and (index%250==0 or index==len(plan['documents'])):
            progress(index,len(plan['documents']))
    return plan


def capture(args, run):
    from config import settings
    from services.ocr_service import ocr_document
    from utils.image_utils import normalize_image
    if not args.live or args.max_calls < 1:
        raise ValueError('capture requires --live and a positive --max-calls physical budget')
    plan=load_plan(run)
    settings.GOOGLE_VISION_MAX_ATTEMPTS=1
    used=0
    for entry in plan['documents']:
        image=normalize_image(Path(entry['image']).read_bytes())
        identity=hashlib.sha256(image).hexdigest()
        path=run/'ocr'/(entry['id']+'.json')
        image_path=run/'images'/(entry['id']+'.jpg')
        if path.exists():
            if json.loads(path.read_text(encoding='utf-8')).get('image_sha256')!=identity:
                raise ValueError('Cached OCR/image mismatch')
            continue
        if used>=args.max_calls: break
        used+=1
        result=asyncio.run(ocr_document(image)).model_dump(mode='json')
        if not result['words']: raise ValueError('No OCR words: '+entry['id'])
        result['image_sha256']=identity
        image_path.parent.mkdir(parents=True,exist_ok=True)
        image_path.write_bytes(image)
        write_json(path,result)
        print(f"Captured {entry['id']} ({used}/{args.max_calls} fresh physical attempts)",flush=True)
    print('Fresh OCR attempts:',used)


def project(run):
    from PIL import Image
    from utils.image_utils import normalize_image
    plan=load_plan(run)
    records=[]
    for entry in plan['documents']:
        path=run/'ocr'/(entry['id']+'.json')
        if not path.exists():
            records.append(dict(id=entry['id'],doc_type=entry['doc_type'],accepted=False,issues=['Missing cached OCR']))
            continue
        image=normalize_image(Path(entry['image']).read_bytes())
        ocr=json.loads(path.read_text(encoding='utf-8'))
        if ocr.get('image_sha256')!=hashlib.sha256(image).hexdigest():raise ValueError('Cached OCR belongs to a different image')
        width,height=Image.open(io.BytesIO(image)).size
        annotation=json.loads(Path(entry['annotation']).read_text(encoding='utf-8'))
        gold=source_targets(annotation,entry['doc_type'])
        aligned,audit=project_tokens(gold,ocr,width,height)
        image_path=run/'images'/(entry['id']+'.jpg')
        image_path.parent.mkdir(parents=True,exist_ok=True)
        image_path.write_bytes(image)
        row=dict(id=entry['id'],image=str(image_path),group=entry['group'],**aligned,
            fields=source_fields(gold,entry['doc_type']),provenance=ocr.get('metadata',{}).get('provider','google')+'_ocr_bbox_projection_requires_review',
            image_sha256=ocr['image_sha256'],ocr_sha256=digest(path))
        validate_row(row,LABEL_SETS[entry['doc_type']])
        projected=run/'projected'/(entry['id']+'.json')
        write_json(projected,row)
        records.append(dict(id=entry['id'],doc_type=entry['doc_type'],**audit,projection_sha256=digest(projected)))
    write_json(run/'alignment_audit.json',dict(documents=len(records),accepted=sum(r['accepted'] for r in records),records=records))
    review_path=run/'review.json'
    previous=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    review={}
    for record in records:
        if 'projection_sha256' not in record: continue
        old=previous.get(record['id'],{})
        review[record['id']]=old if old.get('projection_sha256')==record['projection_sha256'] else dict(
            projection_sha256=record['projection_sha256'],approved=False,exclude=False,reviewed_by='',
            notes='Check all tags against image and OCR; exclusions require a reason. Automatic acceptance is not manual verification.')
    write_json(review_path,review)
    print(f"Projected {len(records)} records; {sum(r['accepted'] for r in records)} pass automatic checks. Review: {review_path}")


def train(args, run):
    plan=load_plan(run)
    audit=json.loads((run/'alignment_audit.json').read_text(encoding='utf-8'))
    review=json.loads((run/'review.json').read_text(encoding='utf-8'))
    audits={r['id']:r for r in audit['records']}
    policy=getattr(args,'annotation_policy','reviewed')
    if policy not in ('reviewed','automatic_strict'):
        raise ValueError('Unknown annotation policy')
    data=defaultdict(list)
    excluded=[]
    for entry in plan['documents']:
        accepted=audits.get(entry['id'],{})
        decision=review.get(entry['id'],{})
        path=run/'projected'/(entry['id']+'.json')
        if policy=='automatic_strict':
            if not path.exists() or 'projection_sha256' not in accepted:
                raise ValueError('Missing OCR/projection; cannot start full retraining: '+entry['id'])
            if digest(path)!=accepted['projection_sha256']:
                raise ValueError('Automatic projection changed: '+entry['id'])
            if not accepted.get('accepted'):
                excluded.append(dict(id=entry['id'],reason=accepted.get('issues'),supervision='automatically_excluded_not_human_reviewed'))
                continue
            decision=dict(approved=True,reviewed_by='automatic_strict_projection',projection_sha256=accepted['projection_sha256'])
        if decision.get('exclude') is True:
            if not decision.get('reviewed_by','').strip() or not decision.get('notes','').strip() or decision.get('approved') is True:
                raise ValueError('Exclusion requires a reviewer/reason and approved=false')
            if not path.exists() or digest(path)!=decision.get('projection_sha256'):
                raise ValueError('Excluded projection changed')
            excluded.append(dict(id=entry['id'],reason=decision['notes'],reviewed_by=decision['reviewed_by']))
            continue
        if not accepted.get('accepted') or decision.get('approved') is not True or not decision.get('reviewed_by','').strip():
            raise ValueError('Training blocked: alignment not manually approved: '+entry['id'])
        if digest(path)!=accepted['projection_sha256'] or digest(path)!=decision.get('projection_sha256'):
            raise ValueError('Reviewed projection changed: '+entry['id'])
        row=json.loads(path.read_text(encoding='utf-8'))
        if digest(run/'ocr'/(entry['id']+'.json'))!=row['ocr_sha256'] or digest(row['image'])!=row['image_sha256']:
            raise ValueError('Reviewed OCR/image changed: '+entry['id'])
        row['training_supervision']='automatic_strict_projection_not_human_verified' if policy=='automatic_strict' else 'manually_reviewed_projection'
        data[entry['doc_type'],entry['split']].append(row)
    input_hashes=dict(plan=digest(run/'plan.json'),review=digest(run/'review.json') if policy=='reviewed' else None,
        audit=digest(run/'alignment_audit.json'),annotation_policy=policy)
    if (run/'training_input_hashes.json').exists():
        saved=json.loads((run/'training_input_hashes.json').read_text(encoding='utf-8'))
        if saved!=input_hashes:
            raise ValueError('Reviewed data changed since training started; use a new run ID')
    source=args.source_root.resolve()
    if getattr(args,'shared_source',False) and not getattr(args,'fresh_head',False):
        raise ValueError('Shared encoder checkpoint requires fresh per-type heads')
    if source.is_relative_to((run/'models').resolve()):
        raise ValueError('Source checkpoint must not be a pilot output directory')
    for kind in LABEL_SETS:
        if len(data[kind,'train'])<8 or not data[kind,'development']:
            raise ValueError('Insufficient reviewed training/development data: '+kind)
        if policy=='automatic_strict':
            for split in ('train','development'):
                planned=sum(e['doc_type']==kind and e['split']==split for e in plan['documents'])
                if len(data[kind,split]) < planned*.8:
                    raise ValueError('Less than 80% projection retention; inspect labels before training: '+kind+'/'+split)
    write_json(run/'training_input_hashes.json',input_hashes)
    write_json(run/'supervision.json',dict(policy=policy,human_verified=policy=='reviewed',
        counts={kind:{split:len(data[kind,split]) for split in ('train','development')} for kind in LABEL_SETS},excluded=len(excluded)))
    write_json(run/'exclusions.json',excluded)
    for kind in LABEL_SETS:
        folder=run/'data'/kind.lower()
        for split in ('train','development'):write_rows(folder/(split+'.jsonl'),data[kind,split])
        command=[sys.executable,'-u',str(HERE/'train_stage.py'),'--stage','synthetic','--doc-type',kind,
            '--source',str(source if getattr(args,'shared_source',False) else source/DOC_TYPE_TO_MODEL[kind]),'--output',str(run/'models'/DOC_TYPE_TO_MODEL[kind]),
            '--run-id',args.run_id,'--data-dir',str(folder),'--allow-missing-labels']
        if getattr(args,'selection_metric','auto')!='auto':command+=['--selection-metric',args.selection_metric]
        if not getattr(args,'fresh_head',False):command.append('--keep-head')
        subprocess.run(command,cwd=ROOT,check=True)


def locked_train(args, run):
    # Share the existing supervisor lock, including on Windows.
    lock=(HERE/'runs/training.lock').open('a+b')
    try:
        if sys.platform=='win32':
            import msvcrt
            lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        train(args,run)
    finally:
        lock.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','capture','project','train'])
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--dataset',type=Path,default=ROOT/'indian_erp_doc_generator/indian_erp_doc_generator/msme_6000')
    parser.add_argument('--train-per-type',type=int,default=100)
    parser.add_argument('--development-per-type',type=int,default=20)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--max-calls',type=int,default=0)
    parser.add_argument('--source-root',type=Path,default=HERE/'runs/msme-6000-20261031/models')
    parser.add_argument('--annotation-policy',choices=['reviewed','automatic_strict'],default='reviewed')
    parser.add_argument('--fresh-head',action='store_true',help='Transfer encoder and initialize a new per-type head')
    parser.add_argument('--shared-source',action='store_true',help='source-root is one shared encoder checkpoint, not a root of per-type checkpoints')
    parser.add_argument('--selection-metric',choices=['auto','entity_f1','field_f1'],default='auto')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
    run=HERE/'runs'/args.run_id
    if args.command=='prepare':prepare(args,run)
    elif args.command=='capture':capture(args,run)
    elif args.command=='project':project(run)
    else:locked_train(args,run)

if __name__=='__main__':main()
