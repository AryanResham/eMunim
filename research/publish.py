"""Generate paper tables and figures only from persisted measured artifacts."""
import csv
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from services.storage import write_json

UNAVAILABLE=[
    {'metric':'Real Indian MSME extraction/reliability','reason':'34 imported images have zero independently verified annotations. No real-data accuracy reported.'},
    {'metric':'Actual monetary cost','reason':'Provider account billing/charge records were not supplied. Counts/tokens are measured; free quota is not a zero deployment-cost claim.'},
    {'metric':'Human correction time / time saved','reason':'No controlled human timing study or participant data.'},
    {'metric':'Remote VLM server memory','reason':'Not observable through the hosted API. Local client RSS is a different measurement.'},
    {'metric':'PostgreSQL verification','reason':'DATABASE_URL is absent and Docker daemon is not running. SQLite persistence is tested separately.'},
    {'metric':'Duplicate-detector accuracy','reason':'No verified duplicate/nonduplicate pair benchmark.'},
    {'metric':'Accounting-head classification','reason':'The app classifies document types; no chart-of-accounts model or ground truth.'},
]


def publish(folder,status='running'):
    checkpoints_path=folder/'checkpoints/summary.json'
    checkpoints=json.loads(checkpoints_path.read_text(encoding='utf-8')) if checkpoints_path.exists() else {}
    pipeline_path=folder/'pipelines/pipeline_report.json'
    measured=json.loads(pipeline_path.read_text(encoding='utf-8')) if pipeline_path.exists() else {}
    summary={'run_id':folder.name,'status':status,'cohort':measured.get('cohort','public_and_synthetic_held_out_only'),
             'documents':measured.get('documents'),'checkpoint_tests':checkpoints,'pipelines':measured.get('pipelines',{}),
             'ocr':measured.get('ocr'),'classification':measured.get('classification'),'policy':measured.get('policy'),
             'api_ledger':measured.get('api_ledger'),'paired':measured.get('paired'),
             'paired_cluster_bootstrap':measured.get('paired_cluster_bootstrap'),
             'routing_replay':measured.get('routing_replay'),
             'unavailable_metrics':UNAVAILABLE,'files':[],
             'limitations':['Synthetic generated layout families are not independent real business vendors.',
                            'Oracle document type is given to extraction; document classification is scored separately.',
                            'Model quality is not certified by consistency rules or provider confidence.',
                            'Warm pipeline timing is distinct from cold model loading and includes explicitly reported client pacing.',
                            'No model training or threshold tuning uses the Indian MSME final test set.']}
    audit_path=folder/'dataset_audit.json'
    if audit_path.exists():
        audits=json.loads(audit_path.read_text(encoding='utf-8'));summary['dataset_audit']=audits
        if any(not row['exact_split_audit_passed'] for row in audits.values()):
            summary['limitations'].append('The raw SROIE mirror has nine exact cross-split duplicate pairs. Public test scoring excludes seven images duplicated from training/development before inference (340 retained). Two historical train/development duplicate pairs remain a training-selection limitation; no old scores are rewritten.')
    lines=['# Measured eMunim benchmark report','',f'Run: `{folder.name}`; execution status: **{status}**.','',
           'All figures/tables below are generated from saved measurements. Real Indian MSME accuracy is unavailable.','',
           '## Held-out checkpoint tests','',
           '| Task | Documents | Entity F1 | Complete document accuracy |','|---|---:|---:|---:|']
    table=[]
    for name,m in checkpoints.items():
        lines.append(f"| {name} | {m['documents']} | {m['entity_f1']:.6f} | {m['complete_document_accuracy']:.6f} |")
        for metric in ('entity_precision','entity_recall','entity_f1','token_accuracy','complete_document_accuracy','complete_labeled_text_accuracy','receipt_vendor_date_total_exact_accuracy','receipt_all_four_fields_exact_accuracy','field_micro_f1','model_load_ms','median_window_inference_ms','p95_window_inference_ms'):
            table.append(['checkpoint',name,m['documents'],metric,m.get(metric)])
        for entity,values in m.get('per_field_exact',{}).items():
            for metric,result in values.items():table.append(['checkpoint_field',name+'/'+entity,m['documents'],metric,result])
    if measured:
        lines+=['','## Production-OCR three-pipeline pilot','',f"Cohort: {measured['cohort']}; N={measured['documents']}. Policy selection: {measured['policy']['selection_status']}.",'',
                '| Pipeline | Micro field F1 | Macro field F1 | Complete accuracy | Failures | Review rate B | Accepted error B |','|---|---:|---:|---:|---:|---:|---:|']
        def value(x):return 'undefined' if x is None else f'{x:.6f}' if isinstance(x,float) else str(x)
        for name,m in measured['pipelines'].items():
            review=m['review']['validation_review']
            lines.append(f"| {name} | {value(m['micro_field_f1'])} | {value(m['macro_field_f1'])} | {value(m['complete_document_accuracy'])} | {m['failures']} | {value(review['review_rate'])} | {value(review['accepted_error_rate'])} |")
            for metric in ('micro_precision','micro_recall','micro_field_f1','macro_field_f1','complete_document_accuracy','failure_rate','fallback_rate','hosted_attempts','logical_hosted_calls','hosted_cache_hits','retry_attempts','median_ms','p95_ms','extra_absent_field_rate'):
                table.append(['pipeline',name,m['documents'],metric,m.get(metric)])
            for policy,metrics in m['review'].items():
                for metric,result in metrics.items():
                    if isinstance(result,(int,float)) or result is None:table.append(['review',name+'/'+policy,m['documents'],metric,result])
            for metric,result in m['resources'].items():table.append(['local_resources',name,m['documents'],metric,result])
            for metric,result in m['calibration'].items():
                if isinstance(result,(int,float)) or result is None:table.append(['confidence',name,m['documents'],metric,result])
        lines+=['','Measured Google OCR and classification summaries:','', '```json',json.dumps({'ocr':measured['ocr'],'classification':measured['classification']},indent=2),'```',
                '', 'API usage is physical measured attempts and logical calls, not a fabricated dollar estimate. Failed attempts remain in the cohort. Pacing-excluded latency still includes real retries/network time.',
                '', 'Detailed per-field counts, A/B/C reliability, confidence bins, review curves, paired intervals and resource samples are in summary.json and the underlying pipeline_report.json.']
    lines+=['','## Missing evidence','']+[f"- **{item['metric']}:** {item['reason']}" for item in UNAVAILABLE]
    lines+=['','## Interpretation limits','']+['- '+item for item in summary['limitations']]
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    with (folder/'tables.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['cohort','task_or_pipeline','documents','metric','value']);writer.writerows(table)
    if measured:
        figures(folder,measured,checkpoints)
    summary['files']=['summary.json','report.md','tables.csv']+[p.name for p in sorted(folder.glob('figure_*.svg'))]
    write_json(folder/'summary.json',summary)
    return summary


def figures(folder,report,checkpoints):
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(folder/'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size':10,'figure.dpi':150,'savefig.bbox':'tight'})
    def save(fig,name):
        fig.tight_layout();fig.savefig(folder/('figure_'+name+'.svg'));fig.savefig(folder/('figure_'+name+'.png'));plt.close(fig)
    labels=['LayoutLM','Hosted VLM','Selective hybrid'];names=list(report['pipelines'])
    fig,ax=plt.subplots(figsize=(8,4));x=np.arange(3)
    for i,key in enumerate(('micro_field_f1','macro_field_f1','complete_document_accuracy')):
        values=[report['pipelines'][n][key] for n in names]
        ax.bar(x+(i-1)*.24,[v if v is not None else float('nan') for v in values],.24,label=key.replace('_',' '))
    ax.set_xticks(x,labels);ax.set_ylim(0,1.08);ax.set_ylabel('Score');ax.legend(fontsize=8);ax.set_title(f"Synthetic production-OCR pilot, N={report['documents']}");save(fig,'pipeline_quality')
    fig,ax=plt.subplots(figsize=(6,4))
    for name,label in zip(names,labels):
        points=[(v[name]['review']['validation_confidence_review']['coverage'],v[name]['review']['validation_confidence_review']['accepted_error_rate']) for v in report['review_curves'].values()]
        points=sorted((x,y) for x,y in points if x is not None and y is not None)
        if points:ax.plot([x for x,_ in points],[y for _,y in points],marker='o',label=label)
    ax.set_xlabel('Automatically accepted coverage');ax.set_ylabel('Error rate among accepted documents');ax.set_title('Review threshold replay; C uses local confidence only');ax.legend(fontsize=8);save(fig,'risk_coverage')
    fig,ax=plt.subplots(figsize=(7,4))
    public=[n for n in ('funsd','sroie') if n in checkpoints]
    ax.bar(public,[checkpoints[n]['entity_f1'] for n in public]);ax.set_ylim(0,1);ax.set_ylabel('Strict entity F1');ax.set_title('Different public tasks: scores are not a transfer-gain estimate');save(fig,'public_tasks')
    fig,ax=plt.subplots(figsize=(9,4))
    synthetic=[n for n in checkpoints if n not in ('funsd','sroie')]
    ax.bar([n.replace('_','\n') for n in synthetic],[checkpoints[n]['field_micro_f1'] if checkpoints[n]['field_micro_f1'] is not None else float('nan') for n in synthetic]);ax.set_ylim(0,1.08);ax.set_ylabel('Micro field F1');ax.set_title('Held-out exact-OCR synthetic checkpoint tests (150/type)');save(fig,'synthetic_types')
    fig,ax=plt.subplots(figsize=(6,4))
    ocr=report['ocr'];values=[ocr['cer'],ocr['wer']]
    ax.bar(['Character error rate','Word error rate'],[v if v is not None else float('nan') for v in values]);ax.set_ylabel('Normalized edit rate');ax.set_title('Google OCR vs generator transcription order');save(fig,'ocr_errors')
    fig,ax=plt.subplots(figsize=(8,6))
    classification=report['classification'];matrix=np.array(classification['confusion_matrix']);image=ax.imshow(matrix,cmap='Blues');fig.colorbar(image,ax=ax)
    ticks=[n.replace('_',' ') for n in classification['labels']];ax.set_xticks(range(len(ticks)),ticks,rotation=50,ha='right');ax.set_yticks(range(len(ticks)),ticks)
    for i in range(len(ticks)):
        for j in range(len(ticks)):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=8)
    ax.set_xlabel('Predicted');ax.set_ylabel('Ground truth');ax.set_title('Document classifier confusion counts');save(fig,'classification')
    fig,ax=plt.subplots(figsize=(7,4))
    for name,label in zip(names,labels):
        bins=[b for b in report['pipelines'][name]['calibration']['bins'] if b['count']]
        if bins:ax.plot([b['mean_confidence'] for b in bins],[b['accuracy'] for b in bins],marker='o',label=label)
    ax.plot([0,1],[0,1],'--',color='gray');ax.set_xlim(0,1);ax.set_ylim(0,1.05);ax.set_xlabel('Mean softmax confidence');ax.set_ylabel('Observed field correctness');ax.set_title('Populated LayoutLM fields only');ax.legend(fontsize=8);save(fig,'confidence')
    fig,ax=plt.subplots(figsize=(7,4))
    times=[report['pipelines'][n]['client_ms_excluding_pacing']['median'] for n in names]
    ax.bar(labels,[v/1000 if v is not None else float('nan') for v in times]);ax.set_ylabel('Client seconds per document');ax.set_title('Warm client median, excluding artificial request spacing');save(fig,'latency')
    fig,ax=plt.subplots(figsize=(7,4))
    points=report['routing_replay']['points']
    ax.plot([p['routing_rate'] for p in points],[p['micro_field_f1'] for p in points],marker='o')
    for point in points:ax.annotate(str(point['threshold']),(point['routing_rate'],point['micro_field_f1']),fontsize=8)
    ax.set_xlabel('Counterfactual routed-document fraction');ax.set_ylabel('Micro field F1');ax.set_title('Fixed-candidate routing replay; not measured billing or latency');save(fig,'routing_replay')
