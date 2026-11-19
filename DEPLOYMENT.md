# eMunim: deployment instructions

You need the code from GitHub, the model ZIP already shared with you, and a Google
Vision API key. The ZIP contains all six trained models. No training is required.
The separate SHA file is optional and is not needed to extract or run the models.

Use a Linux server with Git, unzip, Docker Engine and Docker Compose installed.
The supplied setup runs on CPU; a GPU is not required. Around 16 GB RAM is a
recommended starting point, subject to performance testing. Allow disk space for
the 3 GB ZIP, its extracted contents, Docker images and uploaded documents.

## 1. Get the code

```bash
git clone https://github.com/AryanResham/eMunim.git
cd eMunim
```

Run all remaining commands from this `eMunim` directory.

## 2. Extract the model ZIP

Upload `emunim-identifier-v2-models.zip` into the `eMunim` directory, then run:

```bash
mkdir -p model_artifacts
unzip emunim-identifier-v2-models.zip -d model_artifacts
```

The `model_artifacts` directory should now directly contain six folders named
`layoutlm-synthetic-...-trained`, plus a manifest file. Keep all the files inside
each model folder together. The ZIP is ready to use as supplied.

## 3. Add the Google Vision key

```bash
cp deploy/backend.env.example deploy/backend.env
cp deploy/compose.env.example deploy/compose.env
```

Open `deploy/backend.env` in an editor and fill in:

```dotenv
GOOGLE_CLOUD_VISION_API_KEY=your_actual_key
```

Use a key with Google Cloud Vision enabled and working billing/quota. Leave the
other settings as supplied for the basic application. Groq settings are optional,
only for the hosted/hybrid extraction options. Keep the real key out of GitHub.

`deploy/compose.env` already points to `./model_artifacts`, so no path changes are
needed if you followed step 2.

## 4. Start the application

```bash
docker compose --env-file deploy/compose.env up -d --build
```

The first build downloads dependencies and can take several minutes. Startup
loads the six models; the frontend waits until the backend is ready.

```bash
docker compose --env-file deploy/compose.env ps
curl -f http://127.0.0.1:8080/api/ready
```

Once ready, open **http://localhost:8080** on the server. Complete business
onboarding in the app, then upload a test invoice and check the extracted fields.
The readiness check confirms model loading and key presence; uploading an invoice
also tests the actual Google Vision connection and may incur its normal API charge.

If the server is remote, run this on your own computer and keep it open:

```bash
ssh -L 8080:127.0.0.1:8080 your_user@SERVER_IP
```

Then open **http://localhost:8080** on your computer.

For a public domain, put an HTTPS reverse proxy with access control in front of
`127.0.0.1:8080`. The current app has one shared workspace and no user login; the
default setup therefore listens locally rather than exposing invoice data publicly.

## If something does not work

View the backend log:

```bash
docker compose --env-file deploy/compose.env logs --tail=100 backend
```

| Problem | Check |
|---|---|
| Missing models or backend not ready | `model_artifacts` must directly contain all six extracted model folders, including their weights, config and tokenizer files. |
| OCR unavailable | Check the Vision key, enabled API, billing and quota. The backend uses Google Vision only. |
| Cannot open the app remotely | Use the SSH tunnel above, or configure the host's HTTPS reverse proxy. |

After correcting an environment setting, recreate the containers:

```bash
docker compose --env-file deploy/compose.env up -d --force-recreate
```

Uploaded documents and the default database are kept in Docker's `app_data`
volume. Preserve and back up that volume; do not use `docker compose down -v`
unless you intend to delete the stored data.

For background on the models and their measured limitations, see
[MODEL_CARD.md](MODEL_CARD.md). Container builds and live deployment still need
to be verified on the target server; they were not run on the preparation machine.
