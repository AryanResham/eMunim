from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from deps.auth import get_current_user
from routers import upload, ocr, classify, extract, validate, documents, settings as settings_router, auth, vendors, insights

app = FastAPI(title="eMunim API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public — no auth required
app.include_router(auth.router, prefix="/api")

# Everything else requires a logged-in user
_auth_dep = [Depends(get_current_user)]
app.include_router(upload.router,    prefix="/api", dependencies=_auth_dep)
app.include_router(ocr.router,       prefix="/api", dependencies=_auth_dep)
app.include_router(classify.router,  prefix="/api", dependencies=_auth_dep)
app.include_router(extract.router,   prefix="/api", dependencies=_auth_dep)
app.include_router(validate.router,  prefix="/api", dependencies=_auth_dep)
app.include_router(documents.router, prefix="/api", dependencies=_auth_dep)
app.include_router(settings_router.router, prefix="/api", dependencies=_auth_dep)
app.include_router(vendors.router,   prefix="/api", dependencies=_auth_dep)
app.include_router(insights.router,  prefix="/api", dependencies=_auth_dep)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
