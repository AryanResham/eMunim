from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import User
from routers.upload import get_file_bytes
from utils.confidence_config import OCR_DEFAULT_WORD_CONFIDENCE
from services.extractor.layoutlm_extractor import extract_fields
from services.extractor.table_parser import parse_line_items
from services.settings_service import get_settings
from tests.layoutllm_real_flow import run_layoutllm_real_flow

router = APIRouter()


class OCRWordRequest(BaseModel):
    text: str
    bounding_box: list[list[int]]
    confidence: float = OCR_DEFAULT_WORD_CONFIDENCE


class OCRResultRequest(BaseModel):
    full_text: str
    words: list[OCRWordRequest]
    page_count: int = 1


class ExtractRequest(BaseModel):
    file_id: str
    doc_type: str
    ocr_result: OCRResultRequest
    model_type: str = "indian"


@router.post("/extract")
def extract(
    request: ExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_bytes = get_file_bytes(request.file_id)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="File not found — upload the file first via /api/upload")

    layoutlm_threshold = float(get_settings(db, current_user.id).extractor_layoutlm_threshold)

    # Determine image dimensions for bbox normalization
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    words = [w.text for w in request.ocr_result.words]
    bboxes_raw = [w.bounding_box for w in request.ocr_result.words]

    indian_fields = extract_fields(
        image_bytes=image_bytes,
        words=words,
        bboxes_raw=bboxes_raw,
        image_width=width,
        image_height=height,
        doc_type=request.doc_type,
        ocr_text=request.ocr_result.full_text,
        model_key="indian",
        confidence_threshold=layoutlm_threshold,
    )

    try:
        synthetic_fields = extract_fields(
            image_bytes=image_bytes,
            words=words,
            bboxes_raw=bboxes_raw,
            image_width=width,
            image_height=height,
            doc_type=request.doc_type,
            ocr_text=request.ocr_result.full_text,
            model_key="synthetic",
            confidence_threshold=layoutlm_threshold,
        )
        
        # Modify synthetic fields to avoid key collisions and make them distinguishable
        for f in synthetic_fields:
            f["key"] = f"synthetic_{f['key']}"
            f["label"] = f"{f['label']} (Synthetic)"
            
    except Exception as e:
        print(f"Failed to load synthetic model: {e}")
        synthetic_fields = []

    combined_fields = indian_fields + synthetic_fields

    line_items = parse_line_items(
        [w.model_dump() for w in request.ocr_result.words]
    )

    return {"fields": combined_fields, "line_items": line_items}


@router.post("/layoutllm-test-inference")
def layoutllm_test_inference(request: ExtractRequest):
    image_bytes = get_file_bytes(request.file_id)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="File not found - upload the file first via /api/upload")

    return run_layoutllm_real_flow(
        image_bytes=image_bytes,
        file_name=f"{request.file_id}.jpg",
        ocr_result=request.ocr_result.model_dump(),
        doc_type=request.doc_type,
    )
