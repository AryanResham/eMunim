from sqlalchemy.orm import Session

from models.db_models import AppSettings


def get_settings(db: Session, user_id) -> AppSettings:
    """Fetch this user's settings row, creating it with defaults if missing."""
    settings_row = db.get(AppSettings, user_id)
    if settings_row is None:
        settings_row = AppSettings(user_id=user_id)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


def settings_to_dict(settings_row: AppSettings) -> dict:
    return {
        "business_name": settings_row.business_name,
        "business_gstin": settings_row.business_gstin,
        "business_address": settings_row.business_address,
        "classifier_l1_threshold": float(settings_row.classifier_l1_threshold),
        "classifier_l2_threshold": float(settings_row.classifier_l2_threshold),
        "extractor_layoutlm_threshold": float(settings_row.extractor_layoutlm_threshold),
        "gst_tax_match_tolerance": float(settings_row.gst_tax_match_tolerance),
        "gst_rate_match_tolerance": float(settings_row.gst_rate_match_tolerance),
        "updated_at": settings_row.updated_at.isoformat(),
    }
