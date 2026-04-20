from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.classifier.classifier_pipeline import classify_document

router = APIRouter()


class ClassifyRequest(BaseModel):
    file_id: str
    ocr_text: str


@router.post("/classify")
def classify(request: ClassifyRequest):
    if not request.ocr_text.strip():
        raise HTTPException(status_code=422, detail="ocr_text is empty — run /api/ocr first")

    result = classify_document(request.ocr_text)
    return result
