from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter
from config import settings
from services.extractor.field_mapper import DOC_TYPE_TO_MODEL
router = APIRouter()

@router.get("/capabilities")
def capabilities():
    models = {key: any((Path(settings.LAYOUTLM_MODEL_ROOT) / folder / name).is_file() for name in ("model.safetensors", "pytorch_model.bin"))
              for key, folder in DOC_TYPE_TO_MODEL.items()}
    from services.model_registry import status
    ocr_configured = bool(settings.GOOGLE_CLOUD_VISION_API_KEY)
    return {"model_status": status, "ocr_configured": ocr_configured, "ocr_provider": settings.OCR_PROVIDER,
            "hosted_configured": bool(settings.GROQ_API_KEY and settings.HOSTED_VLM_MODEL),
            "hosted_model": settings.HOSTED_VLM_MODEL or None,
            "hosted_llm_configured": bool((settings.HOSTED_LLM_API_KEY or settings.GROQ_API_KEY) and settings.HOSTED_LLM_MODEL),
            "hosted_llm_model": settings.HOSTED_LLM_MODEL or None,
            "hosted_llm_provider": urlparse(settings.HOSTED_LLM_BASE_URL or settings.HOSTED_VLM_BASE_URL).hostname,
            "layoutlm_weights_present": models,
            "database": "postgresql" if settings.DATABASE_URL.startswith("postgresql") else "sqlite",
            "review_threshold": settings.REVIEW_THRESHOLD, "fallback_threshold": settings.FALLBACK_THRESHOLD,
            "threshold_status": "Development settings; calibrate and freeze before paper experiments.",
            "max_upload_mb": settings.MAX_UPLOAD_MB}
