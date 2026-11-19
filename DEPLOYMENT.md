# Deploying eMunim

The deployable product is `Frontend/` (React/Vite) and `backend/` (FastAPI).
Google Vision supplies OCR. Six local LayoutLMv3 checkpoints tag fields by document
type. Validation, business onboarding and human review precede saving records.
Groq-hosted vision/hybrid extraction is optional. Research scripts and training
datasets are not needed inside the application containers.

## Code and model releases are separate

GitHub holds source, tests, environment examples and deployment configuration.
It must not hold API keys, uploaded invoices, databases, datasets or checkpoints.
Each inference checkpoint needs its tokenizer, image processor and config alongside
`model.safetensors`. Copying only weights will not work.

Use `scripts/export_model_bundle.py` to create a runtime-only ZIP. It validates all
six label schemas, excludes optimizer checkpoints and training reports, and writes
a SHA-256 manifest. It does not choose a model version or upload anything.

Examples from the local workspace, run at repository root:

```powershell
# Inspect either release before deciding which to deploy.
python scripts/export_model_bundle.py --model-root layoutLM__model/runs/ocr-augmented-20261119/models --check-only
python scripts/export_model_bundle.py --model-root layoutLM__model/runs/identifier-pilot-20261119/models --check-only

# After selecting a release, export it. This example exports the identifier run;
# it is not a recommendation to activate it over the previous checkpoints.
python scripts/export_model_bundle.py --model-root layoutLM__model/runs/identifier-pilot-20261119/models --output deploy_artifacts/identifier-v2.zip
```

Both releases have six models. The previous weights plus the compound fix scored
87.50% on the cached-Vision synthetic cohort; identifier-v2 scored 85.88% on that
same cohort. Identifier-v2 scored 82.57% on a different, RapidOCR-based synthetic
cohort. These are supported populated-field accuracies, not real-invoice quality,
classifier accuracy or a direct comparison of OCR engines. Do not select individual
models from test scores; choose on development data and validate the final bundle.
The local experiment releases have not been automatically activated.

Transfer the selected ZIP privately to the server (SSH/SCP or private artifact
storage). For example:

```bash
mkdir -p /srv/emunim/model_artifacts
python -m zipfile -e identifier-v2.zip /srv/emunim/model_artifacts
python scripts/export_model_bundle.py --model-root /srv/emunim/model_artifacts --verify
```

Expected layout:

```text
model_artifacts/
  model_bundle_manifest.json
  layoutlm-synthetic-tax_invoice-trained/
  layoutlm-synthetic-purchase_bill-trained/
  layoutlm-synthetic-expense_receipt-trained/
  layoutlm-synthetic-utility_bill-trained/
  layoutlm-synthetic-credit_note-trained/
  layoutlm-synthetic-debit_note-trained/
```

The backend mounts this directory read-only at `/models` and sets
`LAYOUTLM_MODEL_ROOT=/models`. Inference loads local files only. It never trains or
downloads LayoutLM models at startup. To release another model version, deploy a
new verified directory, change `MODEL_HOST_PATH`, and recreate the backend. Keep
the previous directory for rollback.

## Run the containers

Install Docker Engine and Compose on a Linux server. This configuration starts
with CPU inference and one API worker. All six checkpoints are preloaded, so each
additional worker duplicates model memory. A 16 GB RAM CPU host is a conservative
starting estimate, not a measured capacity guarantee; measure latency and memory
before choosing a production instance. GPU deployment needs a separate CUDA image
and NVIDIA runtime; this CPU image does not become GPU-capable by changing an env var.

```bash
cp deploy/backend.env.example deploy/backend.env
cp deploy/compose.env.example deploy/compose.env
# Edit both local files: Vision key, model directory, and allowed browser origins.
docker compose --env-file deploy/compose.env config --quiet
docker compose --env-file deploy/compose.env up -d --build
docker compose --env-file deploy/compose.env logs -f backend
```

The frontend is served at `http://127.0.0.1:8080` on the host. Nginx serves the built
React app and proxies `/api/` to FastAPI, so the Vite development proxy is not needed
in production. Use an SSH tunnel for a private demo. Before internet exposure,
put an HTTPS reverse proxy and access control in front: the current app is a
single-workspace application without user authentication or tenant isolation.

`/api/health` is process liveness. `/api/ready` requires all six extraction models
to be loaded and a configured Vision key. It does not perform a billable OCR call
or prove that the key/billing/quota works. Compose waits for readiness before
starting the frontend. Check `/api/capabilities` for model status.

Google Vision is the only backend OCR provider. Put its key in `deploy/backend.env`,
never in frontend `VITE_*` variables or Docker build arguments. Groq configuration
is only needed for hosted/hybrid pipelines. Nothing in the build runs paid APIs.

## Storage and optional classifier

The `app_data` named volume keeps uploads, extraction records and the default
SQLite database across container replacements. Back it up. Do not use
`docker compose down -v` unless deleting that data is intended. For PostgreSQL,
set `DATABASE_URL`, but uploads still need the persistent application volume.
This single-host design is not yet a horizontally scaled multi-tenant service.

The optional zero-shot classifier uses `cross-encoder/nli-deberta-v3-small` from
the Hugging Face cache. If absent, rule classification and manual selection remain
available. To provision it once into the persistent `hf_cache` volume:

```bash
docker compose --env-file deploy/compose.env run --rm -e HF_HUB_OFFLINE=0 backend \
  python -c "from huggingface_hub import snapshot_download; snapshot_download('cross-encoder/nli-deberta-v3-small')"
docker compose --env-file deploy/compose.env restart backend
```

The application then runs with `HF_HUB_OFFLINE=1`. Hugging Face also supports private,
revision-pinned model repositories if that is chosen instead of SCP:
https://huggingface.co/docs/huggingface_hub/en/guides/download

Compose volume and readiness behavior:
https://docs.docker.com/compose/how-tos/startup-order/

## Build verification

```bash
python -m pytest backend/tests scripts/tests -q
cd Frontend && npm ci && npm run build && npm run lint
```

The initial preparation machine has Docker CLI installed but its engine is not
running and the Compose command is unavailable. Image builds, Compose CLI
validation and live container smoke tests therefore remain to be run on a
Docker/Compose-enabled host. Frontend build/lint, 88 backend/tool tests and
inspection of all six checkpoint folders passed locally. The inspected runtime
release totals approximately 3.04 GB; training state is excluded.
