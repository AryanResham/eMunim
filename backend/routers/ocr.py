from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from routers.upload import FILE_STORE
from services.ocr_service import ocr_document
from models.schemas import OCRResult

router = APIRouter()


class OCRRequest(BaseModel):
    file_id: str


@router.post("/ocr", response_model=OCRResult)
async def run_ocr(body: OCRRequest):
    image_bytes = FILE_STORE.get(body.file_id)
    if image_bytes is None:
        raise HTTPException(404, "File not found — upload the file first via /api/upload")

    return await ocr_document(image_bytes)
