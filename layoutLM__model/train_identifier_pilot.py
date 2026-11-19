"""GST-first fine-tuning, validation-gated expansion, offline cached test report."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

from common import HERE,ROOT,LABEL_SETS,DOC_TYPE_TO_MODEL,digest,read_rows,write_json

IDS={'invoice_no','po_number','bill_no','receipt_no','credit_note_no','debit_note_no','original_invoice_no'}


def state(run,phase,**extra):
    write_json(run/'status.json',dict(phase=phase,updated_at=datetime.now(timezone.utc).isoformat(),cloud_calls=0,**extra))


def pilot_gate(baseline,candidate):
    gain=candidate['raw_augmented']['identifier_accuracy']-baseline['raw_augmented']['identifier_accuracy']
    checks=dict(identifier_gain_at_least_10pp=gain>=.10,
        raw_overall_not_worse=candidate['raw_augmented']['accuracy']>=baseline['raw_augmented']['accuracy'],
        normalized_overall_within_1pp=candidate['normalized_augmented']['accuracy']>=baseline['normalized_augmented']['accuracy']-.01,
        clean_overall_within_1pp=candidate['normalized_clean']['accuracy']>=baseline['normalized_clean']['accuracy']-.01)
    return dict(passed=all(checks.values()),checks=checks,identifier_gain=gain,
        selection_data='Development only; no cached test scores used in gate')


def measure_development(run,root,kind,arm):
    from config import settings
    from PIL import Image
    from services.extractor import layoutlm_extractor as extractor
    from services.field_contract import canonical_fields
    sys.path.insert(0,str(ROOT/'research'))
    from evaluate import normalize
    settings.LAYOUTLM_MODEL_ROOT=str(root);settings.LAYOUTLM_DEVICE='cuda'
    extractor.release_models()
    metrics={}
    for name,split,normalized in [('raw_augmented','development',False),('normalized_augmented','development',True),('normalized_clean','clean_development',True)]:
        output=run/'development_comparison'/arm/(name+'.json')
        if output.exists():
            metrics[name]=json.loads(output.read_text(encoding='utf-8'))['metrics'];continue
        records=[]
        for row in read_rows(run/'data'/kind.lower()/(split+'.jsonl')):
            image=Path(row['image']).read_bytes();width,height=Image.open(io.BytesIO(image)).size
            boxes=[[[a*width/1000,b*height/1000],[c*width/1000,b*height/1000],
                [c*width/1000,d*height/1000],[a*width/1000,d*height/1000]] for a,b,c,d in row['boxes']]
            fields=canonical_fields(kind,extractor.extract_fields(image,row['words'],boxes,width,height,kind,
                ' '.join(row['words']),strict=True,normalize_tokens=normalized))
            values={f['key']:f.get('value') for f in fields}
            checks=[dict(key=k,expected=v,actual=values.get(k),correct=normalize(k,v)==normalize(k,values.get(k))) for k,v in row['fields'].items() if v]
            records.append(dict(id=row['id'],checks=checks))
        all_checks=[c for r in records for c in r['checks']];identifiers=[c for c in all_checks if c['key'] in IDS]
        result=dict(documents=len(records),correct=sum(c['correct'] for c in all_checks),total=len(all_checks),
            accuracy=sum(c['correct'] for c in all_checks)/len(all_checks),
            identifier_correct=sum(c['correct'] for c in identifiers),identifier_total=len(identifiers),
            identifier_accuracy=sum(c['correct'] for c in identifiers)/len(identifiers))
        metrics[name]=result;write_json(output,dict(metrics=result,records=records))
        print(arm,name,json.dumps(result),flush=True)
    extractor.release_models()
    return metrics


def benchmark_cached(run,root,arm,kinds):
    from config import settings
    from PIL import Image
    from services.extractor import layoutlm_extractor as extractor
    from services.field_contract import canonical_fields
    from utils.image_utils import normalize_image
    sys.path.insert(0,str(ROOT/'scripts'))
    from synthetic_visible_audit import norm
    folder=ROOT/'backend/data/synthetic_pipeline_sample_20261102_seed42'
    entries=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))['documents']
    refs={r['id']:r for r in json.loads((folder/'rendered_reference.json').read_text(encoding='utf-8'))['documents']}
    settings.LAYOUTLM_MODEL_ROOT=str(root);settings.LAYOUTLM_DEVICE='cuda'
    records=[]
    for kind in kinds:
        extractor.release_models()
        for entry in (e for e in entries if e['doc_type']==kind):
            output=run/'cached_test'/arm/'predictions'/(entry['id']+'.json')
            if output.exists():records.append(json.loads(output.read_text(encoding='utf-8')));continue
            image=normalize_image(Path(entry['image']).read_bytes())
            ocr_path=folder/'ocr'/(entry['id']+'.json');ocr=json.loads(ocr_path.read_text(encoding='utf-8'))
            if hashlib.sha256(image).hexdigest()!=ocr['image_sha256']:raise ValueError('Test OCR identity mismatch')
            width,height=Image.open(io.BytesIO(image)).size;diagnostics={}
            fields=canonical_fields(kind,extractor.extract_fields(image,[w['text'] for w in ocr['words']],
                [w['bounding_box'] for w in ocr['words']],width,height,kind,ocr['full_text'],strict=True,
                normalize_tokens=True,diagnostics=diagnostics))
            values={f['key']:f.get('value') for f in fields}
            checks=[dict(key=k,expected=v,actual=values.get(k),correct=norm(k,v)==norm(k,values.get(k))) for k,v in refs[entry['id']]['fields'].items()]
            row=dict(id=entry['id'],doc_type=kind,checks=checks,fields=fields,diagnostics=diagnostics,
                ocr_sha256=digest(ocr_path),checkpoint_sha256=digest(root/DOC_TYPE_TO_MODEL[kind]/'model.safetensors'))
            records.append(row);write_json(output,row)
        print('Cached test',arm,kind,'complete',flush=True)
    extractor.release_models()
    per_type={}
    for kind in kinds:
        rows=[r for r in records if r['doc_type']==kind];checks=[c for r in rows for c in r['checks']]
        ids=[c for c in checks if c['key'] in IDS]
        per_type[kind]=dict(documents=len(rows),correct=sum(c['correct'] for c in checks),total=len(checks),
            accuracy=sum(c['correct'] for c in checks)/len(checks),identifier_correct=sum(c['correct'] for c in ids),identifier_total=len(ids))
    checks=[c for r in records for c in r['checks']]
    result=dict(complete=len(records)==len(kinds)*10,documents=len(records),correct=sum(c['correct'] for c in checks),
        total=len(checks),accuracy=sum(c['correct'] for c in checks)/len(checks),per_type=per_type,
        protocol='Previously examined frozen test cohort; cached Google OCR; known types; printed-field accuracy, not entity F1. Rules and expansion gate frozen before this evaluation.',cloud_calls=0)
    write_json(run/'cached_test'/arm/'metrics.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',default='identifier-pilot-20261119');args=parser.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
    run=HERE/'runs'/args.run_id;run.mkdir(parents=True,exist_ok=True)
    guard=(HERE/'runs/training.lock').open('a+b')
    try:
        import msvcrt
        guard.seek(0);guard.write(b'1');guard.flush();guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        import torch
        torch.set_num_threads(4)
        if not torch.cuda.is_available():raise RuntimeError('CUDA required')
        if not (run/'dataset_audit.json').exists():
            state(run,'preparing_identifier_augmentation')
            from identifier_augmentation import prepare
            prepare(run)
        previous=HERE/'runs/ocr-augmented-20261119/models'
        protocol=dict(source='Completed v1 synthetic checkpoints; retain heads; fine-tune at 1e-5 for at most 3 epochs',
            gate='GST raw augmented development identifier accuracy +10pp; raw overall non-regression; normalized and clean overall within 1pp of v1.',
            test_selection='No test scores used in expansion gate',cloud_calls=0,activation='not_activated')
        write_json(run/'protocol.json',protocol)
        hashes={str(p.relative_to(run)):digest(p) for p in sorted((run/'data').rglob('*.jsonl'))}
        hashes['profile']=digest(run/'augmentation_profile.json');hashes['audit']=digest(run/'dataset_audit.json')
        for kind in LABEL_SETS:hashes['source/'+kind]=digest(previous/DOC_TYPE_TO_MODEL[kind]/'model.safetensors')
        for name in ('train_identifier_pilot.py','identifier_augmentation.py','ocr_augmentation.py','train_stage.py'):
            hashes['code/'+name]=digest(HERE/name)
        for name in ('ocr_compounds.py','layoutlm_extractor.py'):
            hashes['code/'+name]=digest(ROOT/'backend/services/extractor'/name)
        folder=ROOT/'backend/data/synthetic_pipeline_sample_20261102_seed42'
        for path in [folder/'manifest.json',folder/'rendered_reference.json',*sorted((folder/'ocr').glob('*.json'))]:
            hashes['test/'+str(path.relative_to(folder))]=digest(path)
        frozen=run/'input_hashes.json'
        if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=hashes:raise ValueError('Frozen inputs changed')
        write_json(frozen,hashes)
        state(run,'gst_baseline_validation')
        baseline=measure_development(run,previous,'GST_INVOICE','baseline_v1')
        completed=[];gate=None
        for kind in LABEL_SETS:
            if kind!='GST_INVOICE' and not gate['passed']:break
            state(run,'training',active_type=kind,completed_types=completed)
            output=run/'models'/DOC_TYPE_TO_MODEL[kind]
            if not (output/'training_summary.json').exists():
                command=[sys.executable,'-u',str(HERE/'train_stage.py'),'--stage','synthetic','--doc-type',kind,
                    '--source',str(previous/DOC_TYPE_TO_MODEL[kind]),'--output',str(output),'--run-id',args.run_id,
                    '--data-dir',str(run/'data'/kind.lower()),'--allow-missing-labels','--keep-head',
                    '--selection-metric','entity_f1','--epochs','3','--learning-rate','1e-5']
                with (run/(kind.lower()+'.log')).open('a',encoding='utf-8') as log:
                    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                        env={**os.environ,'HF_HUB_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'},check=True)
            completed.append(kind)
            if kind=='GST_INVOICE':
                state(run,'gst_candidate_validation',completed_types=completed)
                candidate=measure_development(run,run/'models',kind,'candidate_v2')
                gate=pilot_gate(baseline,candidate)
                write_json(run/'pilot_gate.json',dict(**gate,baseline=baseline,candidate=candidate))
                print('GST expansion gate:',json.dumps(gate),flush=True)
        state(run,'cached_test_evaluation',completed_types=completed,gate_passed=gate['passed'])
        old_fixed=benchmark_cached(run,previous,'v1_with_compound_fix',list(LABEL_SETS))
        new=benchmark_cached(run,run/'models','v2_with_compound_fix',completed)
        state(run,'complete' if gate['passed'] else 'pilot_gate_not_passed',completed_types=completed,
            gate_passed=gate['passed'],activation='not_activated',
            v1_fixed_accuracy=old_fixed['accuracy'],v2_accuracy=new['accuracy'],v2_evaluated_types=completed)
    except Exception as exc:
        state(run,'failed',error=str(exc));raise
    finally:guard.close()


if __name__=='__main__':main()
