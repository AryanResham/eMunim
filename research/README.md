# Pipeline comparison and offline reliability replay

## Integrated measured suite (2026-10-24)

Start the application with `powershell -File scripts/start_app.ps1` and open
http://127.0.0.1:5173. Its Research page reads saved results; opening the page
does not initiate API calls. Definitions and unavailable measurements are in
[METRICS.md](METRICS.md).

Install evaluation dependencies with `python -m pip install -r research/requirements.txt`.
Retain the CUDA-enabled PyTorch installation. Checkpoint evaluation requires the
prepared datasets and exported models from `layoutLM__model`; it does not train
or download substitute checkpoints. The live pilot additionally requires the
configured Google Vision and hosted-model credentials from `backend/.env`.

Run the finite, resumable suite from the repository root:

```powershell
powershell -File scripts/launch_paper.ps1 -RunId paper-unique-run-id
```+

This evaluates 50 FUNSD test forms, 340 hash-filtered SROIE test receipts, and
150 synthetic test documents for each of six models. The live comparison uses
30 synthetic development documents and a disjoint 36-document synthetic test
cohort selected before inference. The development cohort selects thresholds;
the test cohort never selects them. All three pipeline arms use the same test
images and oracle document types; the classifier is measured separately. The
primary pipeline pilot uses actual Google OCR, whereas checkpoint evaluation
uses supplied text/boxes. These are separate experimental conditions.

The combined physical API-attempt budget is 220. Hosted results are not shared
between primary arms; retries and operational failures remain in the evidence.
Source, model and manifest hashes protect resumability. Do not change inference
or scoring code while a measured run is active. Reusing the same run ID resumes
compatible completed work; use a new ID for a changed protocol.

Outputs are under `backend/data/paper_runs/<run-id>/`: `status.json`, `report.md`,
`summary.json`, `tables.csv`, figures, dataset audit, checkpoint predictions,
pipeline raw responses, frozen policy, protocol and physical API ledger. The
latest index feeds the Research page. Failed runs retain their logs and status;
they are not silently replaced with successful results.

After a run completes, produce per-type tables, incremental C-versus-B review
counts, hybrid improvements/regressions and error examples without new inference:

```powershell
python scripts/summarize_paper.py backend/data/paper_runs/paper-unique-run-id
```

This writes `per_type.csv` and `supplementary_analysis.json`, with source/raw
hashes. Treat these as exploratory breakdowns: the pilot has only six test
documents per type. They do not select or replace the frozen policy.

The pinned SROIE source has nine exact-image cross-split pairs. Seven test images
overlapping training/development are excluded before scoring; two historical
train/development pairs remain a disclosed selection limitation. Synthetic
layouts are parametric families, not independently collected vendors. Zero
real-document annotations are verified at this update, so real Indian MSME
claims, real-data confidence calibration, measured billing, remote-server memory
and human time savings remain unavailable. Do not use synthetic ceiling scores
as evidence of real-world accuracy.

## Independently verified real-data workflow

Run from repository root after installing backend requirements. No script writes
to the LayoutLM folder; inference only reads configured checkpoints.

1. Inventory:
   python research/run.py inventory --out research/local/inventory.json
2. Manually create verified annotations following annotation_guide.md.
3. Validate:
   python research/run.py validate --manifest research/local/manifest.json
4. Copy policy.example.json, select thresholds on development data and set
   status to frozen before final test runs. Do not tune on final test labels.
5. Cached-only development run:
   python research/run.py run --manifest research/local/manifest.json --split development --policy research/local/policy.json --out research/local/dev-predictions.json
6. Live bounded final run:
   python research/run.py run --manifest research/local/manifest.json --split test --policy research/local/policy.json --out research/local/test-predictions.json --live --max-calls 100
7. Offline scoring:
   python research/run.py score --manifest research/local/manifest.json --split test --policy research/local/policy.json --predictions research/local/test-predictions.json --out research/local/report.json

The budget conservatively reserves maximum retries before each uncached hosted
request, and counts fresh OCR calls too. No automatic provider switching.
Failures remain in results; missing arms cannot be silently skipped.
JSON/Markdown reports include per-field F1, complete-document accuracy, failures,
review/detection/accepted-error metrics, source-limited confidence ablations,
review curves, usage, latency and paired document bootstrap intervals.
Use validation-only for the common cross-pipeline review comparison.

Review curves replay fixed outputs. Fallback-threshold curves require separate
development runs because routing changes extraction. Record measured charges
and dated provider rates separately: free quota is not zero deployment cost.
The runner does not invent memory, cost or human-time measurements; profile or
conduct a controlled study for those outcomes. Never present fixtures as results.
Real evaluation requires your independently verified labels, keys and models.

## Annotation workbench (start here)

No database or API key is needed for annotation. All working files below are
git-ignored. Import single-page images (convert PDF pages to images first):

```powershell
python research/annotate.py prepare --source raw_invoices
python research/annotate.py serve
```

Open http://127.0.0.1:8765. Select the document type, transcribe each value,
and mark every field reviewed, including genuinely absent fields. Assign
vendor and template groups separately; keep each group entirely in one split.
The additional `group` identifies the combined family used in the study.
Record the annotator and independent verifier where available. “Verified”
means all fields were manually checked; entering a verifier name alone is
not evidence of independent verification. Leave ambiguous cases as drafts
or excluded with notes. Save before switching documents. No model-generated
labels are prefilled. The server binds only to the local machine.

```powershell
python research/annotate.py export
python research/run.py validate --manifest research/local/manifest.json
```

Export includes only verified documents and checks image identity and split
leakage. Re-exporting replaces the manifest; finish annotation before adding
OCR paths or running experiments. Aim initially for 30–50 independently
checked invoices spanning several layouts, and describe this as a pilot.
The importer deduplicates normalized images; manually check near-duplicates.

## Isolate OCR effects

After final annotation export, capture Google OCR and create correction drafts.
This command makes at most the explicitly allowed number of fresh OCR calls;
rerunning reuses its existing Google files and preserves correction drafts:

```powershell
python research/ocr_inputs.py --manifest research/local/manifest.json --live --max-calls 50
```

Edit `research/local/ocr/*.corrected.json` against the image, correcting word
text, boxes, order and full_text. Boxes use normalized-image pixel coordinates,
not 0–1000 coordinates. Set `verified` to true only after checking. Do not add
field labels or answers to the OCR text. Image hashes and bounds are checked
before inference. Unverified corrected OCR remains an explicit failed local arm.

Copy `policy.example.json` to `research/local/policy.json`, select thresholds
using development data, then mark the policy frozen for final testing. Run:

```powershell
python research/run.py run --manifest research/local/manifest.json --split development --policy research/local/policy.json --out research/local/google.json --ocr-variant google --live --max-calls 100
python research/run.py run --manifest research/local/manifest.json --split development --policy research/local/policy.json --out research/local/corrected.json --ocr-variant corrected --live --max-calls 100
python research/compare_ocr.py --manifest research/local/manifest.json --google research/local/google.json --corrected research/local/corrected.json --out research/local/ocr-comparison.json
```

Use the existing `score` command separately for each output to obtain full
pipeline/reliability metrics. For final results replace `development` with
`test` only after freezing the policy. Run metadata records OCR variant and
per-document OCR hashes. Keep checkpoint/code/provider versions fixed between
paired runs. Google-versus-corrected comparison counts improved, regressed,
unchanged and failed pairs; it does not silently drop failures. Hosted-only
does not consume OCR and is a control (cached responses help keep it fixed).
Do not infer layout robustness from same-template synthetic performance.

## Repeatable system checks

```powershell
python -m pytest backend/tests -q -p no:cacheprovider --basetemp backend/data/test-temp
python scripts/verify_system.py
python scripts/verify_all_types.py --live
cd Frontend
npm run lint
npm run build
$env:EMUNIM_LIVE_E2E='1'
npm run test:e2e
```

`verify_system.py` uses an isolated SQLite database. `verify_all_types.py`
generates six documents with programmatic truth, makes at most six Google OCR
calls and 24 hosted attempts, spaces hosted calls, then runs both OCR variants
and scores all three review policies. It releases checkpoints between documents
with `--release-models` to bound memory. Results are diagnostic synthetic data,
not independently annotated real invoices or calibrated final-test results.

Browser checks use headless installed Chrome and isolated backend, frontend
and annotation servers. Without `EMUNIM_LIVE_E2E=1`, the three live extraction
tests are skipped. They verify upload, extraction, editing, review confirmation,
saving, record search and CSV download. Normal annotation files and database
are untouched. Reports and traces are in `backend/data/browser-tests/`.

Hosted cache hits are reported with zero fresh attempts. Shared P2/P3 caches
and paced requests deliberately affect measured latency and API usage in this
smoke audit; these numbers are not independent production cost/latency estimates.
Use declared cold-cache, isolated pipeline runs for a deployment-cost study.
The adapter respects provider Retry-After within a configurable wait bound;
longer cooldowns fail explicitly. Its optional spacing is per-process, not a
distributed quota limiter. See [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits).
