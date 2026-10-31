"""Read-only postprocessing of completed measured predictions; no model/API calls."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'research')]
from evaluate import evaluate, normalize
from services.field_contract import keys_for
from services.validator.rules_engine import review_document


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def values(run):
    return {field['key']: field.get('value') for field in run.get('fields', [])}


def decision(entry, run, policy, threshold):
    meta = run.get('metadata', {})
    reasons = meta.get('operational_reasons', []) + ([run['error']] if run.get('error') else [])
    return review_document(entry['doc_type'], run.get('fields', []), policy,
                           reasons, meta.get('conflicts', []), threshold)['review_required']


def analyze(entries, rows, threshold):
    by_id = {row['id']: row for row in rows}
    result = {'by_type': {}, 'incremental_C_vs_B': {}, 'hybrid_field_changes':
              {'improvements': 0, 'regressions': 0, 'wrong_to_different_wrong': 0,
               'examples': []}, 'undetected_B_examples': [], 'confidently_wrong_examples': []}
    common = [entry for entry in entries if all(
        not (run.get('error') or run.get('metadata', {}).get('degraded'))
        for run in by_id[entry['id']]['pipelines'].values())]
    result['common_success'] = {
        'scope': 'Conditional descriptive comparison only. Primary full-cohort results retain failures. Provider success selection may confound type/order; not an unbiased six-type ranking.',
        'documents': len(common), 'ids': [entry['id'] for entry in common],
        'type_counts': {t: sum(e['doc_type'] == t for e in common) for t in sorted({e['doc_type'] for e in entries})},
        'report': evaluate(common, [by_id[e['id']] for e in common], threshold) if common else None}
    for doc_type in sorted({entry['doc_type'] for entry in entries}):
        subset = [entry for entry in entries if entry['doc_type'] == doc_type]
        result['by_type'][doc_type] = evaluate(subset, [by_id[e['id']] for e in subset], threshold)
    for pipeline in ('ocr_layoutlm', 'hosted_vlm', 'layoutlm_hosted_fallback'):
        totals = dict(additional_reviewed=0, additional_incorrect_detected=0,
                      additional_correct_reviewed=0, B_flags_removed_by_C=0)
        for entry in entries:
            run = by_id[entry['id']]['pipelines'][pipeline]
            predicted = values(run)
            errors = [key for key in keys_for(entry['doc_type'])
                      if normalize(key, entry['fields'][key]) != normalize(key, predicted.get(key))]
            incorrect = bool(errors or run.get('error') or run.get('metadata', {}).get('degraded'))
            b = decision(entry, run, 'validation_review', threshold)
            c = decision(entry, run, 'validation_confidence_review', threshold)
            totals['additional_reviewed'] += c and not b
            totals['additional_incorrect_detected'] += c and not b and incorrect
            totals['additional_correct_reviewed'] += c and not b and not incorrect
            totals['B_flags_removed_by_C'] += b and not c
            if incorrect and not b and len(result['undetected_B_examples']) < 12:
                result['undetected_B_examples'].append(dict(id=entry['id'], pipeline=pipeline,
                                                            incorrect_fields=errors, operational_error=run.get('error')))
            for field in run.get('fields', []):
                if (field['key'] in errors and field.get('source') == 'layoutlm'
                        and (field.get('confidence') or 0) >= 95
                        and len(result['confidently_wrong_examples']) < 12):
                    result['confidently_wrong_examples'].append(dict(id=entry['id'], pipeline=pipeline,
                        key=field['key'], truth=entry['fields'][field['key']], prediction=field.get('value'),
                        confidence=field['confidence']))
        result['incremental_C_vs_B'][pipeline] = totals
    changes = result['hybrid_field_changes']
    for entry in entries:
        arms = by_id[entry['id']]['pipelines']
        local, hybrid = values(arms['ocr_layoutlm']), values(arms['layoutlm_hosted_fallback'])
        for key in keys_for(entry['doc_type']):
            gold = normalize(key, entry['fields'][key])
            before, after = normalize(key, local.get(key)), normalize(key, hybrid.get(key))
            if before == after:
                continue
            category = 'improvements' if after == gold else 'regressions' if before == gold else 'wrong_to_different_wrong'
            changes[category] += 1
            if len(changes['examples']) < 18:
                changes['examples'].append(dict(id=entry['id'], key=key, category=category,
                    truth=entry['fields'][key], local=local.get(key), hybrid=hybrid.get(key)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_folder', type=Path)
    args = parser.parse_args()
    folder = args.run_folder.resolve()
    state = json.loads((folder / 'status.json').read_text(encoding='utf-8'))
    if state['status'] not in ('complete', 'completed_with_failures'):
        raise ValueError('Only completed cohorts can be postprocessed')
    pilot = folder / 'pipelines'
    manifest = json.loads((pilot / 'manifest.json').read_text(encoding='utf-8'))
    entries = [e for e in manifest['documents'] if e['split'] == 'test']
    paths = [pilot / 'raw' / (e['id'] + '.json') for e in entries]
    rows = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
    policy = json.loads((pilot / 'policy.json').read_text(encoding='utf-8'))
    result = analyze(entries, rows, policy['review_threshold'])
    result['provenance'] = {'scope': 'Exploratory postprocessing of frozen synthetic test outputs; no tuning or new inference',
        'documents': len(entries), 'manifest_sha256': sha(pilot / 'manifest.json'),
        'policy_sha256': sha(pilot / 'policy.json'), 'script_sha256': sha(__file__),
        'raw_sha256': {path.name: sha(path) for path in paths},
        'limitations': 'Six documents/type. No real-data or participant claims; examples illustrate errors, not prevalence estimates.'}
    (folder / 'supplementary_analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    common = result['common_success']
    summary_path = folder / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['supplementary_analysis'] = result
    failed_types = sorted({entry['doc_type'] for entry in entries if any(
        run.get('error') or run.get('metadata', {}).get('degraded')
        for run in next(row for row in rows if row['id'] == entry['id'])['pipelines'].values())})
    latency_counts = ', '.join(f"{name}: {metrics['client_ms_excluding_pacing']['samples']}" for name, metrics in summary['pipelines'].items())
    notes = ['## Supplementary saved-output analysis', '',
        f"The common-success subset contains **{common['documents']}** documents.",
        common['scope'], '',
        'The primary tables above retain every failure. Types with operational failures: '+(', '.join(failed_types) or 'none')+'. Provider availability and document type/order can be confounded. Consult saved reasons; the exact quota dimension and reset time are not retained and cannot be inferred.', '',
        '| Pipeline | Common-success N | Micro field F1 | Complete document accuracy |',
        '|---|---:|---:|---:|']
    if common['report']:
        for name, metrics in common['report']['pipelines'].items():
            notes.append(f"| {name} | {metrics['documents']} | {metrics['micro_field_f1']:.6f} | {metrics['complete_document_accuracy']:.6f} |")
    changes = result['hybrid_field_changes']
    notes += ['', f"Hybrid field changes: {changes['improvements']} improvements, {changes['regressions']} regressions, and {changes['wrong_to_different_wrong']} changes between two incorrect values.", '',
        'Incremental confidence review beyond validation B:', '',
        '| Pipeline | Additional reviews | Additional incorrect detected | Additional correct reviewed |',
        '|---|---:|---:|---:|']
    for name, counts in result['incremental_C_vs_B'].items():
        notes.append(f"| {name} | {counts['additional_reviewed']} | {counts['additional_incorrect_detected']} | {counts['additional_correct_reviewed']} |")
    notes += ['', 'Interpretation qualifications:', '',
        '- At the frozen threshold, hybrid fallback rate is '+str(summary['pipelines']['layoutlm_hosted_fallback']['fallback_rate'])+'. A rate of 1 means no logical hosted-call savings versus P2.',
        '- Confidence review local-only accepted coverage: '+str(summary['pipelines']['ocr_layoutlm']['review']['validation_confidence_review']['coverage'])+'. If coverage is zero, accepted accuracy is undefined, not 100%.',
        '- Pacing-excluded client latency sample counts: '+latency_counts+'. Failed hosted-only calls lack a retained pacing breakdown; use all-attempt elapsed_ms for the full operational distribution, with pacing included. These latency populations are not interchangeable.',
        '- OCR CER/WER includes generator-versus-OCR reading-order differences. It is not a pure glyph-recognition error estimate.',
        '- Reported token usage covers accepted provider responses. Failed-attempt consumption and actual charges are unavailable.',
        '- Source snapshot and raw/policy hashes support inspection. Per-type counts and examples are in supplementary_analysis.json and per_type.csv.',
        '', 'Supplementary generator: scripts/summarize_paper.py; no inference or policy tuning.']
    report_path = folder / 'report.md'
    original = report_path.read_text(encoding='utf-8').split('\n## Supplementary saved-output analysis')[0]
    if not (folder / 'primary_report.md').exists():
        (folder / 'primary_report.md').write_text(original, encoding='utf-8')
    report_path.write_text(original + '\n\n' + '\n'.join(notes), encoding='utf-8')
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    # Keep exported latency figure honest about its differing available populations.
    import os
    os.environ.setdefault('MPLCONFIGDIR', str(folder / 'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names = list(summary['pipelines'])
    metrics = [summary['pipelines'][name]['client_ms_excluding_pacing'] for name in names]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([name.replace('_', '\n') + f"\nN={metric['samples']}" for name, metric in zip(names, metrics)],
           [metric['median'] / 1000 if metric['median'] is not None else float('nan') for metric in metrics])
    ax.set_ylabel('Median client seconds, artificial spacing excluded')
    ax.set_title('Available client latency samples; different populations')
    fig.text(.5, .02, 'Failed hosted-only calls lack retained pacing details.\nFull operational elapsed distributions include pacing and failures; see JSON.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .10, 1, 1))
    for suffix in ('svg', 'png'):
        fig.savefig(folder / ('figure_latency.' + suffix), dpi=150, bbox_inches='tight')
    plt.close(fig)
    with (folder / 'per_type.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['doc_type', 'pipeline', 'N', 'micro_field_f1', 'complete_document_accuracy', 'failures'])
        for doc_type, report in result['by_type'].items():
            for pipeline, metrics in report['pipelines'].items():
                writer.writerow([doc_type, pipeline, metrics['documents'], metrics['micro_field_f1'],
                                 metrics['complete_document_accuracy'], metrics['failures']])
    print(json.dumps({key: result[key] for key in ('incremental_C_vs_B', 'hybrid_field_changes')}, indent=2))


if __name__ == '__main__':
    main()
