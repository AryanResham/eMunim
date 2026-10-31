"""Import annotated ERP generator documents and train six isolated CUDA models."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from common import HERE, ROOT, LABEL_SETS, DOC_TYPE_TO_MODEL, digest, read_rows, validate_row, write_json, write_rows


def field_map(kind):
    common = {'supplier.name': 'VENDOR_NAME', 'supplier.gstin': 'VENDOR_GSTIN'}
    if kind == 'GST_INVOICE':
        return {**common, 'document_number': 'INVOICE_NO', 'date': 'INVOICE_DATE',
                'buyer.name': 'BUYER_NAME', 'buyer.gstin': 'BUYER_GSTIN',
                'totals.taxable_value': 'TAXABLE_AMOUNT', 'totals.cgst': 'CGST_AMOUNT',
                'totals.sgst': 'SGST_AMOUNT', 'totals.igst': 'IGST_AMOUNT',
                'totals.grand_total': 'TOTAL_AMOUNT', 'extra.due_date': 'DUE_DATE',
                'extra.purchase_order': 'PO_NUMBER'}
    if kind == 'PURCHASE_BILL':
        return {**common, 'document_number': 'BILL_NO', 'date': 'BILL_DATE',
                'totals.taxable_value': 'SUBTOTAL', 'totals.tax_total': 'TAX_AMOUNT',
                'totals.grand_total': 'TOTAL_AMOUNT', 'extra.payment_terms': 'PAYMENT_TERMS'}
    if kind == 'EXPENSE_RECEIPT':
        return {'supplier.name': 'VENDOR_NAME', 'document_number': 'RECEIPT_NO',
                'date': 'RECEIPT_DATE', 'totals.grand_total': 'AMOUNT',
                'totals.tax_total': 'TAX_AMOUNT', 'extra.payment_mode': 'PAYMENT_MODE',
                'extra.category': 'CATEGORY'}
    if kind == 'UTILITY_BILL':
        return {'supplier.name': 'UTILITY_PROVIDER', 'buyer.name': 'ACCOUNT_NAME',
                'date': 'BILL_DATE', 'extra.due_date': 'DUE_DATE',
                'extra.consumer_number': 'CONSUMER_NO', 'extra.billing_period': 'BILLING_PERIOD',
                'extra.consumption': 'UNITS_CONSUMED', 'totals.grand_total': 'AMOUNT_DUE'}
    prefix = 'CREDIT' if kind == 'CREDIT_NOTE' else 'DEBIT'
    return {**common, 'document_number': prefix + '_NOTE_NO', 'date': prefix + '_NOTE_DATE',
            'extra.reference_invoice.number': 'ORIGINAL_INVOICE_NO', 'extra.reason': 'REASON',
            'totals.grand_total': prefix + '_AMOUNT',
            'totals.tax_total': 'TAX_CREDIT' if prefix == 'CREDIT' else 'TAX_AMOUNT'}


def prepare(dataset, run):
    manifest = dataset / 'manifest.jsonl'
    groups = defaultdict(list)
    identities = {}
    parties = {}
    seen = set()
    for item in read_rows(manifest):
        kind = item['document_type'].upper()
        split = {'val': 'development', 'train': 'train', 'test': 'test'}[item['split']]
        if item['sample_id'] in seen:
            raise ValueError('Duplicate sample ID')
        seen.add(item['sample_id'])
        for identifier, registry in [(item['base_document_id'], identities),
                                     (item['supplier_id'], parties), (item['buyer_id'], parties)]:
            if registry.setdefault(identifier, split) != split:
                raise ValueError('Cross-split document/party leakage: ' + identifier)
        annotation = dataset / item['annotation']
        image = dataset / item['image']
        if not image.is_file():
            raise FileNotFoundError(image)
        data = json.loads(annotation.read_text(encoding='utf-8'))
        if data['sample_id'] != item['sample_id'] or data['split'] != item['split']:
            raise ValueError('Manifest/annotation mismatch')
        mapping = field_map(kind)
        words, boxes, labels = [], [], []
        previous = None
        values = defaultdict(list)
        for word in data['ocr']['words']:
            target = mapping.get(word['field']) if word['role'] == 'value' else None
            # Only supervise visible values; never invent a combined tax token from components.
            label = ('I-' if previous == target else 'B-') + target if target else 'O'
            words.append(word['text'])
            boxes.append(word['bbox_1000'])
            labels.append(label)
            if target:
                values[target.lower()].append(word['text'])
            previous = target
        row = dict(id=item['sample_id'], image=str(image.resolve()), words=words, boxes=boxes,
                   labels=labels, fields={x[2:].lower(): ' '.join(values[x[2:].lower()]) or None
                                         for x in LABEL_SETS[kind] if x.startswith('B-')},
                   annotation_sha256=digest(annotation), group=item['base_document_id'])
        validate_row(row, LABEL_SETS[kind])
        groups[kind, split].append(row)
    audit = dict(source=str(dataset), manifest_sha256=digest(manifest), documents=len(seen),
                 synthetic_data=True, layout_families_shared_across_splits=True, types={})
    for kind in LABEL_SETS:
        counts = Counter(label for row in groups[kind, 'train'] for label in row['labels'])
        audit['types'][kind] = dict(splits={}, missing_training_labels=[x for x in LABEL_SETS[kind]
                                                                     if x.startswith('B-') and not counts[x]])
        for split in ('train', 'development', 'test'):
            rows = groups[kind, split]
            if len(rows) != {'train': 800, 'development': 100, 'test': 100}[split]:
                raise ValueError('Unexpected split count: ' + kind + '/' + split)
            write_rows(run / 'data' / kind.lower() / (split + '.jsonl'), rows)
            audit['types'][kind]['splits'][split] = len(rows)
    write_json(run / 'dataset_audit.json', audit)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT/'indian_erp_doc_generator/indian_erp_doc_generator/msme_6000')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if not args.run_id.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid run ID')
    run = HERE / 'runs' / args.run_id
    run.mkdir(parents=True, exist_ok=True)
    lock = (HERE / 'runs/training.lock').open('a+b')
    if sys.platform == 'win32':
        import msvcrt
        lock.seek(0); lock.write(b'1'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = dict(status='preparing', run_id=args.run_id, completed_types=[],
                 started_at=datetime.now(timezone.utc).isoformat())
    try:
        audit = prepare(args.dataset.resolve(), run)
        print(json.dumps(audit), flush=True)
        if args.prepare_only:
            return
        for kind in LABEL_SETS:
            output = run / 'models' / DOC_TYPE_TO_MODEL[kind]
            state.update(status='running', active_type=kind)
            write_json(run/'status.json', state)
            command = [sys.executable, '-u', str(HERE/'train_stage.py'), '--stage', 'synthetic',
                       '--doc-type', kind, '--source', str(HERE/DOC_TYPE_TO_MODEL[kind]),
                       '--output', str(output), '--run-id', args.run_id,
                       '--data-dir', str(run/'data'/kind.lower()), '--allow-missing-labels', '--keep-head']
            with (run/(kind.lower()+'.log')).open('a', encoding='utf-8') as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               env={**os.environ, 'TOKENIZERS_PARALLELISM': 'false'}, check=True)
            state['completed_types'].append(kind)
        state.update(status='complete', active_type=None)
    except Exception as exc:
        state.update(status='failed', error=str(exc))
        raise
    finally:
        write_json(run/'status.json', state)
        lock.close()


if __name__ == '__main__':
    main()
