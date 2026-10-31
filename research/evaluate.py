"""Pure scoring/review replay. Never contacts a model or changes predictions."""
import json
import re
import random
import statistics
from collections import defaultdict
from decimal import Decimal
from services.field_contract import keys_for, AMOUNT_KEYS
from services.validator.rules_engine import review_document, parse_amount, parse_date
from metric_math import wilson, calibration

def normalize(key, value):
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    if key in AMOUNT_KEYS:
        amount = parse_amount(value)
        return str(amount.normalize()) if amount is not None else value
    if key.endswith("_date") or key == "due_date":
        parsed = parse_date(value)
        return parsed.isoformat() if parsed else value.casefold()
    if key.endswith("gstin"):
        return re.sub(r"\s", "", value).upper()
    return re.sub(r"\s+", " ", value).casefold()

def ratio(a, b):
    return a / b if b else None

def evaluate(entries, predictions, threshold=75):
    if len({r['id'] for r in predictions}) != len(predictions):
        raise ValueError("Duplicate prediction IDs")
    if len({e['id'] for e in entries}) != len(entries):
        raise ValueError("Duplicate ground-truth IDs")
    by_id = {r["id"]:r for r in predictions}
    groups = {}
    for pipeline in ("ocr_layoutlm", "hosted_vlm", "layoutlm_hosted_fallback"):
        results = []
        fields = defaultdict(lambda: {"tp":0,"fp":0,"fn":0,"present":0,"absent":0,"correct_absent":0})
        failure_count = 0
        observations=[]
        missing, wrong, extra = 0, 0, 0
        for entry in entries:
            run = by_id.get(entry["id"], {}).get("pipelines", {}).get(pipeline)
            if run is None:
                raise ValueError(f"Missing prediction for {entry['id']} / {pipeline}; incomplete arms cannot be scored as complete.")
            failure = bool(run.get("error") or run.get("metadata", {}).get("degraded"))
            failure_count += failure
            predicted = {f["key"]:f.get("value") for f in run.get("fields", [])}
            errors = set()
            for key in keys_for(entry["doc_type"]):
                gt = normalize(key, entry["fields"][key])
                pred = normalize(key, predicted.get(key))
                field=next((f for f in run.get('fields',[]) if f['key']==key),{})
                if pred is not None and field.get('source')=='layoutlm' and field.get('confidence') is not None:
                    observations.append((float(field['confidence'])/100,int(gt==pred)))
                counter = fields[key]
                if gt is None:
                    counter["absent"] += 1
                    counter["correct_absent"] += pred is None
                else:
                    counter["present"] += 1
                if gt is not None and gt == pred:
                    counter["tp"] += 1
                elif gt != pred:
                    errors.add(key)
                    if gt is not None:
                        counter["fn"] += 1
                    if pred is not None:
                        counter["fp"] += 1
                    missing += gt is not None and pred is None
                    wrong += gt is not None and pred is not None
                    extra += gt is None and pred is not None
            results.append({"entry":entry, "run":run, "incorrect":bool(errors) or failure, "error_fields":errors})
        policies = {}
        for policy in ("extraction_only","validation_review","validation_confidence_review"):
            N=len(results); E=sum(r["incorrect"] for r in results)
            flagged=detected=false_flags=field_hits=field_flags=0
            for row in results:
                run=row["run"]; metadata=run.get("metadata",{})
                operational=metadata.get("operational_reasons", []) + ([run["error"]] if run.get("error") else [])
                decision = review_document(row["entry"]["doc_type"], run.get("fields",[]),policy,
                    operational, metadata.get("conflicts",[]),threshold)
                # A is the no-detector comparator; report failures separately.
                review = decision["review_required"] if policy!="extraction_only" else False
                keys=set(decision["flagged_fields"]) if policy!="extraction_only" else set()
                flagged+=review
                detected+=review and row["incorrect"]
                false_flags+=review and not row["incorrect"]
                field_hits+=len(keys & row["error_fields"]); field_flags+=len(keys)
            silent=E-detected
            policies[policy]={"review_rate":ratio(flagged,N),"coverage":ratio(N-flagged,N),
                "detection_precision":ratio(detected,flagged),"detection_recall":ratio(detected,E),
                "silent_error_rate":ratio(silent,N),"accepted_error_rate":ratio(silent,N-flagged),
                "unnecessary_review_rate":ratio(false_flags,N-E),
                "field_detection_precision":ratio(field_hits,field_flags),
                "field_detection_recall":ratio(field_hits,sum(len(r["error_fields"]) for r in results)),
                "reviewed":flagged,"incorrect_flagged":detected,
                "confusion":{"tp":detected,"fp":false_flags,"fn":silent,"tn":N-E-false_flags},
                "specificity":ratio(N-E-false_flags,N-E),"false_positive_rate":ratio(false_flags,N-E),
                "accepted_accuracy":ratio(N-flagged-silent,N-flagged),
                "scope":"LayoutLM confidence only; hosted confidence unavailable" if policy=="validation_confidence_review" else "common policy"}
        for values in fields.values():
            values["precision"]=ratio(values["tp"],values["tp"]+values["fp"])
            values["recall"]=ratio(values["tp"],values["tp"]+values["fn"])
            values["f1"]=ratio(2*values["tp"],2*values["tp"]+values["fp"]+values["fn"])
        times=[r["run"]["metadata"]["elapsed_ms"] for r in results if "elapsed_ms" in r["run"].get("metadata",{})]
        successful_times=[r['run']['metadata']['elapsed_ms'] for r in results if not (r['run'].get('error') or r['run'].get('metadata',{}).get('degraded')) and 'elapsed_ms' in r['run'].get('metadata',{})]
        attempts=sum(r["run"].get("metadata",{}).get("hosted",{}).get("attempts",0) for r in results)
        total_tp=sum(v['tp'] for v in fields.values());total_fp=sum(v['fp'] for v in fields.values());total_fn=sum(v['fn'] for v in fields.values())
        total_fields=sum(v['present']+v['absent'] for v in fields.values())
        correct_absent=sum(v['correct_absent'] for v in fields.values())
        usage=defaultdict(int)
        for row in results:
            for key,value in row["run"].get("metadata",{}).get("hosted",{}).get("usage",{}).items():
                if isinstance(value,(int,float)): usage[key]+=value
        groups[pipeline]={"documents":len(results),"failures":failure_count,
            "failure_rate":ratio(failure_count,len(results)),
            "micro_precision":ratio(total_tp,total_tp+total_fp),"micro_recall":ratio(total_tp,total_tp+total_fn),
            "micro_field_f1":ratio(2*total_tp,2*total_tp+total_fp+total_fn),
            "present_field_accuracy":ratio(total_tp,total_tp+total_fn),
            "all_field_accuracy":ratio(total_tp+correct_absent,total_fields),
            "absent_field_specificity":ratio(correct_absent,sum(v['absent'] for v in fields.values())),
            "extra_absent_field_rate":ratio(extra,total_tp+total_fp),
            "calibration":calibration(observations),
            "complete_document_accuracy":ratio(sum(not r["incorrect"] for r in results),len(results)),
            "complete_document_accuracy_ci95_wilson":wilson(sum(not r['incorrect'] for r in results),len(results)),
            "macro_field_f1":statistics.mean([v["f1"] for v in fields.values() if v["f1"] is not None]) if fields else None,
            "macro_field_precision":statistics.mean([v['precision'] for v in fields.values() if v['precision'] is not None]) if any(v['precision'] is not None for v in fields.values()) else None,
            "macro_field_recall":statistics.mean([v['recall'] for v in fields.values() if v['recall'] is not None]) if any(v['recall'] is not None for v in fields.values()) else None,
            "macro_f1_defined_fields":sum(v['f1'] is not None for v in fields.values()),
            "fields":dict(fields),"errors":{"missing":missing,"wrong":wrong,"extra":extra},"review":policies,
            "hosted_attempts":attempts, "usage":dict(usage),
            "logical_hosted_calls":sum(r['run'].get('metadata',{}).get('hosted',{}).get('logical_calls',0) for r in results),
            "hosted_cache_hits":sum(bool(r['run'].get('metadata',{}).get('hosted',{}).get('cached')) for r in results),
            "retry_attempts":sum(max(0,r['run'].get('metadata',{}).get('hosted',{}).get('attempts',0)-1) for r in results),
            "fallback_rate":ratio(sum(bool(r['run'].get('metadata',{}).get('routing_reasons')) for r in results),len(results)),
            "fallback_documents":sum(bool(r["run"].get("metadata",{}).get("routing_reasons")) for r in results),
            "median_ms":statistics.median(times) if times else None,
            "p95_ms":sorted(times)[max(0,int(len(times)*.95+.999)-1)] if times else None,
            "latency_samples":len(times),
            "latency_scope":"All timed attempts including failures; successful-only latency is separate",
            "median_successful_ms":statistics.median(successful_times) if successful_times else None,
            "successful_latency_samples":len(successful_times),
            "cost_usd":None,"cost_status":"Not measured: requires provider account charges or explicitly dated price estimates",
            "remote_provider_memory_bytes":None,"remote_memory_status":"Not observable from this client",
            "human_time_saved_seconds":None,"human_time_status":"Requires a controlled human study"}
    # Paired bootstrap, document is the unit. Deterministic seed for reproducibility.
    rng=random.Random(42)
    accuracy={p:[not(bool(by_id[e["id"]]["pipelines"][p].get("error")) or
        bool(by_id[e["id"]]["pipelines"][p].get("metadata",{}).get("degraded")) or
        any(normalize(k,e["fields"][k])!=normalize(k,{f["key"]:f.get("value") for f in by_id[e["id"]]["pipelines"][p].get("fields",[])}.get(k)) for k in keys_for(e["doc_type"]))) for e in entries] for p in groups}
    paired={}
    paired_groups={}
    if entries:
        for other in ("ocr_layoutlm","hosted_vlm"):
            deltas=[]
            for _ in range(1000):
                indices=[rng.randrange(len(entries)) for _ in entries]
                deltas.append(statistics.mean(int(accuracy["layoutlm_hosted_fallback"][i])-int(accuracy[other][i]) for i in indices))
            deltas.sort()
            paired["hybrid_minus_"+other]={"document_accuracy_difference_ci95":[deltas[25],deltas[974]],"unit":"document","bootstrap_seed":42}
            clusters=defaultdict(list)
            for i,entry in enumerate(entries):clusters[entry.get('template_group') or entry.get('group') or entry['id']].append(i)
            keys=list(clusters);cluster_deltas=[]
            for _ in range(1000):
                indices=[i for _ in keys for i in clusters[rng.choice(keys)]]
                cluster_deltas.append(statistics.mean(int(accuracy['layoutlm_hosted_fallback'][i])-int(accuracy[other][i]) for i in indices))
            cluster_deltas.sort()
            paired_groups['hybrid_minus_'+other]={'document_accuracy_difference_ci95':[cluster_deltas[25],cluster_deltas[974]],'unit':'template/group cluster','clusters':len(keys),'bootstrap_seed':42}
    return {"pipelines":groups,"paired":paired,"paired_cluster_bootstrap":paired_groups,"review_threshold":threshold,"notes":["Raw extraction scores are independent of A/B/C review replay.","Free-tier allowance is not a zero deployment-cost claim.","C is source-limited; use validation_review for common cross-pipeline comparison."]}
