import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import Document, FieldCorrection, StoredFile, User
from services.local_storage import read_file
from services.settings_service import get_settings
from services.validator.math_checker import parse_amount
from services.validator.rules_engine import validate_document
from services.vendor_service import vendor_key_expr_with_fallback
from services.direction_service import determine_direction

router = APIRouter()


def _avg_confidence(extraction_result: list | None) -> float | None:
    """Mean of ExtractedField.confidence (0-100) across a document's fields, or None if it has none."""
    if not extraction_result:
        return None
    confidences = [f.get("confidence") for f in extraction_result if isinstance(f, dict) and f.get("confidence") is not None]
    if not confidences:
        return None
    return round(sum(confidences) / len(confidences), 1)


@router.get("/documents")
def list_documents(
    doc_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    vendor_key: str | None = None,
    direction: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if from_date:
        query = query.filter(func.date(Document.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Document.created_at) <= to_date)
    if direction:
        query = query.filter(Document.direction == direction)
    if vendor_key:
        query = query.filter(vendor_key_expr_with_fallback(direction or "payable") == vendor_key)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Document.invoice_no.ilike(like),
                Document.vendor_name.ilike(like),
                Document.file_name.ilike(like),
            )
        )

    total = query.count()
    rows = (
        query.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "documents": [
            {
                "id": str(r.id),
                "file_id": r.file_id,
                "file_name": r.file_name,
                "doc_type": r.doc_type,
                "invoice_no": r.invoice_no,
                "vendor_name": r.vendor_name,
                "buyer_name": r.buyer_name,
                "direction": r.direction,
                "total_amount": float(r.total_amount) if r.total_amount is not None else None,
                "document_date": r.document_date,
                "overall_passed": r.overall_passed,
                "avg_confidence": _avg_confidence(r.extraction_result),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/documents/summary")
def documents_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(
            Document.doc_type,
            func.count(Document.id),
            func.coalesce(func.sum(Document.total_amount), 0),
        )
        .filter(Document.user_id == current_user.id)
        .group_by(Document.doc_type)
        .all()
    )
    return {
        "by_doc_type": [
            {"doc_type": doc_type, "count": count, "total_amount": float(total)}
            for doc_type, count, total in rows
        ]
    }


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = db.query(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_file = db.get(StoredFile, doc.file_id)
    corrections = (
        db.query(FieldCorrection)
        .filter(FieldCorrection.document_id == doc.id)
        .order_by(FieldCorrection.created_at.desc())
        .all()
    )

    return {
        "id": str(doc.id),
        "file_id": doc.file_id,
        "file_name": doc.file_name,
        "doc_type": doc.doc_type,
        "invoice_no": doc.invoice_no,
        "vendor_name": doc.vendor_name,
        "vendor_gstin": doc.vendor_gstin,
        "buyer_name": doc.buyer_name,
        "buyer_gstin": doc.buyer_gstin,
        "direction": doc.direction,
        "total_amount": float(doc.total_amount) if doc.total_amount is not None else None,
        "document_date": doc.document_date,
        "extracted_fields": doc.extracted_fields,
        "ocr_result": doc.ocr_result,
        "classification_result": doc.classification_result,
        "extraction_result": doc.extraction_result,
        "line_items": [
            {
                "description": li.description,
                "hsn_sac": li.hsn_sac,
                "quantity": li.quantity,
                "unit": li.unit,
                "rate": li.rate,
                "amount": li.amount,
            }
            for li in doc.line_items
        ],
        "validation_result": doc.validation_result,
        "overall_passed": doc.overall_passed,
        "created_at": doc.created_at.isoformat(),
        "has_original_file": stored_file is not None,
        "original_filename": stored_file.original_filename if stored_file else None,
        "mime_type": stored_file.mime_type if stored_file else None,
        "corrections": [
            {
                "field_name": c.field_name,
                "original_value": c.original_value,
                "corrected_value": c.corrected_value,
                "model_confidence": float(c.model_confidence) if c.model_confidence is not None else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in corrections
        ],
    }


class DocumentUpdateRequest(BaseModel):
    # Partial: only the fields the reviewer actually changed.
    fields: dict[str, str]
    # Manual override for when auto-detection got payable/receivable wrong
    # (e.g. the business GSTIN wasn't in Settings yet when this was extracted).
    # Omit to let it be recomputed automatically from the (possibly corrected) fields.
    direction: str | None = None


@router.put("/documents/{document_id}")
def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply reviewer corrections to a saved document's fields and re-run validation
    against them, so a fixed GSTIN or amount actually clears the rule that flagged it.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = db.query(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Confidence lookup for the correction log, keyed by the same stripped field name
    # extracted_fields uses (extraction_result keeps the raw model/synthetic key names).
    confidence_by_key: dict[str, float] = {}
    for entry in doc.extraction_result or []:
        key = entry["key"][10:] if entry["key"].startswith("synthetic_") else entry["key"]
        confidence_by_key[key] = entry.get("confidence")

    # Log every actual change as feedback data before overwriting it
    for field_name, new_value in request.fields.items():
        old_value = doc.extracted_fields.get(field_name, "")
        if old_value == new_value:
            continue
        db.add(FieldCorrection(
            document_id=doc.id,
            corrected_by=current_user.id,
            field_name=field_name,
            original_value=old_value,
            corrected_value=new_value,
            model_confidence=confidence_by_key.get(field_name),
        ))

    # Merge corrections into the stored field map
    updated_fields = {**doc.extracted_fields, **request.fields}
    doc.extracted_fields = updated_fields

    # Reflect corrected values into extraction_result too, so the full trace stays consistent
    extraction_result = doc.extraction_result or []
    for entry in extraction_result:
        key = entry["key"][10:] if entry["key"].startswith("synthetic_") else entry["key"]
        if key in request.fields:
            entry["value"] = request.fields[key]
    doc.extraction_result = extraction_result

    # Re-derive the pulled-out columns
    doc.invoice_no = updated_fields.get("invoice_no") or updated_fields.get("bill_no")
    doc.vendor_name = updated_fields.get("vendor_name")
    doc.vendor_gstin = updated_fields.get("vendor_gstin")
    doc.buyer_name = updated_fields.get("buyer_name")
    doc.buyer_gstin = updated_fields.get("buyer_gstin")
    doc.total_amount = parse_amount(updated_fields.get("total_amount") or updated_fields.get("amount"))
    doc.document_date = (
        updated_fields.get("invoice_date") or updated_fields.get("bill_date") or updated_fields.get("receipt_date")
    )

    # Re-run validation against the corrected fields
    settings_row = get_settings(db, current_user.id)
    doc.direction = (
        request.direction
        if request.direction in ("payable", "receivable")
        else determine_direction(updated_fields, settings_row.business_gstin)
    )
    result = validate_document(
        doc.doc_type,
        updated_fields,
        db=db,
        user_id=current_user.id,
        gst_tax_match_tolerance=float(settings_row.gst_tax_match_tolerance),
        gst_rate_match_tolerance=float(settings_row.gst_rate_match_tolerance),
        exclude_document_id=doc.id,
        direction=doc.direction,
    )
    doc.validation_result = result
    doc.overall_passed = result["overall_passed"]

    db.commit()
    db.refresh(doc)

    return get_document(document_id, db, current_user)


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = db.query(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_file = db.get(StoredFile, doc.file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="Original file was not retained for this document")

    content = read_file(doc.file_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Original file is missing from storage")

    return StreamingResponse(io.BytesIO(content), media_type=stored_file.mime_type or "application/octet-stream")
