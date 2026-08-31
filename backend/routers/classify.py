from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import User
from services.classifier.classifier_pipeline import classify_document
from services.settings_service import get_settings

router = APIRouter()


class ClassifyRequest(BaseModel):
    file_id: str
    ocr_text: str


@router.post("/classify")
def classify(
    request: ClassifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.ocr_text.strip():
        raise HTTPException(status_code=422, detail="ocr_text is empty — run /api/ocr first")

    settings_row = get_settings(db, current_user.id)
    result = classify_document(
        request.ocr_text,
        l1_threshold=float(settings_row.classifier_l1_threshold),
        l2_threshold=float(settings_row.classifier_l2_threshold),
    )
    return result
