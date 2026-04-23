import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from routers.upload import FILE_STORE
from services.ocr_service import ocr_document
from models.schemas import OCRResult

router = APIRouter()

OCR_RESULTS_DIR = Path("data/ocr_results")
OCR_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class OCRRequest(BaseModel):
    file_id: str




@router.post("/ocr", response_model=OCRResult)
async def run_ocr(body: OCRRequest):
    image_bytes = FILE_STORE.get(body.file_id)
    if image_bytes is None:
        raise HTTPException(404, "File not found — upload the file first via /api/upload")

    result = await ocr_document(image_bytes)
    
    # Save to disk
    result_path = OCR_RESULTS_DIR / f"{body.file_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
        
    return result


