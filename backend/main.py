from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import upload, ocr, classify, extract, validate, documents, capabilities, research

@asynccontextmanager
async def lifespan(app):
    from services.model_registry import preload_models
    await run_in_threadpool(preload_models)
    yield

app = FastAPI(title="eMunim API", version="0.1.0", lifespan=lifespan)
from routers import business
app.include_router(business.router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router,    prefix="/api")
app.include_router(ocr.router,       prefix="/api")
app.include_router(classify.router,  prefix="/api")
app.include_router(extract.router,   prefix="/api")
app.include_router(validate.router,  prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(capabilities.router, prefix="/api")
app.include_router(research.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/ready")
def ready():
    from fastapi.responses import JSONResponse
    from services.model_registry import status
    from services.extractor.field_mapper import DOC_TYPE_TO_MODEL
    missing = [kind for kind in DOC_TYPE_TO_MODEL if status['extractors'].get(kind) != 'ready']
    configured = bool(settings.GOOGLE_CLOUD_VISION_API_KEY)
    return JSONResponse(status_code=200 if configured and not missing else 503,
        content={"ready": configured and not missing, "ocr_provider": "google_vision",
                 "ocr_configured": configured, "unavailable_models": missing})
