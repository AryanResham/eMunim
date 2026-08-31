from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import User
from services.settings_service import get_settings, settings_to_dict

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    business_name: str | None = None
    business_gstin: str | None = None
    business_address: str | None = None
    classifier_l1_threshold: float | None = Field(default=None, ge=0, le=1)
    classifier_l2_threshold: float | None = Field(default=None, ge=0, le=1)
    extractor_layoutlm_threshold: float | None = Field(default=None, ge=0, le=1)
    gst_tax_match_tolerance: float | None = Field(default=None, ge=0)
    gst_rate_match_tolerance: float | None = Field(default=None, ge=0)


@router.get("/settings")
def read_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return settings_to_dict(get_settings(db, current_user.id))


@router.put("/settings")
def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings_row = get_settings(db, current_user.id)
    updates = request.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(settings_row, key, value)
    db.commit()
    db.refresh(settings_row)
    return settings_to_dict(settings_row)
