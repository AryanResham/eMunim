# Verification results — 2026-10-16

The configured Google Vision and Groq keys were used for bounded live tests.
Keys were not changed or copied into frontend code. No training or changes
were made inside the LayoutLM folder. Existing edits there predate this work.
All test accounting records were isolated from the normal database.

## Final checks

| Check | Result |
|---|---|
| Backend tests | 42 passed |
| Headless Chrome browser tests with live extraction | 5 passed, 0 skipped, 0 unexpected failures |
| Frontend lint | Passed |
| Frontend production build | Passed |
| npm dependency audit after compatible updates | 0 vulnerabilities |
| Python source compilation | 59 source files passed |
| Google OCR on six generated document types | Passed |
| Classification on those six types | 6/6 correct |
| Three pipelines × six documents × two OCR variants | 36 runs, no operational failures |
| Scoring, A/B/C review replay and paired OCR report | Passed |

The six types are GST invoice, purchase bill, expense receipt, utility bill,
credit note and debit note. Browser coverage includes configuration, dashboard,
records, annotation validation/persistence, unsaved type-change handling and
each pipeline's upload → extraction → edit → validation → explicit confirmation
→ save → search → record detail → CSV download. Hosted-only made no OCR call;
the pure LayoutLM path made no hosted call.

Backend checks additionally cover missing weights, unavailable providers,
bounded retries, rate-limit cooldowns, malformed model output, missing OCR,
invalid/oversized uploads, schema enforcement, server-derived field sources,
save idempotency, retained original values, CSV formula escaping, dataset
image identity, split leakage and incomplete annotation rejection.

## Synthetic extraction findings

These are six generated documents with known programmatic truth, one per
type, sharing a simple layout. They are diagnostic examples, not a real-data
benchmark, representative accuracy estimate, calibrated test set or evidence
of universal model superiority.

| Pipeline | Completely correct documents, Google OCR variant | Macro field F1 |
|---|---:|---:|
| OCR + LayoutLM | 0/6 | 0.0270 |
| Hosted VLM | 6/6 | 1.0000 |
| LayoutLM + selective hosted fallback | 5/6 | 0.9730 |

The exact generated OCR variant produced the same aggregate extraction scores.
Correcting OCR alone did not remove the local model's failures on these layouts.
This supports investigating model generalization rather than assuming OCR is
the sole problem. It does not establish the isolated causal contribution of
layout, training balance, or tokenization.

On the GST example, LayoutLM confidently labeled `90.00` as the invoice date.
The hybrid preserved that local value under its conservative conflict policy,
recorded disagreement with the hosted result, and flagged review. Common
validation review flagged all six incorrect local documents and the single
incorrect hybrid document; no incorrect document passed unflagged in this tiny
cohort. This is evidence that the review path works on these examples, not a
claim that validation catches every error.

Seven fresh hosted attempts were used in the final six-document Google run.
The paired exact-OCR run and hybrid path reused hosted image-only responses.
Their cached latency and zero fresh attempts must not be presented as independent
deployment speed/cost advantages. Request pacing also contributes to latency.

## Fixes found during verification

- Hosted retries now respect seconds/HTTP-date Retry-After within a configured
  maximum wait. Longer cooldowns fail explicitly. Batch verification uses
  per-process request spacing and remains bounded by a physical-call budget.
- Explicit utility-bill headings are recognized; generic invoice mentions no
  longer override more specific purchase-bill or receipt rules.
- Discarding an unsaved annotation type change restores the saved draft rather
  than keeping a mutated in-memory record. Type changes preserve metadata.
- Browser tests allow a realistic cold LayoutLM load time. A prior 15-second
  response timeout was a test-harness failure, not an extraction API failure.
- Compatible frontend dependency updates cleared ten audit findings. Vite's
  module path handling was updated and the build passed after those changes.

The original rate-limited run is preserved rather than replaced. See the
[provider's rate-limit documentation](https://console.groq.com/docs/rate-limits)
for the Retry-After header contract. Spacing is per process, not a distributed
quota limiter; future quota outages remain possible.

## Evidence on this machine

- Live system audit: `backend/data/verification/20261016T141940Z/report.json`
- Original rate-limited cohort: `backend/data/verification/20261016T142528Z-all-types/report.json`
- Final complete cohort: `backend/data/verification/20261016T143705Z-all-types/report.json`
- Pipeline scores and review metrics: the same folder's `google-scores.json`
  and `corrected-scores.json`; readable summaries use `.md`.
- Paired OCR results: the same folder's `paired-ocr.json`.
- Final browser evidence: `backend/data/browser-tests/2026-10-16T15-36-11-986Z/results.json`

Raw predictions, OCR hashes, checkpoint hashes, manifests, policies and command
logs remain alongside the cohort reports. Local evidence is git-ignored.

## Remaining external requirements

DATABASE_URL is still absent. SQLite persistence was verified; PostgreSQL was
not exercised. The 34 imported document images remain unverified annotation
drafts. API predictions cannot independently certify ground truth. Real-data
paper results require checked labels, independent development/test groups and
a policy frozen after development calibration. LayoutLM retraining remains
deferred as requested.
