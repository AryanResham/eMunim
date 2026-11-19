"""Supplemental scoring from rendered source lines, never inferred model labels.

Preserves the primary BIO-annotation scoring as a separate experimental result.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'research'),str(ROOT/'layoutLM__model')]
from train_msme import field_map
from services.field_contract import keys_for
from services.validator.rules_engine import parse_amount,parse_date
from services.storage import write_json

OUT=ROOT/'backend/data/synthetic_pipeline_sample_20261102_seed42'
SOURCE=ROOT/'indian_erp_doc_generator/indian_erp_doc_generator/msme_6000/annotations/test'
ARMS=['ocr_regex','ocr_layoutlm','hosted_vlm','layoutlm_hosted_fallback']

def norm(key,value):
    if value is None or not str(value).strip():return None
    value=str(value).strip()
    if 'amount' in key or key in ('subtotal','tax_credit'):
        # Explicit currency normalization for this rendered-value audit.
        # The original application parser already handled U+20B9; the earlier
        # contrary diagnosis came from reading UTF-8 JSON with Windows defaults.
        amount=parse_amount(value.replace('\u20b9','').strip())
        return str(amount.normalize()) if amount is not None else value.casefold()
    if key.endswith('_date'):
        date=parse_date(value)
        if date is None:
            for pattern in ('%d-%b-%Y','%d/%m/%y','%d-%m-%y','%d.%m.%y'):
                try:date=datetime.strptime(value,pattern).date();break
                except ValueError:pass
        return date.isoformat() if date else value.casefold()
    if key=='reason':value=re.sub(r'^reason\s*:\s*','',value,flags=re.I)
    if key=='billing_period':value=re.sub(r'^billing\s+period\s*:\s*','',value,flags=re.I)
    if key=='units_consumed':
        # The schema's consumption target is a quantity. This audit checks the
        # numeric quantity only, not a separate unit-of-measure prediction.
        match=re.fullmatch(r'([\d,.]+)(?:\s*(?:kwh|kvah|kl|units?|m3|m\u00b3))?',value,flags=re.I)
        if match:
            number=parse_amount(match.group(1))
            if number is not None:return str(number.normalize())
    if key.endswith('gstin'):return re.sub(r'\s+','',value).upper()
    return re.sub(r'\s+',' ',value).casefold()

def prepare():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    documents=[]
    differences=[]
    for entry in manifest['documents']:
        source=SOURCE/entry['doc_type'].lower()/(entry['id']+'.json')
        assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['annotation_sha256']
        annotation=json.loads(source.read_text(encoding='utf-8'))
        mapping=field_map(entry['doc_type'])
        values=defaultdict(list)
        for line in annotation['ocr']['lines']:
            key=mapping.get(line['field'])
            if key and line['role']=='value':values[key.lower()].append(line['text'])
            # The A5 renderer places supplier GSTIN in a composite registration line.
            if line['field']=='supplier.registration' and 'vendor_gstin' in keys_for(entry['doc_type']):
                expected=annotation['document']['supplier']['gstin']
                if expected and expected in line['text']:values['vendor_gstin'].append(expected)
            # Utility consumption is printed inside a composite meter-reading line.
            if entry['doc_type']=='UTILITY_BILL' and line['field']=='extra.meter_readings':
                match=re.search(r'\bUsed:\s*([\d,.]+)',line['text'])
                if match:values['units_consumed'].append(match.group(1))
        fields={}
        for key,texts in values.items():
            distinct={norm(key,x) for x in texts}
            if len(distinct)!=1:raise ValueError('Conflicting rendered values: '+entry['id']+'/'+key)
            fields[key]=texts[0]
            if entry['fields'].get(key) is None:
                differences.append(dict(id=entry['id'],doc_type=entry['doc_type'],field=key,rendered_value=texts[0],bio_value=None))
        documents.append(dict(id=entry['id'],doc_type=entry['doc_type'],fields=fields,source_annotation=str(source),
            annotation_sha256=entry['annotation_sha256']))
    reference=dict(provenance='Source renderer OCR lines and their semantic field paths. No predictions used to build references. Only printed supported values are checked; unprinted/unmapped fields are unscored, not assumed absent.',
        normalization='Case/whitespace insensitive; amounts parsed numerically; date-format normalization; remove literal Reason: and Billing period: field-name prefixes. No fuzzy matching.',
        exceptions='supplier.registration line recovers printed supplier GSTIN; extra.meter_readings Used: component recovers printed consumption.',
        documents=documents,printed_values_missing_from_bio=differences)
    path=OUT/'rendered_reference.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=reference:raise ValueError('Frozen rendered reference changed')
    write_json(path,reference)
    print('Frozen rendered references:',len(documents),'images;',len(differences),'printed values missing from BIO labels')

def report():
    reference=json.loads((OUT/'rendered_reference.json').read_text(encoding='utf-8'))
    counts=defaultdict(Counter)
    errors=[]
    for entry in reference['documents']:
        result=json.loads((OUT/'documents'/(entry['id']+'.json')).read_text(encoding='utf-8'))
        for arm in ARMS:
            run=result['pipelines'][arm]
            predicted={f['key']:f.get('value') for f in run.get('result',{}).get('fields',[])}
            c=counts[(entry['doc_type'],arm)]
            c['images']+=1;c[run['status']]+=1
            all_ok=bool(run.get('result'))
            for key,expected in entry['fields'].items():
                actual=predicted.get(key)
                correct=norm(key,expected)==norm(key,actual)
                c['checked']+=1;c['correct']+=correct
                all_ok &= correct
                errors.append(dict(id=entry['id'],doc_type=entry['doc_type'],pipeline=arm,key=key,
                    expected=expected,actual=actual,correct=correct,status=run['status']))
            c['all_checked_correct']+=all_ok
    scores=[dict(doc_type=key[0],pipeline=key[1],**c,checked_value_accuracy=c['correct']/c['checked']) for key,c in counts.items()]
    write_json(OUT/'rendered_summary.json',dict(reference_provenance=reference['provenance'],scores=scores,
        missing_bio_values=reference['printed_values_missing_from_bio'],limitations=['Supplemental source-rendered-value audit, not the frozen primary BIO-annotation metric.',
        'Only printed mapped fields are scored. Complete-document accuracy and F1 cannot be claimed from this positive-only audit.']))
    with (OUT/'rendered_field_checks.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(errors[0]));writer.writeheader();writer.writerows(errors)
    lines=['# Supplemental printed-value comparison','',reference['provenance'],'',
        'This table checks printed values from the source renderer. It supplements the primary BIO-based report because some printed values lack BIO labels. It is not full-document accuracy or a field F1 score. Failed requests remain missing predictions.','',
        '| Type | Images | OCR + regex | OCR + LayoutLM | Hosted VLM | Hybrid |',
        '|---|---:|---:|---:|---:|---:|']
    for kind in ['GST_INVOICE','PURCHASE_BILL','EXPENSE_RECEIPT','UTILITY_BILL','CREDIT_NOTE','DEBIT_NOTE']:
        row=[]
        for arm in ARMS:
            c=counts[(kind,arm)];row.append(f"{c['correct']}/{c['checked']} ({c['correct']/c['checked']:.2%})")
        lines.append('| '+kind+' | 10 | '+' | '.join(row)+' |')
    lines+=['',f"Printed values missing BIO labels: {len(reference['printed_values_missing_from_bio'])}.",'',
        'Original BIO-based results remain in REPORT.md and summary.json. Source references and explicit exceptions are in rendered_reference.json; every comparison is in rendered_field_checks.csv.']
    (OUT/'PRINTED_VALUE_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='prepare':prepare()
    else:report()
