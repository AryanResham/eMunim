"""Single-stage CUDA-only LayoutLMv3 trainer with streaming images and resume."""
import argparse
import gc
import json
import math
import os
import time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
from seqeval.metrics import precision_score, recall_score, f1_score
from seqeval.scheme import IOB2
from common import HERE, ROOT, FUNSD_LABELS, SROIE_LABELS, LABEL_SETS, digest, read_rows, seed_all, validate_row, weight_file, write_json
from services.extractor.ocr_compounds import assemble_field_text


def enable_checkpointing(model):
    """LayoutLMv3 in Transformers 5.6 has no native checkpointing switch."""
    from torch.utils.checkpoint import checkpoint
    for layer in model.layoutlmv3.encoder.layer:
        original = layer.forward
        def forward(*args, _original=original, _layer=layer, **kwargs):
            if _layer.training and torch.is_grad_enabled():
                return checkpoint(_original,*args,use_reentrant=False,**kwargs)
            return _original(*args,**kwargs)
        layer.forward=forward


def reset_head(model):
    # LayoutLMv3 uses a Linear head for small schemas and an MLP for larger ones.
    for module in model.classifier.modules():
        if isinstance(module,torch.nn.Linear):
            module.reset_parameters()


class WindowDataset(Dataset):
    """Cache small token tensors, decode one image at a time; no corpus of pixel tensors."""
    def __init__(self, manifest, processor, labels, stride=96):
        self.rows = read_rows(manifest)
        self.processor = processor
        self.windows = []
        self.label_counts = Counter()
        label_ids = {label:i for i,label in enumerate(labels)}
        for row_index,row in enumerate(self.rows):
            validate_row(row,labels)
            self.label_counts.update(row["labels"])
            encoded = processor.tokenizer(row["words"],boxes=row["boxes"],word_labels=[label_ids[x] for x in row["labels"]],
                truncation=True,max_length=512,padding="max_length",stride=stride,return_overflowing_tokens=True,return_tensors="pt")
            covered = set()
            for window_index in range(len(encoded["input_ids"])):
                word_ids = encoded.word_ids(window_index)
                covered.update(w for w in word_ids if w is not None)
                values = {k:encoded[k][window_index] for k in ("input_ids","attention_mask","bbox","labels")}
                self.windows.append((row_index,values,word_ids))
            if covered != set(range(len(row["words"]))):
                raise ValueError("Token windows lost OCR words: "+row["id"])
        if not self.rows or not self.windows:
            raise ValueError("Dataset is empty")

    def __len__(self):
        return len(self.windows)

    def __getitem__(self,index):
        row_index,values,_ = self.windows[index]
        with Image.open(HERE/self.rows[row_index]["image"]) as image:
            pixels = self.processor.image_processor(image.convert("RGB"),return_tensors="pt")["pixel_values"][0]
        return {**values,"pixel_values":pixels},index


def entity_spans(words,tags):
    result=[];current=None;start=0;tokens=[]
    for i,(word,tag) in enumerate(zip(words,tags)):
        if tag.startswith("I-") and current==tag[2:]:
            tokens.append(word)
            continue
        if current is not None:
            result.append((current,start,i,assemble_field_text(current.lower(),tokens)))
        current=tag[2:] if tag.startswith("B-") else None
        start=i;tokens=[word] if current else []
    if current is not None:
        result.append((current,start,len(words),assemble_field_text(current.lower(),tokens)))
    return result


def evaluate(model,dataset,labels,device):
    model.eval()
    choices=[[None]*len(row["words"]) for row in dataset.rows]
    with torch.inference_mode():
        for item,index in DataLoader(dataset,batch_size=1,shuffle=False,num_workers=0):
            window_index=int(index[0])
            row_index,_,word_ids=dataset.windows[window_index]
            gold=item.pop("labels")[0]
            with torch.autocast("cuda",dtype=torch.float16):
                logits=model(**{k:v.to(device) for k,v in item.items()}).logits[0]
            probabilities=logits.float().softmax(-1).cpu()
            confidences,predictions=probabilities.max(-1)
            for token,wid in enumerate(word_ids):
                if wid is None or int(gold[token])==-100:
                    continue
                candidate=(float(confidences[token]),int(predictions[token]))
                if choices[row_index][wid] is None or candidate[0]>choices[row_index][wid][0]:
                    choices[row_index][wid]=candidate
    true=[row["labels"] for row in dataset.rows]
    predicted=[[labels[value[1]] if value is not None else "O" for value in row] for row in choices]
    metrics=dict(entity_precision=precision_score(true,predicted,mode="strict",scheme=IOB2,zero_division=0),
                 entity_recall=recall_score(true,predicted,mode="strict",scheme=IOB2,zero_division=0),
                 entity_f1=f1_score(true,predicted,mode="strict",scheme=IOB2,zero_division=0),
                 complete_document_accuracy=sum(entity_spans(r["words"],r["labels"])==entity_spans(r["words"],p) for r,p in zip(dataset.rows,predicted))/len(dataset.rows),
                 documents=len(dataset.rows),windows=len(dataset))
    if "fields" in dataset.rows[0]:
        import sys
        sys.path.insert(0,str(ROOT/"research"))
        from evaluate import normalize
        tp=fp=fn=complete=0
        for row,tags in zip(dataset.rows,predicted):
            fields={name.lower():text for name,_,_,text in entity_spans(row["words"],tags)}
            correct=True
            for key,value in row["fields"].items():
                expected,actual=normalize(key,value),normalize(key,fields.get(key))
                if expected is not None and expected==actual:
                    tp+=1
                elif expected!=actual:
                    fn+=expected is not None
                    fp+=actual is not None
                    correct=False
            complete+=correct
        metrics.update(field_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                       field_tp=tp,field_fp=fp,field_fn=fn,complete_document_accuracy=complete/len(dataset.rows))
    model.train()
    return metrics


def selection_score(metrics, requested="auto"):
    if requested == "auto":
        return metrics.get("field_f1", metrics["entity_f1"])
    if requested not in ("entity_f1", "field_f1"):
        raise ValueError("Unknown development selection metric")
    return metrics[requested]


def train(args):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required. CPU fallback is deliberately disabled.")
    torch.set_num_threads(4)
    seed_all(args.seed)
    device=torch.device("cuda:0")
    if args.stage=="funsd":
        labels=FUNSD_LABELS; folder=HERE/"data/public/funsd"
    elif args.stage=="sroie":
        labels=SROIE_LABELS; folder=HERE/"data/public/sroie"
    else:
        labels=LABEL_SETS[args.doc_type]; folder=HERE/"data/synthetic"/args.doc_type.lower()
    if args.data_dir:
        folder=Path(args.data_dir).resolve()
    output=Path(args.output).resolve()
    run_dir=HERE/"runs"/args.run_id/(args.stage+('-'+args.doc_type.lower() if args.doc_type else ''))
    run_dir.mkdir(parents=True,exist_ok=True)
    processor=LayoutLMv3Processor.from_pretrained(args.source,apply_ocr=False,local_files_only=True)
    processor.tokenizer.only_label_first_subword=True
    if args.keep_head:
        source_config=json.loads((Path(args.source)/"config.json").read_text(encoding="utf-8"))
        if [source_config["id2label"][str(i)] for i in range(len(labels))] != labels:
            raise ValueError("Cannot retain a head with a different label schema")
    model=LayoutLMv3ForTokenClassification.from_pretrained(args.source,local_files_only=True,
        num_labels=len(labels),id2label=dict(enumerate(labels)),label2id={v:k for k,v in enumerate(labels)},ignore_mismatched_sizes=True)
    # Label meanings can differ even when dimensions match. Always replace the task head.
    if args.keep_head:
        if [model.config.id2label[i] for i in range(len(labels))] != labels:
            raise ValueError("Cannot retain a head with a different label schema")
    else:
        reset_head(model)
    enable_checkpointing(model)
    model.to(device)
    model.train()
    train_data=WindowDataset(folder/"train.jsonl",processor,labels)
    dev_data=WindowDataset(folder/"development.jsonl",processor,labels)
    unsupported=[label for label in labels if label.startswith("B-") and train_data.label_counts[label]==0]
    if unsupported and not args.allow_missing_labels:
        raise ValueError("No training support for target labels: "+str(unsupported))
    write_json(run_dir/"dataset_audit.json",dict(train_documents=len(train_data.rows),train_windows=len(train_data),
        development_documents=len(dev_data.rows),development_windows=len(dev_data),label_counts=dict(train_data.label_counts),labels=labels,unsupported_labels=unsupported,
        train_sha256=digest(folder/"train.jsonl"),development_sha256=digest(folder/"development.jsonl")))
    provenance=dict(stage=args.stage,doc_type=args.doc_type,source=str(Path(args.source).resolve()),
        source_weights_sha256=digest(weight_file(args.source)),train_sha256=digest(folder/"train.jsonl"),
        development_sha256=digest(folder/"development.jsonl"),labels=labels,seed=args.seed,
        gpu=torch.cuda.get_device_name(0),cuda=torch.version.cuda,torch=torch.__version__,
        method="full_parameter_finetuning_fp16_gradient_checkpointing",keep_head=args.keep_head,epochs=args.epochs,learning_rate=args.learning_rate,
        gradient_accumulation=args.accumulation,stride=96,window_merge="maximum first-subtoken confidence",real_msme_used=False)
    if getattr(args,"selection_metric","auto") != "auto":
        provenance["selection_metric"] = args.selection_metric
    write_json(run_dir/"provenance.json",provenance)
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.learning_rate,weight_decay=.01,foreach=False)
    scaler=torch.amp.GradScaler("cuda")
    last=run_dir/"last.pt"
    start_epoch=0;best=-1.;bad_epochs=0;global_step=0;history=[]
    if last.exists():
        checkpoint=torch.load(last,map_location="cpu",weights_only=False)
        if checkpoint["provenance"]!=provenance:
            raise ValueError("Resume configuration/data/source changed; start a distinct run")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        start_epoch=checkpoint["epoch"]+1;best=checkpoint["best"];global_step=checkpoint["global_step"]
        history=checkpoint["history"];bad_epochs=checkpoint["bad_epochs"]
        del checkpoint
        gc.collect()
    peak=0.; sanity_losses=[]
    if start_epoch==0:
        # Tiny-set fit gate: use eight documents, with actual GPU optimizer steps.
        ids=[i for i,(r,_,_) in enumerate(train_data.windows) if r<min(8,len(train_data.rows))]
        for step in range(args.sanity_steps):
            item,_=train_data[ids[step%len(ids)]]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda",dtype=torch.float16):
                loss=model(**{k:v.unsqueeze(0).to(device) for k,v in item.items()}).loss
            if not torch.isfinite(loss):
                raise ValueError("Non-finite sanity loss")
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            scaler.step(optimizer);scaler.update()
            sanity_losses.append(float(loss.detach()))
            if step%5==0:
                print(json.dumps(dict(stage=args.stage,phase="cuda_sanity",step=step,loss=sanity_losses[-1],gpu=torch.cuda.get_device_name(0))),flush=True)
        if not sanity_losses or np.mean(sanity_losses[-5:])>=np.mean(sanity_losses[:5]):
            raise RuntimeError("Tiny-set loss did not improve; refusing the full run")
        gate=evaluate(model,WindowDatasetSubset(train_data,8),labels,device)
        write_json(run_dir/"sanity.json",dict(losses=sanity_losses,metrics=gate,peak_vram_gb=torch.cuda.max_memory_allocated()/2**30))
        if gate["entity_f1"]==0:
            raise RuntimeError("Tiny-set predictions are all-O/incorrect; refusing the full run")
        # Sanity examples are training data, but restore initialization before the actual experiment.
        del loss,model,optimizer,scaler
        gc.collect();torch.cuda.empty_cache()
        seed_all(args.seed)
        model=LayoutLMv3ForTokenClassification.from_pretrained(args.source,local_files_only=True,num_labels=len(labels),
            id2label=dict(enumerate(labels)),label2id={v:k for k,v in enumerate(labels)},ignore_mismatched_sizes=True)
        if not args.keep_head:
            reset_head(model)
        enable_checkpointing(model)
        model.to(device);model.train()
        optimizer=torch.optim.AdamW(model.parameters(),lr=args.learning_rate,weight_decay=.01,foreach=False)
        scaler=torch.amp.GradScaler("cuda")
    steps_per_epoch=math.ceil(len(train_data)/args.accumulation)
    total_steps=steps_per_epoch*args.epochs
    warmup=max(1,round(total_steps*.1))
    for epoch in range(start_epoch,args.epochs):
        loader=DataLoader(train_data,batch_size=1,shuffle=True,num_workers=0,
                          generator=torch.Generator().manual_seed(args.seed+epoch))
        optimizer.zero_grad(set_to_none=True)
        loss_sum=0.;started=time.time()
        for batch,(item,_) in enumerate(loader):
            group_size=min(args.accumulation,len(loader)-(batch//args.accumulation)*args.accumulation)
            with torch.autocast("cuda",dtype=torch.float16):
                loss=model(**{k:v.to(device) for k,v in item.items()}).loss
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss")
            loss_sum+=float(loss.detach())
            scaler.scale(loss/group_size).backward()
            if (batch+1)%args.accumulation==0 or batch+1==len(loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                multiplier=min(1.,(global_step+1)/warmup)*max(0.,(total_steps-global_step)/max(1,total_steps-warmup)) if global_step>=warmup else (global_step+1)/warmup
                for group in optimizer.param_groups:
                    group["lr"]=args.learning_rate*multiplier
                scaler.step(optimizer);scaler.update();optimizer.zero_grad(set_to_none=True)
                global_step+=1
            if batch%10==0:
                heartbeat=dict(status="running",stage=args.stage,doc_type=args.doc_type,epoch=epoch+1,
                    batch=batch+1,batches=len(loader),optimizer_steps=global_step,loss=float(loss.detach()),
                    elapsed_epoch_seconds=round(time.time()-started,1),peak_vram_gb=round(torch.cuda.max_memory_allocated()/2**30,3),updated_at=time.time())
                write_json(run_dir/"status.json",heartbeat)
                print(json.dumps(heartbeat),flush=True)
        metrics=evaluate(model,dev_data,labels,device)
        row=dict(epoch=epoch+1,training_loss=loss_sum/len(loader),seconds=time.time()-started,**metrics)
        history.append(row)
        score=selection_score(metrics,getattr(args,"selection_metric","auto"))
        if score>best:
            best=score;bad_epochs=0
            output.mkdir(parents=True,exist_ok=True)
            model.save_pretrained(output,safe_serialization=True)
            processor.save_pretrained(output)
            write_json(output/"training_provenance.json",{**provenance,"best_epoch":epoch+1,"development_metrics":metrics})
        else:
            bad_epochs+=1
        write_json(run_dir/"history.json",history)
        # State is resumable at epoch boundaries. Interrupted epochs repeat deterministically.
        state=dict(model=model.state_dict(),optimizer=optimizer.state_dict(),scaler=scaler.state_dict(),
            epoch=epoch,best=best,global_step=global_step,history=history,bad_epochs=bad_epochs,provenance=provenance)
        temporary=last.with_suffix(".partial")
        torch.save(state,temporary);temporary.replace(last)
        print(json.dumps(dict(stage=args.stage,phase="epoch_complete",**row)),flush=True)
        if bad_epochs>=2:
            break
    if best<=0:
        raise RuntimeError("No useful development extraction learned; refusing next transfer stage")
    summary=dict(status="complete",best_development_score=best,history=history,output=str(output),provenance=provenance)
    write_json(output/"training_summary.json",summary)
    write_json(run_dir/"status.json",dict(status="complete",stage=args.stage,doc_type=args.doc_type,updated_at=time.time()))


class WindowDatasetSubset(WindowDataset):
    def __init__(self,source,count):
        self.rows=source.rows[:count]
        self.processor=source.processor
        self.windows=[entry for entry in source.windows if entry[0]<count]


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["funsd","sroie","synthetic"],required=True)
    parser.add_argument("--doc-type",choices=list(LABEL_SETS))
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--epochs",type=int,default=5)
    parser.add_argument("--learning-rate",type=float,default=2e-5)
    parser.add_argument("--accumulation",type=int,default=8)
    parser.add_argument("--sanity-steps",type=int,default=80)
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--data-dir",help="Explicit prepared manifest directory")
    parser.add_argument("--allow-missing-labels",action="store_true",help="Record absent target fields in audit")
    parser.add_argument("--keep-head",action="store_true",help="Continue an existing model with the same labels")
    parser.add_argument("--selection-metric",choices=["auto","entity_f1","field_f1"],default="auto")
    args=parser.parse_args()
    train(args)
