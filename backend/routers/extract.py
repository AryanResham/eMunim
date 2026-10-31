import io
from PIL import Image
from fastapi import APIRouter, HTTPException
from typing import Literal
from pydantic import BaseModel
from models.schemas import DocType, Pipeline, ReviewPolicy, OCRResult
from services.storage import load_image, save_run
from services.errors import HostedError, ServiceUnavailable
from services.extractor.pipeline import run_pipeline
router = APIRouter()
class ExtractRequest(BaseModel):
    classification_confirmed: bool = False
    business_role: Literal["buyer", "vendor"] = "buyer"
    file_id: str
    doc_type: DocType
    ocr_result: OCRResult | None = None
    pipeline: Pipeline = "ocr_layoutlm"
    review_policy: ReviewPolicy = "validation_review"

@router.post("/extract")
def extract(request: ExtractRequest):
    if not request.classification_confirmed:
        raise HTTPException(422, "Confirm the document classification before extraction.")
    from services.business_profile import load_profile, assess_parties
    profile = load_profile()
    if profile is None:
        raise HTTPException(422, "Complete business onboarding before extraction.")
    try:
        image = load_image(request.file_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Upload not found.")
    with Image.open(io.BytesIO(image)) as img:
        width, height = img.size
    try:
        result = run_pipeline(pipeline=request.pipeline, image_bytes=image,
            ocr_result=request.ocr_result.model_dump() if request.ocr_result else None,
            doc_type=request.doc_type.value, image_width=width, image_height=height,
            review_policy=request.review_policy)
    except (ServiceUnavailable, ImportError):
        raise HTTPException(503, "LayoutLM unavailable. Train/configure the per-type checkpoint and restart the backend.")
    except HostedError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    identity = assess_parties(result["fields"], profile, request.business_role)
    result["metadata"]["business_identity"] = identity
    result["metadata"]["business_profile"] = profile
    result["metadata"]["operational_reasons"].extend(identity["reasons"])
    from services.validator.rules_engine import review_document
    result["validation"] = review_document(request.doc_type.value, result["fields"], request.review_policy,
        result["metadata"]["operational_reasons"], result["metadata"]["conflicts"])
    result.update(file_id=request.file_id, doc_type=request.doc_type.value, review_policy=request.review_policy)
    return save_run(result)
