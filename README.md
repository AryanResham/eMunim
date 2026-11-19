# eMunim

Accounting-document extraction, consistency checks, human review and durable records.
For deployment, model packaging, environment setup and persistent storage, see
[DEPLOYMENT.md](DEPLOYMENT.md). Model weights are distributed separately from Git.
The application supports JPEG/PNG images and six document types. Research begins
with independently labelled single-page English GST invoices.

## Extraction and reliability

| Pipeline | Input / engine |
| --- | --- |
| OCR + LayoutLM | Google Vision OCR plus one locally trained per-type checkpoint |
| Hosted vision | Image directly to Groq, no external OCR or local model required |
| Selective hybrid | Same LayoutLM path, with bounded hosted fallback for missing core values, low confidence or consistency failures |
| LLM/VLM cascade (`layoutlm_llm_vlm`) | Same LayoutLM path. Problems where the text was read (low confidence, failed value rules, a missing value whose kind appears in the OCR text) go to a hosted text LLM that selects OCR token ids; it cannot write values. Only text absent from the OCR output, or still missing after the LLM, goes to the hosted vision model |

Review policies are separate: extraction-only (offline comparator), validation,
and validation plus LayoutLM-confidence flags. Hosted confidence is unavailable,
not a fabricated probability. Rule flags never silently change values. The
hybrid preserves original candidates, replacement decisions, and disagreements.
Unresolved checks require an explicit acceptance note when saving.

The UI includes upload/type confirmation, editable review, validation reruns,
records, source images, audit history, document summaries and CSV export.
The Research page displays saved benchmark progress, measured tables, artifacts
and explicit unavailable metrics. It never starts billable experiments from the browser.
Classification means document type, not learned chart-of-accounts assignment.
Summaries of printed amounts are not profit, cash flow or accounting postings.

## Backend setup (PowerShell)

Use Python 3.11+ and a virtual environment.

    cd backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Edit backend/.env locally:

    GOOGLE_CLOUD_VISION_API_KEY=<your-key>
    GROQ_API_KEY=<your-key>
    HOSTED_VLM_MODEL=<image-capable-model-id-available-in-your-Groq-account>
    HOSTED_LLM_MODEL=<text-model-id-for-the-cascade-pipeline>

Groq configuration uses the image-input chat-completions endpoint documented at
https://console.groq.com/docs/vision. Confirm current model availability/quota in
your account. Do not use a text-only model. No Gemini/OpenAI key or local Qwen
weights are required. Keys never belong in the frontend.

Google Vision requires the service enabled and applicable billing/quota.
The backend OCR provider is Google Vision only (`OCR_PROVIDER=google_vision`).
Missing credentials return an explicit unavailable error; there is no local OCR
fallback. Historical local-OCR experiments are separate from the backend runtime.
Hosted inference uses bounded retries; it never silently changes providers.
Backend/data stores OCR/provider caches, original uploads and immutable extraction
runs. They can contain invoice information; keep them private and outside commits.

Restart the backend after changing environment settings or training checkpoints.

    python manage.py init-db
    python -m uvicorn main:app --host 127.0.0.1 --port 8000

The empty DATABASE_URL default uses local SQLite so the application can run
without a database server. For PostgreSQL, create a database and set:

    DATABASE_URL=postgresql://user:password@localhost:5432/emunim

Then run init-db. Schema v1 initialization is additive and version-recorded.
Future schema changes need explicit migrations; the app does not provision a
PostgreSQL server or create the database itself. PostgreSQL uses psycopg v3.co

## LayoutLM training handoff

The current synthetic training variants and measured limitations are documented in
[MODEL_CARD.md](MODEL_CARD.md). Export a selected release using the deployment
guide; model folders and training runs stay outside Git.

The CUDA FUNSD → SROIE → six synthetic-model training sequence is complete.
Inference reads per-type folders under LAYOUTLM_MODEL_ROOT (default:
`layoutLM__model`). See backend/services/extractor/field_mapper.py for mappings
and layoutLM__model/runs/cuda-20261024 for training evidence. Indian MSME data
was not used for training. A trained checkpoint is not proof of real-data quality.

Train and save weights plus config/tokenizer/processor there when ready.
The per-type checkpoint must have usable BIO labels aligned with its document
schema. Missing/unloadable weights produce an explicit unavailable error; the
pure baseline never silently becomes regex inference. Only local model files
are loaded; no LayoutLM weights are downloaded by the app.

Long documents use overlapping 512-token windows with word-level reconstruction.
Any lost word coverage is reported for review. `LAYOUTLM_DEVICE=auto` uses CUDA
when available; `cpu` and `cuda` explicitly select a device. The cache holds one
model and serializes local inference to bound memory. Settings reports file
presence; actual loading is checked at inference.

REVIEW_THRESHOLD and FALLBACK_THRESHOLD are development percentages. They are
not calibrated research operating points. Freeze thresholds using independent
development data before reporting final benchmark results.

## Frontend

    cd Frontend
    npm.cmd install
    npm.cmd run dev

Open the Vite URL. Its /api proxy targets 127.0.0.1:8000. For another backend,
set VITE_API_URL in Frontend/.env (only the public URL, never secrets).
Settings reports credential presence/model files; unavailable services remain
visible. Image-only hosted extraction can run while LayoutLM training is pending.

To start both local services without visible console windows from the repository
root: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_app.ps1`.
Open http://127.0.0.1:5173. Process identities/logs are in backend/data/app_runtime;
the launcher refuses occupied ports instead of killing unrelated services.

## API

- GET /api/health and /api/capabilities
- POST /api/upload (multipart JPEG/PNG)
- POST /api/ocr
- POST /api/classify
- POST /api/extract (pipeline and review_policy)
- POST /api/validate (current edited fields and review policy)
- POST /api/documents (run_id, full final fields, confirmed, override_reason)
- GET /api/documents (search, doc_type, pipeline, offset, limit)
- GET /api/documents/summary
- GET /api/documents/export/csv
- GET /api/documents/{id}
- GET /api/files/{file_id}
- GET /api/research/latest and /api/research/files/{published-artifact}

Saved values are revalidated server-side, and source/confidence are derived
from the stored original run. Changed values become human corrections.
Exact duplicate candidates require acknowledgement. CSV cells are escaped
against spreadsheet formulas.

This is a local single-user prototype. Authentication/multitenancy and protected
file-serving must be added before exposing it as a shared public service.

## Research and verification

See research/README.md, research/annotation_guide.md, and
PLAN_PIPELINES_RESEARCH.md. The runner compares all three pipelines and replays
review policies against saved outputs, with bounded opt-in live calls. It
reports failures instead of treating missing model/API results as success.
Real scores require manually verified labels, trained weights and API access;
fixture results are not research evidence.

Paper definitions: research/METRICS.md. The measured suite is launched with
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/launch_paper.ps1`.
It audits dataset identities, evaluates held-out public/synthetic checkpoints,
and runs a bounded 36-document live synthetic comparison after synthetic
development-only threshold selection. See backend/data/paper_runs/latest.json.
JSON/CSV/Markdown and SVG/PNG figures retain measured failures and missing evidence.
The pinned SROIE mirror contains exact cross-split duplicates: seven test images
are excluded by SHA-256 before scoring (340 retained); two historical
train/development duplicate pairs remain a disclosed training-selection limitation.
No real Indian MSME results, human time savings, remote-server memory, actual
monetary charges or PostgreSQL success are invented when evidence is missing.

    python -m pytest backend/tests layoutLM__model/tests -q -p no:cacheprovider
    cd Frontend
    npm.cmd run build

Tests mock provider/model boundaries and use isolated temporary SQLite storage.
No training, live paid calls, real-dataset annotation or PostgreSQL provisioning
is performed by these unit tests. `npm.cmd run test:e2e` separately exercises the
browser workflow with live configured providers and isolated test storage; it
can consume API quota. Those fixture records are not research measurements.


### Business onboarding and model startup

On first use, save your business legal/trade name, GSTINs (optional for unregistered businesses), and address. Edit them later in Settings. This is one shared business profile per installation, stored under DATA_DIR; it is not an account-scoped multi-tenant profile.

The backend loads all available per-type LayoutLM checkpoints and the locally cached classification model before accepting requests. Models remain cached for the lifetime of the process, so allow enough RAM/VRAM for all six checkpoints. Missing or unloadable checkpoints and classifier status appear in Settings. Startup does not download models or make paid hosted/OCR inference calls; remote models run through their configured provider when requested.

Upload, review the suggested classification, select whether your business is buyer or vendor, and explicitly confirm before extraction. Hosted extraction also uses automatic classification when OCR is configured; otherwise manually select and confirm a type. Only the confirmed document type's local model performs extraction (with the configured hosted fallback when selected).

The extraction API now requires `classification_confirmed: true` and a saved business profile. `business_role` is `buyer` or `vendor` (default buyer). GSTIN identity conflicts or insufficient evidence trigger review without silently rewriting extracted parties. Profile details are captured with each extraction for audit history.
