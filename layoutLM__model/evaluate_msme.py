"""Paired old/new held-out checkpoint evaluation and offline real OCR smoke test."""
import argparse
from collections import Counter
import io
import json
from pathlib import Path
import sys
import traceback

from common import HERE, ROOT, LABEL_SETS, DOC_TYPE_TO_MODEL, read_rows, write_json, digest

sys.path.insert(0, str(ROOT/'research'))
from checkpoint_eval import evaluate_checkpoint
from evaluate import normalize


def errors(path):
    counts = Counter()
    examples = []
    for row in read_rows(path):
        for key, gold in row['gold_fields'].items():
            actual = row['predicted_fields'].get(key)
            if normalize(key, gold) != normalize(key, actual):
                category = 'extra' if gold is None else 'missing' if actual is None else 'wrong'
                counts[key+':'+category] += 1
                if len(examples) < 40:
                    examples.append(dict(id=row['id'], image=row['image'], field=key,
                                         expected=gold, actual=actual, category=category))
    return dict(counts= dict(counts), examples=examples)


def real_smoke(run, out):
    from PIL import Image
    from config import settings
    from services.extractor import layoutlm_extractor as local
    records = []
    # Fixed existing real-document OCR records; other cached records are synthetic.
    for file_id, kind in [('9b3274bf-cd12-42cf-af2d-8c2093c2c806', 'GST_INVOICE'),
                          ('8a1e57e8-6965-4a96-b125-da067f98368a', 'CREDIT_NOTE')]:
        ocr_path = ROOT/'backend/data/ocr_results'/ (file_id+'.json')
        candidates = [p for p in (ROOT/'backend/data/raw_invoices').glob(file_id+'.*')
                      if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
        if not ocr_path.exists() or len(candidates) != 1:
            records.append(dict(id=file_id, status='unavailable', reason='Missing cached OCR or image'))
            continue
        image_path = candidates[0]
        image = image_path.read_bytes()
        ocr = json.loads(ocr_path.read_text(encoding='utf-8'))
        width, height = Image.open(io.BytesIO(image)).size
        record = dict(id=file_id, doc_type=kind, image=str(image_path), image_sha256=digest(image_path),
                      ocr_sha256=digest(ocr_path), scope='Previously cached OCR; no fresh provider call; unverified field truth', arms={})
        for arm, root in [('existing', HERE), ('new', run/'models')]:
            local.release_models()
            settings.LAYOUTLM_MODEL_ROOT = str(root)
            diagnostics = {}
            record['arms'][arm] = dict(fields=local.extract_fields(image,
                [w['text'] for w in ocr['words']], [w['bounding_box'] for w in ocr['words']],
                width, height, kind, ocr['full_text'], strict=True, diagnostics=diagnostics),
                diagnostics=diagnostics)
        records.append(record)
    local.release_models()
    write_json(out/'real_smoke.json', records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not args.run_id.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid run ID')
    run = HERE/'runs'/args.run_id
    out = run/'evaluation'
    out.mkdir(parents=True, exist_ok=True)
    status = dict(status='running', completed=[])
    results = {}
    try:
        for kind, labels in LABEL_SETS.items():
            data = run/'data'/kind.lower()/'test.jsonl'
            test = read_rows(data)
            trained = read_rows(run/'data'/kind.lower()/'train.jsonl')
            dev = read_rows(run/'data'/kind.lower()/'development.jsonl')
            assert len(test) == 100
            assert not ({r['id'] for r in test} & {r['id'] for r in trained+dev})
            assert not ({r['group'] for r in test} & {r['group'] for r in trained+dev})
            pair = {}
            for arm, root in [('existing', HERE), ('new', run/'models')]:
                status.update(active_type=kind, active_arm=arm)
                write_json(out/'status.json', status)
                metrics = evaluate_checkpoint(root/DOC_TYPE_TO_MODEL[kind], data, labels,
                                               out/(kind.lower()+'-'+arm+'.json'))
                pair[arm] = metrics
                write_json(out/(kind.lower()+'-'+arm+'-errors.json'),
                           errors(out/(kind.lower()+'-'+arm+'.predictions.jsonl')))
                print(json.dumps(dict(doc_type=kind, arm=arm, f1=metrics['field_micro_f1'],
                                      complete_accuracy=metrics['complete_document_accuracy'])), flush=True)
            pair['improved'] = (pair['new']['field_micro_f1'] > pair['existing']['field_micro_f1']
                                and pair['new']['complete_document_accuracy'] >= pair['existing']['complete_document_accuracy'])
            results[kind] = pair
            status['completed'].append(kind)
            write_json(out/'comparison.json', results)
        status.update(active_type='real_smoke', active_arm=None)
        write_json(out/'status.json', status)
        real_smoke(run, out)
        lines = ['# MSME held-out checkpoint comparison', '',
                 '100 held-out synthetic documents per type. Supplied generator OCR; no real-world accuracy claim.', '',
                 '| Type | Existing field F1 | New field F1 | Existing document accuracy | New document accuracy |',
                 '|---|---:|---:|---:|---:|']
        for kind, pair in results.items():
            a,b=pair['existing'],pair['new']
            lines.append(f"| {kind} | {a['field_micro_f1']:.2%} | {b['field_micro_f1']:.2%} | {a['complete_document_accuracy']:.2%} | {b['complete_document_accuracy']:.2%} |")
        lines += ['', 'Real smoke predictions are in real_smoke.json. Real annotations are unverified.',
                  'Per-field counts and error examples are saved for both arms. Missing training labels remain unsupported.',
                  'No checkpoint activation is performed by this evaluator.']
        (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        status.update(status='complete', active_type=None)
    except Exception as exc:
        status.update(status='failed', error=str(exc))
        traceback.print_exc()
        raise
    finally:
        write_json(out/'status.json', status)


if __name__ == '__main__':
    main()
