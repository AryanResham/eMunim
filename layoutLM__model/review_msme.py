"""Replay saved predictions using single-value field truth; no model inference."""
import argparse
from collections import Counter, defaultdict
from common import HERE, LABEL_SETS, read_rows, write_json
from train_stage import entity_spans
import sys
sys.path.insert(0, str(HERE.parent/'research'))
from evaluate import normalize


def score(records, kind):
    counters = defaultdict(Counter)
    examples = []
    complete = 0
    repeated = Counter()
    for row in records:
        gold = defaultdict(list)
        for name, _, _, text in entity_spans(row['words'], row['gold_tags']):
            gold[name.lower()].append(text)
        document_correct = True
        for label in LABEL_SETS[kind]:
            if not label.startswith('B-'):
                continue
            key = label[2:].lower()
            distinct = {normalize(key, text) for text in gold[key]}
            if len(distinct) > 1:
                raise ValueError(f"Conflicting gold values: {row['id']} / {key}: {gold[key]}")
            expected = next(iter(distinct), None)
            actual = normalize(key, row['predicted_fields'].get(key))
            if len(gold[key]) > 1:
                repeated[key] += 1
            counts = counters[key]
            counts['present'] += expected is not None
            if expected is not None and expected == actual:
                counts['tp'] += 1
            elif expected != actual:
                counts['fn'] += expected is not None
                counts['fp'] += actual is not None
                document_correct = False
                category = 'extra' if expected is None else 'missing' if actual is None else 'wrong'
                counts[category] += 1
                if len(examples) < 50:
                    examples.append(dict(id=row['id'], image=row['image'], field=key,
                                         expected=expected, actual=actual, category=category))
        complete += document_correct
    tp, fp, fn = [sum(c[k] for c in counters.values()) for k in ('tp', 'fp', 'fn')]
    for c in counters.values():
        denominator = 2*c['tp']+c['fp']+c['fn']
        c['f1'] = 2*c['tp']/denominator if denominator else None
    return dict(documents=len(records), field_f1=2*tp/(2*tp+fp+fn) if tp+fp+fn else 0,
                complete_document_accuracy=complete/len(records), tp=tp, fp=fp, fn=fn,
                per_field=dict(counters), repeated_gold_fields=dict(repeated), errors=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    out = HERE/'runs'/args.run_id/'evaluation'
    result = dict(protocol='One semantic value per field; collapse identical gold BIO spans; reject conflicting gold spans. Predictions use the last BIO span, matching backend aggregation.',
                  source='Saved raw paired checkpoint predictions; no new inference or training', types={})
    lines = ['# Corrected MSME test comparison', '', result['protocol'], '',
             '| Type | Old field F1 | New field F1 | Old document accuracy | New document accuracy |',
             '|---|---:|---:|---:|---:|']
    for kind in LABEL_SETS:
        pair = {arm:score(read_rows(out/(kind.lower()+'-'+arm+'.predictions.jsonl')),kind)
                for arm in ('existing','new')}
        a,b=pair['existing'],pair['new']
        pair['synthetic_improved'] = b['field_f1'] > a['field_f1'] and b['complete_document_accuracy'] >= a['complete_document_accuracy']
        result['types'][kind] = pair
        lines.append(f"| {kind} | {a['field_f1']:.2%} | {b['field_f1']:.2%} | {a['complete_document_accuracy']:.2%} | {b['complete_document_accuracy']:.2%} |")
    lines += ['', 'These are synthetic test results using generator OCR. Missing annotated labels cannot be assessed for recall.',
              'The real-document smoke check uses cached provider OCR and has no independently verified accuracy labels.',
              'Raw original metrics and predictions are retained separately.']
    write_json(out/'corrected_comparison.json', result)
    (out/'corrected_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
