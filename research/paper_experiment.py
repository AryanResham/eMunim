"""Bounded, resumable production-pipeline pilot on preselected held-out synthetic data."""
import argparse
import asyncio
import hashlib
import io
import json
import math
import random
import sys
import time
import unicodedata
import importlib.metadata
import platform
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'layoutLM__model')]
from config import settings
from common import HERE as TRAIN_ROOT,LABEL_SETS,DOC_TYPE_TO_MODEL,read_rows,write_json,digest
from PIL import Image
from services.extractor import pipeline as pipelines
from services.extractor import layoutlm_extractor as local
from services.extractor.hosted_vlm import extract_hosted
from services.errors import HostedError
from services.ocr_service import ocr_document
from services.classifier.classifier_pipeline import classify_document
from services.validator.rules_engine import review_document
from utils.image_utils import normalize_image
from evaluate import evaluate,normalize
from metric_math import edit_distance
from resources import ResourceProbe,resource_summary

# Frozen protocol arms. Only extract_hosted is budgeted below, so newer arms that
# call other paid tiers (layoutlm_llm_vlm) are excluded rather than run unbudgeted.
PAPER_ARMS=('ocr_layoutlm','hosted_vlm','layoutlm_hosted_fallback')


def prepare(out,development_per_type=5,test_per_type=6):
    path=out/'manifest.json'
    if path.exists():
        existing=json.loads(path.read_text(encoding='utf-8'))
        if existing['counts_per_type']!={'development':development_per_type,'test':test_per_type}:raise ValueError('Cohort configuration changed; use a new run directory')
        return existing
    entries=[]
    for doc_type in LABEL_SETS:
        folder=TRAIN_ROOT/'data/synthetic'/doc_type.lower()
        for split,count in (('development',development_per_type),('test',test_per_type)):
            rows=read_rows(folder/(split+'.jsonl'))
            if count>len(rows):raise ValueError('Requested cohort larger than held-out split')
            selected=random.Random(42).sample(rows,count)
            for row in selected:
                image=normalize_image((TRAIN_ROOT/row['image']).read_bytes())
                image_path=out/'images'/(row['id']+'.jpg');image_path.parent.mkdir(parents=True,exist_ok=True);image_path.write_bytes(image)
                with Image.open(io.BytesIO(image)) as im:width,height=im.size
                boxes=[[[math.ceil(b[0]*width/1000),math.ceil(b[1]*height/1000)],
                        [math.ceil(b[2]*width/1000),math.ceil(b[1]*height/1000)],
                        [math.ceil(b[2]*width/1000),math.ceil(b[3]*height/1000)],
                        [math.ceil(b[0]*width/1000),math.ceil(b[3]*height/1000)]] for b in row['boxes']]
                exact={'full_text':' '.join(row['words']),'words':[{'text':word,'bounding_box':box,'confidence':1.0} for word,box in zip(row['words'],boxes)]}
                exact_path=out/'ocr'/(row['id']+'.exact.json');write_json(exact_path,exact)
                entries.append({'id':row['id'],'doc_type':doc_type,'split':split,'group':row['group'],
                    'image':image_path.relative_to(out).as_posix(),'sha256':hashlib.sha256(image).hexdigest(),
                    'fields':row['fields'],'exact_ocr':exact_path.relative_to(out).as_posix(),
                    'exact_ocr_sha256':digest(exact_path),
                    'annotation_source':'synthetic_generator_programmatic_truth','source_split_sha256':digest(folder/(split+'.jsonl'))})
    manifest={'version':'paper-synthetic-pilot-v1','selection_seed':42,'selected_before_inference':True,
              'cohort':'synthetic_held_out_parametric_families_not_real_msme','documents':entries,
              'counts_per_type':{'development':development_per_type,'test':test_per_type},
              'limitations':['Parametric layout families; not independent real vendors','Oracle document type supplied to extraction; classification scored separately']}
    write_json(path,manifest)
    return manifest


def ocr_metrics(reference,prediction):
    def norm(text):return ' '.join(unicodedata.normalize('NFKC',text).split())
    reference,prediction=norm(reference),norm(prediction)
    return {'character_edits':edit_distance(reference,prediction),'reference_characters':len(reference),
            'word_edits':edit_distance(reference.split(),prediction.split()),'reference_words':len(reference.split()),
            'normalization':'Unicode NFKC + whitespace collapse, case-sensitive; generator word order'}


def calibrate(entries,results):
    lookup={r['id']:r for r in results};curves=[]
    for threshold in (25,50,60,75,85,90,95,99):
        tp=fp=fn=reviewed=0
        for entry in entries:
            run=lookup[entry['id']]['pipelines']['ocr_layoutlm']
            fields={f['key']:f.get('value') for f in run.get('fields',[])}
            incorrect=bool(run.get('error') or run.get('metadata',{}).get('degraded')) or any(normalize(k,v)!=normalize(k,fields.get(k)) for k,v in entry['fields'].items())
            flag=bool(run.get('error')) or review_document(entry['doc_type'],run.get('fields',[]),'validation_confidence_review',run.get('metadata',{}).get('operational_reasons',[]),threshold=threshold)['review_required']
            tp+=flag and incorrect;fp+=flag and not incorrect;fn+=incorrect and not flag;reviewed+=flag
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
        curves.append({'threshold':threshold,'tp':tp,'fp':fp,'fn':fn,'reviewed':reviewed,'detection_f1':f1,
                       'objective':(f1 if f1 is not None else 0)-.05*reviewed/max(1,len(entries))})
    errors=curves[0]['tp']+curves[0]['fn']
    if errors:
        choice=max(curves,key=lambda row:(row['objective'],-row['threshold']))
        review=fallback=choice['threshold'];status='selected_on_production_OCR_synthetic_development'
    else:
        review=settings.REVIEW_THRESHOLD;fallback=settings.FALLBACK_THRESHOLD;status='insufficient_development_errors_defaults_retained'
    return {'version':'policy-v1','status':'frozen','selected_on':'development','review_threshold':review,'fallback_threshold':fallback,
            'selection_status':status,'selection_objective':'document detection F1 minus 0.05*review rate; same selected confidence threshold for routing and C',
            'development_documents':len(entries),'development_incorrect':errors,'curves':curves,
            'limitations':'Synthetic-only calibration; not calibrated on real Indian MSME data; not a probability calibration model'}


def run(args):
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=prepare(out,args.development_per_type,args.test_per_type)
    settings.DATA_DIR=str(out/'isolated_data');settings.LAYOUTLM_DEVICE='cuda'
    settings.HOSTED_VLM_CACHE=False
    settings.HOSTED_VLM_MIN_INTERVAL_SECONDS=20
    settings.HOSTED_VLM_MAX_ATTEMPTS=2
    import torch
    torch.set_num_threads(4)
    if not torch.cuda.is_available():raise RuntimeError('CUDA required for this declared benchmark')
    ledger_path=out/'api_ledger.json';ledger=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {'google_requests':0,'hosted_attempts':0,'max_calls':args.max_calls}
    def persist_ledger():write_json(ledger_path,ledger)
    original=pipelines.extract_hosted
    def bounded(*a,**kw):
        if ledger['google_requests']+ledger['hosted_attempts']+settings.HOSTED_VLM_MAX_ATTEMPTS>args.max_calls:
            raise HostedError('Declared benchmark call budget exhausted',kind='budget')
        try:
            result=extract_hosted(*a,**{**kw,'allow_network':args.live})
            ledger['hosted_attempts']+=result['metadata']['attempts'];persist_ledger();return result
        except HostedError as exc:
            ledger['hosted_attempts']+=exc.attempts;persist_ledger();raise
    pipelines.extract_hosted=bounded
    source={str(p.relative_to(ROOT)):digest(p) for base in (ROOT/'backend',ROOT/'research') for p in base.rglob('*.py') if 'data' not in p.parts and '__pycache__' not in p.parts}
    protocol={'created_at':datetime.now(timezone.utc).isoformat(),'manifest_sha256':digest(out/'manifest.json'),
        'model':settings.HOSTED_VLM_MODEL,'provider':'groq','temperature':0,'prompt_version':__import__('services.extractor.hosted_vlm',fromlist=['PROMPT_VERSION']).PROMPT_VERSION,
        'source_code_sha256':source,'torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),'device':'cuda',
        'cache_policy':'No hosted result cache; independent requests for P2 and routed P3; saved raw predictions reused only for resume',
        'latency_policy':'Warm local models; cold load/hash measured separately; both raw wall time and pacing-excluded times retained',
        'max_calls':args.max_calls,'real_msme_training_or_test_labels_used':False}
    protocol['environment']={'python':sys.version,'platform':platform.platform(),'packages':{name:importlib.metadata.version(name) for name in ('torch','transformers','Pillow','httpx','numpy','psutil','fastapi','scikit-learn','matplotlib')}}
    protocol['hardware']={'cpu':platform.processor(),'torch_threads':torch.get_num_threads(),'gpu_total_memory_bytes':torch.cuda.get_device_properties(0).total_memory}
    protocol_path=out/'protocol.json'
    if protocol_path.exists():
        previous=json.loads(protocol_path.read_text(encoding='utf-8'))
        for key in ('manifest_sha256','source_code_sha256','model','max_calls'):
            if previous[key]!=protocol[key]:raise ValueError('Resume protocol changed: '+key+'; start a distinct run')
    else:write_json(protocol_path,protocol)
    predictions=[];ocr_rows=[];classifications=[]
    cold_loads=json.loads((out/'cold_model_loads.json').read_text(encoding='utf-8')) if (out/'cold_model_loads.json').exists() else []
    for split in ('development','test'):
        entries=[e for e in manifest['documents'] if e['split']==split]
        for index,entry in enumerate(entries):
            raw_path=out/'raw'/(entry['id']+'.json')
            if raw_path.exists():
                row=json.loads(raw_path.read_text(encoding='utf-8'))
                predictions.append(row);ocr_rows.append(row['ocr_metrics']);classifications.append(row['classification']);continue
            image=(out/entry['image']).read_bytes()
            if hashlib.sha256(image).hexdigest()!=entry['sha256'] or digest(out/entry['exact_ocr'])!=entry['exact_ocr_sha256']:
                raise ValueError('Cohort input changed after selection')
            with Image.open(io.BytesIO(image)) as im:width,height=im.size
            exact=json.loads((out/entry['exact_ocr']).read_text(encoding='utf-8'))
            ocr_path=out/'ocr'/(entry['id']+'.google.json')
            ocr_error=None
            if ocr_path.exists():cached=json.loads(ocr_path.read_text(encoding='utf-8'));ocr=cached['ocr'];ocr_ms=cached['elapsed_ms']
            else:
                started=time.perf_counter()
                try:
                    if not args.live or ledger['google_requests']+ledger['hosted_attempts']+settings.GOOGLE_VISION_MAX_ATTEMPTS>args.max_calls:raise ValueError('Live OCR disabled or call budget exhausted')
                    ledger['google_requests']+=1;persist_ledger()
                    ocr=asyncio.run(ocr_document(image)).model_dump();ocr_ms=(time.perf_counter()-started)*1000
                    ledger['google_requests']+=ocr.get('metadata',{}).get('attempts',1)-1;persist_ledger()
                    write_json(ocr_path,{'ocr':ocr,'elapsed_ms':ocr_ms,'image_sha256':entry['sha256']})
                except Exception as exc:
                    if hasattr(exc,'headers') and exc.headers and 'X-OCR-Attempts' in exc.headers:
                        ledger['google_requests']+=int(exc.headers['X-OCR-Attempts'])-1;persist_ledger()
                    ocr=None;ocr_ms=(time.perf_counter()-started)*1000;ocr_error=type(exc).__name__
            measured_ocr=ocr_metrics(exact['full_text'],ocr['full_text']) if ocr else {'error':ocr_error,'character_edits':None,'reference_characters':None,'word_edits':None,'reference_words':None}
            measured_ocr.update(id=entry['id'],split=split,elapsed_ms=ocr_ms)
            measured_ocr['empty_result']=ocr is not None and not bool(ocr['words'] and ocr['full_text'].strip())
            measured_ocr['mean_provider_word_confidence']=sum(w['confidence'] for w in ocr['words'])/len(ocr['words']) if ocr and ocr['words'] else None
            started=time.perf_counter()
            try:
                classified=classify_document(ocr['full_text']) if ocr else None
                classification={'id':entry['id'],'split':split,'expected':entry['doc_type'],'predicted':classified['type'] if classified else None,
                                'level':classified['classifier_level'] if classified else None,'elapsed_ms':(time.perf_counter()-started)*1000}
            except Exception as exc:classification={'id':entry['id'],'split':split,'expected':entry['doc_type'],'predicted':None,'error':type(exc).__name__,'elapsed_ms':(time.perf_counter()-started)*1000}
            # Prime weights and hash independently of timed requests, once per type transition.
            if f"doc::{entry['doc_type']}" not in local._models:
                with ResourceProbe() as cold:
                    local._get_model_for_doc_type(entry['doc_type'])
                    weights=Path(settings.LAYOUTLM_MODEL_ROOT)/DOC_TYPE_TO_MODEL[entry['doc_type']]/'model.safetensors'
                    local._weight_hash(str(weights),weights.stat().st_mtime_ns)
                cold_loads.append({'doc_type':entry['doc_type'],'split':split,**cold.result})
                write_json(out/'cold_model_loads.json',cold_loads)
            row={'id':entry['id'],'split':split,'image_sha256':entry['sha256'],'pipelines':{},'ocr_metrics':measured_ocr,'classification':classification}
            names=['ocr_layoutlm'] if split=='development' else PAPER_ARMS
            for name in names:
                started=time.perf_counter()
                try:
                    with ResourceProbe() as probe:
                        if name!='hosted_vlm' and ocr is None:raise ValueError('OCR unavailable: '+str(ocr_error))
                        result=pipelines.run_pipeline(pipeline=name,image_bytes=image,ocr_result=ocr,doc_type=entry['doc_type'],image_width=width,image_height=height,
                            fallback_threshold=policy['fallback_threshold'] if split=='test' else settings.FALLBACK_THRESHOLD,
                            review_threshold=policy['review_threshold'] if split=='test' else settings.REVIEW_THRESHOLD,allow_network=args.live)
                    metadata=result['metadata'];metadata['resources']=probe.result
                    metadata['ocr_logical_calls']=0 if name=='hosted_vlm' else 1
                    metadata['shared_ocr_elapsed_ms']=0 if name=='hosted_vlm' else ocr_ms
                    metadata['shared_classification_elapsed_ms']=0 if name=='hosted_vlm' else classification['elapsed_ms']
                    metadata['end_to_end_client_ms']=metadata['elapsed_ms']+metadata['shared_ocr_elapsed_ms']+metadata['shared_classification_elapsed_ms']
                    metadata['client_ms_excluding_pacing']=metadata['end_to_end_client_ms']-metadata['hosted'].get('pacing_wait_seconds',0)*1000
                    row['pipelines'][name]=result
                except Exception as exc:
                    row['pipelines'][name]={'error':str(exc) if isinstance(exc,(HostedError,ValueError)) else type(exc).__name__,'fields':[],
                        'metadata':{'elapsed_ms':(time.perf_counter()-started)*1000,'hosted':{'attempts':getattr(exc,'attempts',0),'logical_calls':int(name!='ocr_layoutlm')},'operational_reasons':[type(exc).__name__]}}
            predictions.append(row);ocr_rows.append(measured_ocr);classifications.append(classification)
            write_json(raw_path,row)
            write_json(out/'progress.json',{'status':'running','phase':split,'completed_documents':index+1,'total_documents':len(entries),'api_ledger':ledger,'updated_at':datetime.now(timezone.utc).isoformat()})
            print(split,entry['id'],flush=True)
        if split=='development':
            policy=calibrate(entries,[r for r in predictions if r['split']=='development'])
            write_json(out/'policy.json',policy)
            frozen=json.loads(protocol_path.read_text(encoding='utf-8'));frozen.update(policy_sha256=digest(out/'policy.json'),policy_frozen_at=datetime.now(timezone.utc).isoformat());write_json(protocol_path,frozen)
    pipelines.extract_hosted=original
    test_entries=[e for e in manifest['documents'] if e['split']=='test'];test_predictions=[r for r in predictions if r['split']=='test']
    report=evaluate(test_entries,test_predictions,policy['review_threshold'])
    report['review_curves']={str(t):evaluate(test_entries,test_predictions,t)['pipelines'] for t in (25,50,60,75,85,90,95,99)}
    import copy
    routing_curves=[]
    for threshold in (25,50,60,75,85,90,95,99):
        scenarios=[];routed=0
        for entry,row in zip(test_entries,test_predictions):
            arms=copy.deepcopy(row['pipelines']);baseline=arms['ocr_layoutlm'];hosted=arms['hosted_vlm']
            reasons=pipelines.routing_reasons(entry['doc_type'],baseline.get('fields',[]),threshold) if not baseline.get('error') else ['Local failure']
            fields=baseline.get('fields',[]);conflicts=[];degraded=bool(baseline.get('error'))
            if reasons:
                routed+=1
                if hosted.get('error'):degraded=True
                elif fields:fields,_,conflicts=pipelines.resolve_candidates(entry['doc_type'],fields,hosted['fields'],threshold)
            arms['layoutlm_hosted_fallback']={'fields':fields,'metadata':{'routing_reasons':reasons,'conflicts':conflicts,'degraded':degraded}}
            scenarios.append({'id':entry['id'],'pipelines':arms})
        replay=evaluate(test_entries,scenarios,policy['review_threshold'])['pipelines']['layoutlm_hosted_fallback']
        routing_curves.append({'threshold':threshold,'counterfactual_logical_calls':routed,'routing_rate':routed/len(test_entries),
                               'micro_field_f1':replay['micro_field_f1'],'complete_document_accuracy':replay['complete_document_accuracy']})
    report['routing_replay']={'scope':'Counterfactual fixed P1/P2 candidate replay, not new hybrid inference, charges or latency; test sensitivity analysis never selects the frozen policy','points':routing_curves}
    for name,metrics in report['pipelines'].items():
        runs=[r['pipelines'][name] for r in test_predictions]
        metrics['resources']=resource_summary(runs)
        for key in ('end_to_end_client_ms','client_ms_excluding_pacing'):
            values=sorted(r['metadata'][key] for r in runs if key in r.get('metadata',{}))
            metrics[key]={'median':__import__('statistics').median(values) if values else None,'p95':values[max(0,math.ceil(.95*len(values))-1)] if values else None,'samples':len(values)}
    test_ocr=[r for r in ocr_rows if r['split']=='test' and r.get('character_edits') is not None]
    ref_chars=sum(r['reference_characters'] for r in test_ocr);ref_words=sum(r['reference_words'] for r in test_ocr)
    report['ocr']={'documents':len(test_ocr),'failures':len(test_entries)-len(test_ocr),'cer':sum(r['character_edits'] for r in test_ocr)/ref_chars if ref_chars else None,
                   'wer':sum(r['word_edits'] for r in test_ocr)/ref_words if ref_words else None,'reference_characters':ref_chars,'reference_words':ref_words,
                   'normalization':'Unicode NFKC + whitespace collapse; case-sensitive; generator word order, including column-order differences'}
    report['ocr']['empty_results']=sum(r.get('empty_result',False) for r in test_ocr)
    from sklearn.metrics import precision_recall_fscore_support,confusion_matrix
    labels=list(LABEL_SETS);test_class=[r for r in classifications if r['split']=='test']
    actual=[r['expected'] for r in test_class];predicted=[r.get('predicted') or 'UNAVAILABLE' for r in test_class]
    precision,recall,f1,_=precision_recall_fscore_support(actual,predicted,labels=labels,average='macro',zero_division=0)
    report['classification']={'documents':len(actual),'accuracy':sum(a==b for a,b in zip(actual,predicted))/len(actual),'macro_precision':float(precision),
        'macro_recall':float(recall),'macro_f1':float(f1),'labels':labels+['UNAVAILABLE'],'confusion_matrix':confusion_matrix(actual,predicted,labels=labels+['UNAVAILABLE']).tolist(),
        'levels':{level:sum(r.get('level')==level for r in test_class) for level in ('L1','L2','L3')},'unavailable':predicted.count('UNAVAILABLE')}
    report['classification']['conditional_level_accuracy']={level:(sum(r['expected']==r.get('predicted') for r in test_class if r.get('level')==level)/sum(r.get('level')==level for r in test_class)) if any(r.get('level')==level for r in test_class) else None for level in ('L1','L2','L3')}
    report.update(cohort=manifest['cohort'],documents=len(test_entries),policy=policy,api_ledger=ledger,
                  raw_predictions='raw/',metric_scope='Synthetic held-out production-OCR pilot; not final Indian MSME results')
    write_json(out/'pipeline_report.json',report);write_json(out/'ocr_measurements.json',ocr_rows);write_json(out/'classification_measurements.json',classifications)
    write_json(out/'progress.json',{'status':'complete','phase':'complete','completed_documents':len(test_entries),'api_ledger':ledger,'finished_at':datetime.now(timezone.utc).isoformat()})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--live',action='store_true');parser.add_argument('--max-calls',type=int,default=220)
    parser.add_argument('--development-per-type',type=int,default=5);parser.add_argument('--test-per-type',type=int,default=6)
    run(parser.parse_args())
