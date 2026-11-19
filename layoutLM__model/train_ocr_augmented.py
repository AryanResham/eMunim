"""Offline augmentation, six isolated models, then frozen cached-Vision evaluation."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

from common import ROOT,HERE,LABEL_SETS,DOC_TYPE_TO_MODEL,digest,write_json


def state(run,phase,**extra):
    write_json(run/'status.json',dict(phase=phase,updated_at=datetime.now(timezone.utc).isoformat(),cloud_calls=0,**extra))


def evaluate_cached(run,kind):
    """All 10 frozen test images/type; no OCR calls, no threshold selection."""
    from config import settings
    from services.extractor import layoutlm_extractor as extractor
    from services.field_contract import canonical_fields
    from utils.image_utils import normalize_image
    from PIL import Image
    sys.path.insert(0,str(ROOT/'scripts'))
    from synthetic_visible_audit import norm
    folder=ROOT/'backend/data/synthetic_pipeline_sample_20261102_seed42'
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    refs={r['id']:r for r in json.loads((folder/'rendered_reference.json').read_text(encoding='utf-8'))['documents']}
    settings.LAYOUTLM_MODEL_ROOT=str(run/'models')
    settings.LAYOUTLM_DEVICE='cuda'
    extractor.release_models()
    for entry in manifest['documents']:
        if entry['doc_type']!=kind:continue
        output=run/'cached_vision_evaluation'/'predictions'/(entry['id']+'.json')
        checkpoint=run/'models'/DOC_TYPE_TO_MODEL[kind]/'model.safetensors'
        checkpoint_hash=digest(checkpoint)
        if output.exists():
            saved=json.loads(output.read_text(encoding='utf-8'))
            if saved['checkpoint_sha256']==checkpoint_hash:continue
        image=normalize_image(Path(entry['image']).read_bytes())
        ocr_path=folder/'ocr'/(entry['id']+'.json')
        ocr=json.loads(ocr_path.read_text(encoding='utf-8'))
        if hashlib.sha256(image).hexdigest()!=ocr['image_sha256']:raise ValueError('Cached test OCR/image mismatch')
        width,height=Image.open(io.BytesIO(image)).size
        diagnostics={}
        fields=canonical_fields(kind,extractor.extract_fields(image,[w['text'] for w in ocr['words']],
            [w['bounding_box'] for w in ocr['words']],width,height,kind,ocr['full_text'],strict=True,diagnostics=diagnostics))
        values={f['key']:f.get('value') for f in fields}
        checks=[dict(key=k,expected=v,actual=values.get(k),correct=norm(k,v)==norm(k,values.get(k))) for k,v in refs[entry['id']]['fields'].items()]
        write_json(output,dict(id=entry['id'],doc_type=kind,fields=fields,checks=checks,
            diagnostics=diagnostics,checkpoint_sha256=checkpoint_hash,ocr_sha256=digest(ocr_path)))
    extractor.release_models()
    results=[json.loads(p.read_text(encoding='utf-8')) for p in (run/'cached_vision_evaluation/predictions').glob('*.json')]
    per_type={}
    for name in LABEL_SETS:
        rows=[r for r in results if r['doc_type']==name];checks=[c for r in rows for c in r['checks']]
        per_type[name]=dict(documents=len(rows),correct=sum(c['correct'] for c in checks),total=len(checks),
            printed_field_accuracy=sum(c['correct'] for c in checks)/len(checks) if checks else None)
    write_json(run/'cached_vision_evaluation/metrics.json',dict(complete=len(results)==60,
        protocol='Frozen 60 previously examined synthetic test images, same 432 printed-field checks. Cached Google OCR, known document types. No new OCR, model selection, threshold tuning or test-driven augmentation fitting.',
        documents=len(results),per_type=per_type,cloud_calls=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',default='ocr-augmented-20261119')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
    run=HERE/'runs'/args.run_id;run.mkdir(parents=True,exist_ok=True)
    guard=(HERE/'runs/training.lock').open('a+b')
    try:
        import msvcrt
        guard.seek(0);guard.write(b'1');guard.flush();guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        import torch
        if not args.prepare_only and not torch.cuda.is_available():raise RuntimeError('CUDA training unavailable')
        audit=run/'dataset_audit.json'
        if not audit.exists():
            state(run,'preparing_generated_annotations')
            from ocr_augmentation import prepare
            prepare(run)
        frozen=run/'input_hashes.json'
        inputs={str(p.relative_to(run)):digest(p) for p in sorted((run/'data').rglob('*.jsonl'))}
        inputs['augmentation_profile.json']=digest(run/'augmentation_profile.json')
        inputs['dataset_audit.json']=digest(audit)
        inputs['source_weights']=digest(HERE/'layoutlm-sroie-trained/model.safetensors')
        for script in ('ocr_augmentation.py','train_stage.py','train_ocr_augmented.py'):
            inputs['code/'+script]=digest(HERE/script)
        evaluation=ROOT/'backend/data/synthetic_pipeline_sample_20261102_seed42'
        for name in ('manifest.json','rendered_reference.json'):
            inputs['evaluation/'+name]=digest(evaluation/name)
        for path in sorted((evaluation/'ocr').glob('*.json')):
            inputs['evaluation/ocr/'+path.name]=digest(path)
        if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=inputs:raise ValueError('Frozen inputs changed')
        write_json(frozen,inputs)
        if args.prepare_only:
            state(run,'prepared',training_started=False);return
        completed=[]
        for kind in LABEL_SETS:
            output=run/'models'/DOC_TYPE_TO_MODEL[kind]
            state(run,'training',active_type=kind,completed_types=completed,training_started=True)
            if not (output/'training_summary.json').exists():
                command=[sys.executable,'-u',str(HERE/'train_stage.py'),'--stage','synthetic','--doc-type',kind,
                    '--source',str(HERE/'layoutlm-sroie-trained'),'--output',str(output),'--run-id',args.run_id,
                    '--data-dir',str(run/'data'/kind.lower()),'--allow-missing-labels','--selection-metric','entity_f1']
                with (run/(kind.lower()+'.log')).open('a',encoding='utf-8') as log:
                    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                        env={**os.environ,'TOKENIZERS_PARALLELISM':'false','HF_HUB_OFFLINE':'1'},check=True)
            completed.append(kind)
            state(run,'cached_test_evaluation',active_type=kind,completed_types=completed)
            evaluate_cached(run,kind)
        state(run,'complete',completed_types=completed,activation='not_activated',
            model_root=str(run/'models'),evaluation=str(run/'cached_vision_evaluation/metrics.json'))
    except Exception as exc:
        state(run,'failed',error=str(exc));raise
    finally:guard.close()


if __name__=='__main__':main()
