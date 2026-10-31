from pathlib import Path
from fastapi import APIRouter
from config import settings
from services.extractor.field_mapper import DOC_TYPE_TO_MODEL
router = APIRouter()

@router.get("/capabilities")
def capabilities():
    models = {key: any((Path(settings.LAYOUTLM_MODEL_ROOT) / folder / name).is_file() for name in ("model.safetensors", "pytorch_model.bin"))
              for key, folder in DOC_TYPE_TO_MODEL.items()}
    from services.model_registry import status
    return {"model_status": status, "ocr_configured": bool(settings.GOOGLE_CLOUD_VISION_API_KEY),
            "hosted_configured": bool(settings.GROQ_API_KEY and settings.HOSTED_VLM_MODEL),
            "hosted_model": settings.HOSTED_VLM_MODEL or None,
            "layoutlm_weights_present": models,
            "database": "postgresql" if settings.DATABASE_URL.startswith("postgresql") else "sqlite",
            "review_threshold": settings.REVIEW_THRESHOLD, "fallback_threshold": settings.FALLBACK_THRESHOLD,
            "threshold_status": "Development settings; calibrate and freeze before paper experiments.",
            "max_upload_mb": settings.MAX_UPLOAD_MB}
