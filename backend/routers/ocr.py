import hashlib
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.storage import load_image, data_dir, write_json
from services.ocr_service import ocr_document, OCR_VERSION
from models.schemas import OCRResult
router = APIRouter()
class OCRRequest(BaseModel):
    file_id: str

@router.post("/ocr", response_model=OCRResult)
async def run_ocr(body: OCRRequest):
    try:
        image = load_image(body.file_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Upload not found.")
    key = hashlib.sha256(image + OCR_VERSION.encode()).hexdigest()
    path = data_dir() / "ocr_cache" / (key + ".json")
    if path.exists():
        return OCRResult.model_validate_json(path.read_text(encoding="utf-8"))
    result = await ocr_document(image)
    if not result.words or not result.full_text.strip():
        raise HTTPException(422, "No readable text detected.")
    write_json(path, result.model_dump())
    return result


