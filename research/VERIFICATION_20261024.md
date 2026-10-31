# Application and benchmark verification — 2026-10-24

The local application runs at http://127.0.0.1:5173 with its API at
http://127.0.0.1:8000. Service process identities and logs are saved in
`backend/data/app_runtime/launch.json`. SQLite is the working persistence backend.

## Executed checks

| Check | Observed result | Evidence |
|---|---|---|
| Unit/API/metric/training-contract tests | 61 passed, one pytz deprecation warning; 26.37 seconds | `backend/data/app_runtime/final-unit-tests.xml` |
| Supplementary analysis known-answer test | 1 passed; 0.29 seconds | `backend/data/app_runtime/supplementary-tests.xml` |
| Browser end-to-end workflows | 6 passed, no skips or retries; 53.08 seconds | `backend/data/browser-tests/2026-10-24T14-55-11-595Z/results.json` |
| Frontend ESLint | Exit 0 | `npm.cmd run lint` |
| TypeScript and production build | Exit 0; 2,133 transformed modules | `npm.cmd run build` |
| Frontend dependency audit after compatible Zod update | Zero reported vulnerabilities | `npm.cmd update zod --ignore-scripts --fetch-retries=0 --fetch-timeout=20000` |

Browser tests use isolated SQLite/storage and synthetic fixtures. They exercise
real configured extraction providers, editing, validation, explicit confirmation,
save, search, detail, CSV, Research, mobile navigation, and the annotation UI.
They demonstrate workflow behavior, not real-data model accuracy. An earlier
browser run had one genuine transient Google OCR failure (5/6 passed); its
evidence remains under `backend/data/browser-tests/2026-10-24T14-40-05-185Z`.
Bounded transient OCR retries were added before the successful six-test run.

## Measured research run

Run ID: `paper-20261024-r2`. Read its current `status.json` and generated
`report.md` under `backend/data/paper_runs/paper-20261024-r2` for completion and
results. Raw predictions, request attempts, manifests, hashes, thresholds and
failures are retained. Definitions are in [METRICS.md](METRICS.md).

The run finished at 16:16:16 UTC with status **completed_with_failures**. The
physical ledger contains 66 Google attempts (30 development + 36 test) and 90
hosted attempts, within the combined 220-attempt budget. All 108 test pipeline
arms have saved outputs. Nine PNG and nine SVG figures were generated. An
independent recount matched all primary field F1, complete-document accuracy and
failure counts; JSON finiteness and frozen source hashes passed verification
(`evidence_audit.json`).

| Pipeline | Full test N | Micro field F1 | Complete accuracy | Operational failures/degraded |
|---|---:|---:|---:|---:|
| Local LayoutLM | 36 | 0.778146 | 0.027778 | 0 |
| Hosted VLM | 36 | 0.796875 | 0.555556 | 12 |
| Selective hybrid | 36 | 0.880131 | 0.527778 | 12 |

The hosted provider returned rate-limit cooldowns exceeding the configured wait
limit on all six credit-note and six debit-note cases. P3 retained local output
and marked it degraded. The exact quota dimension/reset time was not retained.
These are genuine failed/degraded executions; they were not removed or replaced
by successful retries after the experiment. The primary comparison confounds
availability with type/order and cannot establish a clean model-quality ranking.

The conditional common-success subset has 24 documents (six each GST invoice,
purchase bill, expense receipt and utility bill). Its field F1 values are
0.830097/0.980769/0.978417 for P1/P2/P3. This descriptive subset excludes failures
and is not an unbiased six-type comparison. It supplements the primary results.

P3 routed all 36 documents, so it showed no logical hosted-call savings. It
improved 37 fields and regressed four. Local confidence review flagged 26
additional incorrect documents and one additional correct document beyond B;
it reviewed every document, leaving accepted accuracy undefined. These are
measured limitations, not evidence that the hybrid or review policy wins.

The pacing-excluded latency figure labels its differing populations: P2 N=24,
P1/P3 N=36. Failed P2 calls lack pacing breakdowns. All-attempt elapsed timings
remain in JSON and include pacing; do not compare these scopes interchangeably.
OCR CER/WER includes reading-order disagreement and is not pure glyph error.

Final read-only Chrome verification checked the normal running app on desktop
and mobile: completed status/count, visible failure warning, actual scores,
conditional count, four artifact downloads, and zero page errors. Evidence:
`backend/data/app_runtime/live-browser-check.json`, `research-desktop.png`, and
`research-mobile.png`. HTTP health/proxy/records/Research checks also returned
200 (`live-http-checks.json`). This ran after the final Research-page changes;
lint and production build passed again.

The first run, `paper-20261024`, failed on a NumPy integer JSON serialization
error before the live-provider phase. Its failed status/logs are retained.
The serialization fix has a regression test. The second run is a distinct
measurement; results are not spliced between run directories.

The held-out checkpoint phase evaluated 1,290 documents: 50 FUNSD, 340
hash-filtered SROIE, and 900 generated documents across six type-specific
models. FUNSD strict entity F1 was 0.7165374030522891; SROIE was
0.7998572957545487. All six synthetic checkpoint tests had field F1 1.0 using
generator-provided text/boxes. These are different tasks and experimental
conditions. In the separate production-OCR development cohort, 29/30 documents
had at least one incorrect field; synthetic ceiling scores do not establish
production-OCR or real invoice accuracy.

## Evidence still missing

- There are 34 real-image annotation drafts and zero verified real labels. No
  real Indian MSME extraction/reliability result can be reported yet.
- DATABASE_URL is absent and the Docker daemon is not running. PostgreSQL was
  not verified; SQLite persistence was tested.
- Actual account charges, controlled human timing, remote-provider memory,
  duplicate-detector accuracy and accounting-head classification lack evidence.
- Hosted token totals describe usage returned with accepted responses, not
  exhaustive consumption by failed attempts. Physical attempts are separately
  recorded; rejected HTTP bodies are not all retained.
- The SROIE source contains nine exact-image cross-split pairs. Seven test images
  overlapping training/development were excluded before inference, leaving 340.
  Two historical training/development duplicate pairs remain a selection
  limitation. This audit does not establish absence of near-duplicates.
- Global `pip check` reports pre-existing conflicts for unrelated label-studio
  (requests/setuptools) and langchain-google-genai (langchain-core), plus an
  invalid `~uggingface-hub` distribution warning. These were not silently changed
  during model evaluation. The application and test results above ran in this
  environment; use a dedicated environment for reproducibility.

The implemented workflow is a local single-user prototype. This verification
does not claim a public deployment, a user study, or a completed real-data paper.
