from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.upload import FILE_STORE
from services.extractor.layoutlm_extractor import extract_fields
from services.extractor.table_parser import parse_line_items
from tests.layoutllm_real_flow import run_layoutllm_real_flow

router = APIRouter()


class OCRWordRequest(BaseModel):
    text: str
    bounding_box: list[list[int]]
    confidence: float = 1.0


class OCRResultRequest(BaseModel):
    full_text: str
    words: list[OCRWordRequest]
    page_count: int = 1


class ExtractRequest(BaseModel):
    file_id: str
    doc_type: str
    ocr_result: OCRResultRequest


@router.post("/extract")
def extract(request: ExtractRequest):
    if request.file_id not in FILE_STORE:
        raise HTTPException(status_code=404, detail="File not found — upload the file first via /api/upload")

    image_bytes = FILE_STORE[request.file_id]

    # Determine image dimensions for bbox normalization
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size

    words = [w.text for w in request.ocr_result.words]
    bboxes_raw = [w.bounding_box for w in request.ocr_result.words]

    fields = extract_fields(
        image_bytes=image_bytes,
        words=words,
        bboxes_raw=bboxes_raw,
        image_width=width,
        image_height=height,
        doc_type=request.doc_type,
        ocr_text=request.ocr_result.full_text,
    )

    line_items = parse_line_items(
        [w.model_dump() for w in request.ocr_result.words]
    )

    return {"fields": fields, "line_items": line_items}


@router.post("/layoutllm-test-inference")
def layoutllm_test_inference(request: ExtractRequest):
    if request.file_id not in FILE_STORE:
        raise HTTPException(status_code=404, detail="File not found - upload the file first via /api/upload")

    image_bytes = FILE_STORE[request.file_id]

    return run_layoutllm_real_flow(
        image_bytes=image_bytes,
        file_name=f"{request.file_id}.jpg",
        ocr_result=request.ocr_result.model_dump(),
        doc_type=request.doc_type,
    )
