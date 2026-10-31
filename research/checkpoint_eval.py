"""Evaluate trained checkpoints on untouched public/synthetic splits with raw predictions."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'layoutLM__model')]
import torch
from torch.utils.data import DataLoader
from transformers import LayoutLMv3Processor,LayoutLMv3ForTokenClassification
from common import HERE,FUNSD_LABELS,SROIE_LABELS,LABEL_SETS,DOC_TYPE_TO_MODEL,digest,write_json,write_rows,read_rows
from train_stage import WindowDataset,entity_spans
from resources import ResourceProbe
from evaluate import normalize
from seqeval.metrics import precision_score,recall_score,f1_score,classification_report
from seqeval.scheme import IOB2


def entity_report(truth,predicted):
    raw=classification_report(truth,predicted,mode='strict',scheme=IOB2,output_dict=True,zero_division=0)
    return {label:{key:int(value) if key=='support' else float(value) for key,value in row.items()} for label,row in raw.items()}


def independent_public_test(folder,out):
    """Hash rule is applied before scoring, never based on prediction quality."""
    seen={digest(HERE/row['image']) for split in ('train','development') for row in read_rows(folder/(split+'.jsonl'))}
    source=read_rows(folder/'test.jsonl');kept=[];excluded=[]
    for row in source:
        (excluded if digest(HERE/row['image']) in seen else kept).append(row)
    if not kept:raise ValueError('No independent public test documents remain')
    path=out/(folder.name+'-independent-test.jsonl');write_rows(path,kept)
    audit={'source_test_documents':len(source),'independent_test_documents':len(kept),'excluded_test_ids':[row['id'] for row in excluded],
           'exclusion_rule':'Exact image file SHA-256 matches public training or development; fixed before inference',
           'original_test_manifest_sha256':digest(folder/'test.jsonl'),'filtered_manifest_sha256':digest(path)}
    write_json(out/(folder.name+'-exclusions.json'),audit)
    return path,audit


def evaluate_checkpoint(folder,data,labels,out,device='cuda'):
    if device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    torch.set_num_threads(4)
    with ResourceProbe() as resources:
        load_started=time.perf_counter()
        processor=LayoutLMv3Processor.from_pretrained(folder,apply_ocr=False,local_files_only=True)
        model=LayoutLMv3ForTokenClassification.from_pretrained(folder,local_files_only=True).to(device).eval()
        load_ms=(time.perf_counter()-load_started)*1000
        assert [model.config.id2label[i] for i in range(len(labels))]==labels
        dataset=WindowDataset(data,processor,labels)
        choices=[[None]*len(row['words']) for row in dataset.rows]
        times=[]
        with torch.inference_mode():
            for item,index in DataLoader(dataset,batch_size=1,shuffle=False,num_workers=0):
                window=int(index[0]);row_index,_,word_ids=dataset.windows[window]
                gold=item.pop('labels')[0]
                if device=='cuda':torch.cuda.synchronize()
                started=time.perf_counter()
                with torch.autocast('cuda',dtype=torch.float16,enabled=device=='cuda'):
                    logits=model(**{k:v.to(device) for k,v in item.items()}).logits[0]
                confidence,prediction=[x.cpu() for x in logits.float().softmax(-1).max(-1)]
                times.append((time.perf_counter()-started)*1000)
                for token,wid in enumerate(word_ids):
                    if wid is None or int(gold[token])==-100:continue
                    candidate=(float(confidence[token]),int(prediction[token]))
                    if choices[row_index][wid] is None or candidate[0]>choices[row_index][wid][0]:choices[row_index][wid]=candidate
        records=[];truth=[];predicted=[];tp=fp=fn=correct_docs=correct_tokens=all_tokens=0
        per_field={label[2:]:{'present':0,'correct_present':0,'predicted_present':0,'tp':0,'fp':0,'fn':0} for label in labels if label.startswith('B-')}
        exact_field_documents=receipt_three_documents=0
        for row,values in zip(dataset.rows,choices):
            tags=[labels[v[1]] if v else 'O' for v in values]
            truth.append(row['labels']);predicted.append(tags)
            spans=entity_spans(row['words'],tags)
            gold_spans=entity_spans(row['words'],row['labels'])
            field_correct=True;receipt_three_correct=True
            for name,counter in per_field.items():
                expected=' '.join(text for label,_,_,text in gold_spans if label==name) or None
                actual=' '.join(text for label,_,_,text in spans if label==name) or None
                key={'COMPANY':'vendor_name','DATE':'invoice_date','TOTAL':'total_amount'}.get(name,name.lower())
                expected,actual=normalize(key,expected),normalize(key,actual)
                field_correct=field_correct and expected==actual
                if name in ('COMPANY','DATE','TOTAL'):receipt_three_correct=receipt_three_correct and expected==actual
                counter['present']+=expected is not None;counter['predicted_present']+=actual is not None
                if expected is not None and expected==actual:counter['correct_present']+=1;counter['tp']+=1
                elif expected!=actual:counter['fp']+=actual is not None;counter['fn']+=expected is not None
            exact_field_documents+=field_correct
            receipt_three_documents+=receipt_three_correct
            correct_tokens+=sum(a==b for a,b in zip(row['labels'],tags));all_tokens+=len(tags)
            record={'id':row['id'],'image':row['image'],'words':row['words'],'gold_tags':row['labels'],'predicted_tags':tags,
                    'confidences':[v[0] if v else None for v in values]}
            if 'fields' in row:
                fields={name.lower():text for name,_,_,text in spans}
                correct=True
                for key,value in row['fields'].items():
                    actual,expected=normalize(key,fields.get(key)),normalize(key,value)
                    if expected is not None and actual==expected:tp+=1
                    elif actual!=expected:
                        fp+=actual is not None;fn+=expected is not None;correct=False
                correct_docs+=correct
                record.update(gold_fields=row['fields'],predicted_fields=fields)
            else:correct_docs+=spans==entity_spans(row['words'],row['labels'])
            records.append(record)
    import statistics
    for counter in per_field.values():
        counter['exact_accuracy_when_present']=counter['correct_present']/counter['present'] if counter['present'] else None
        counter['precision']=counter['tp']/(counter['tp']+counter['fp']) if counter['tp']+counter['fp'] else None
        counter['recall']=counter['tp']/(counter['tp']+counter['fn']) if counter['tp']+counter['fn'] else None
        counter['f1']=2*counter['tp']/(2*counter['tp']+counter['fp']+counter['fn']) if 2*counter['tp']+counter['fp']+counter['fn'] else None
    metrics={'documents':len(records),'windows':len(dataset),'entity_precision':precision_score(truth,predicted,mode='strict',scheme=IOB2,zero_division=0),
             'entity_recall':recall_score(truth,predicted,mode='strict',scheme=IOB2,zero_division=0),'entity_f1':f1_score(truth,predicted,mode='strict',scheme=IOB2,zero_division=0),
             'token_accuracy':correct_tokens/all_tokens,'complete_document_accuracy':correct_docs/len(records),
             'field_micro_f1':2*tp/(2*tp+fp+fn) if tp+fp+fn else None,'model_load_ms':load_ms,
             'median_window_inference_ms':statistics.median(times),'p95_window_inference_ms':sorted(times)[max(0,__import__('math').ceil(len(times)*.95)-1)],
             'latency_scope':'forward/transfer/softmax per token window; excludes OCR, tokenization and human review',
             'device':device,'resources':resources.result,'weights_sha256':digest(Path(folder)/'model.safetensors'),
             'dataset_sha256':digest(data),'split':'test','not_training_or_development':True}
    metrics['per_entity_bio']=entity_report(truth,predicted)
    metrics['per_field_exact']=per_field
    metrics['field_exact_scope']='All spans of a label concatenated in document token order; FUNSD is form entity extraction, not accounting field extraction'
    metrics['token_accuracy_scope']='Original OCR words using first-subtoken labels; excludes special tokens and padding, not all BPE pieces'
    metrics['complete_labeled_text_accuracy']=exact_field_documents/len(records)
    if 'COMPANY' in per_field:
        metrics['receipt_vendor_date_total_exact_accuracy']=receipt_three_documents/len(records)
        metrics['receipt_all_four_fields_exact_accuracy']=exact_field_documents/len(records)
    write_rows(out.with_suffix('.predictions.jsonl'),records)
    write_json(out,metrics)
    del model,dataset,processor
    import gc
    gc.collect()
    if torch.cuda.is_available():torch.cuda.empty_cache()
    return metrics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    public={name:independent_public_test(HERE/'data/public'/name,args.out) for name in ('funsd','sroie')}
    jobs=[('funsd','layoutlm-funsd-trained',public['funsd'][0],FUNSD_LABELS),
          ('sroie','layoutlm-sroie-trained',public['sroie'][0],SROIE_LABELS)]
    jobs.extend((t,DOC_TYPE_TO_MODEL[t],HERE/'data/synthetic'/t.lower()/'test.jsonl',labels) for t,labels in LABEL_SETS.items())
    results={}
    for name,folder,data,labels in jobs:
        results[name]=evaluate_checkpoint(HERE/folder,data,labels,args.out/(name.lower()+'.json'))
        if name in public:
            results[name]['public_test_identity_audit']=public[name][1]
            write_json(args.out/(name+'.json'),results[name])
        write_json(args.out/'summary.json',results)
        print(name,results[name]['documents'],results[name]['entity_f1'],flush=True)


if __name__=='__main__':main()
