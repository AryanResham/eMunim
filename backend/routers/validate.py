from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import Document, DocumentLineItem, User
from models.schemas import DocType, ValidationResult, ExtractedField, OCRResult, ClassificationResult, LineItem
from services.validator.math_checker import parse_amount
from services.validator.rules_engine import validate_document
from services.settings_service import get_settings
from services.direction_service import determine_direction

router = APIRouter()

class ValidateRequest(BaseModel):
    doc_type: DocType
    fields: list[ExtractedField]
    file_id: str = ""
    file_name: str = ""
    # Optional — carried through from earlier stages purely for persistence/traceability.
    # Validation itself only ever looks at `fields`.
    ocr_result: OCRResult | None = None
    classification_result: ClassificationResult | None = None
    line_items: list[LineItem] = []

@router.post("/validate", response_model=ValidationResult)
async def validate_document_endpoint(
    request: ValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Receive extracted fields, run the rule-based validation engine,
    and persist the document (so future duplicate checks can see it).
    """
    # Convert list[ExtractedField] -> dict[str, str] for the rules engine
    fields_dict = {}
    for f in request.fields:
        key = f.key
        if key.startswith("synthetic_"):
            key = key[10:]
        fields_dict[key] = f.value

    # Run validation
    settings_row = get_settings(db, current_user.id)
    direction = determine_direction(fields_dict, settings_row.business_gstin)
    result = validate_document(
        request.doc_type,
        fields_dict,
        db=db,
        user_id=current_user.id,
        gst_tax_match_tolerance=float(settings_row.gst_tax_match_tolerance),
        gst_rate_match_tolerance=float(settings_row.gst_rate_match_tolerance),
        direction=direction,
    )

    # Persist the document
    invoice_no = fields_dict.get("invoice_no") or fields_dict.get("bill_no")
    document_date = fields_dict.get("invoice_date") or fields_dict.get("bill_date") or fields_dict.get("receipt_date")
    total_amount = parse_amount(fields_dict.get("total_amount") or fields_dict.get("amount"))

    doc = Document(
        user_id=current_user.id,
        file_id=request.file_id,
        file_name=request.file_name,
        doc_type=request.doc_type.value,
        invoice_no=invoice_no,
        vendor_name=fields_dict.get("vendor_name"),
        vendor_gstin=fields_dict.get("vendor_gstin"),
        buyer_name=fields_dict.get("buyer_name"),
        buyer_gstin=fields_dict.get("buyer_gstin"),
        direction=direction,
        total_amount=total_amount,
        document_date=document_date,
        extracted_fields=fields_dict,
        classification_confidence=request.classification_result.confidence if request.classification_result else None,
        classifier_level=request.classification_result.classifier_level if request.classification_result else None,
        ocr_result=request.ocr_result.model_dump() if request.ocr_result else {},
        classification_result=request.classification_result.model_dump() if request.classification_result else {},
        extraction_result=[f.model_dump() for f in request.fields],
        validation_result=result,
        overall_passed=result["overall_passed"],
    )
    db.add(doc)
    db.flush()  # assign doc.id before attaching line items

    for i, item in enumerate(request.line_items):
        db.add(DocumentLineItem(
            document_id=doc.id,
            sort_order=i,
            description=item.description,
            hsn_sac=item.hsn_sac,
            quantity=item.quantity,
            unit=item.unit,
            rate=item.rate,
            amount=item.amount,
        ))

    db.commit()

    return result
