# ============================================================
# ARYAN — routers/ocr.py
# ============================================================
#
# PURPOSE:
#   Accept a file_id (from /api/upload), retrieve the stored image bytes,
#   run OCR, and return structured word + bounding-box data.
#
# ENDPOINT TO IMPLEMENT:
#
#   POST /api/ocr
#   Request body (JSON): { "file_id": str }
#   - Look up file_id in FILE_STORE imported from routers.upload
#     If not found: raise HTTPException(status_code=404, detail="File not found")
#   - Call ocr_document(image_bytes) from services.ocr_service
#   - Return OCRResult directly (FastAPI serializes it to JSON)
#
# IMPORTANT — bounding box format:
#   Cloud Vision returns vertices as [{"x":...,"y":...}, ...] (4 points)
#   Normalize to: list[list[int]] shape (4, 2) → [[x,y],[x,y],[x,y],[x,y]]
#   This normalization happens inside ocr_service.py, NOT here.
#
# IMPORTS YOU WILL NEED:
#   from fastapi import APIRouter, HTTPException
#   from pydantic import BaseModel
#   from routers.upload import FILE_STORE
#   from services.ocr_service import ocr_document
#   from models.schemas import OCRResult

from fastapi import APIRouter

router = APIRouter()


@router.post("/ocr")
async def run_ocr():
    # TODO: implement OCR endpoint
    return {"status": "not implemented"}
