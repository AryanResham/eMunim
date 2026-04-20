from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import upload, ocr, classify, extract, validate, documents

app = FastAPI(title="eMunim API", version="0.1.0")

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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
