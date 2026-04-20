# ============================================================
# CHAITYA — routers/validate.py
# ============================================================
#
# PURPOSE:
#   Receive extracted fields from the frontend and run the
#   rule-based validation engine. Return pass/fail results.
#
# ENDPOINT TO IMPLEMENT:
#
#   POST /api/validate
#   Request body (JSON):
#       {
#           "doc_type": "GST_INVOICE",        ← one of the 6 DocType values
#           "fields": {                        ← key-value dict of extracted fields
#               "vendor_gstin": "27AABCU9603R1ZM",
#               "total_amount": "₹33,630.00",
#               ...
#           }
#       }
#
#   - Call validate_document(doc_type, fields, db=None) from services.validator.rules_engine
#   - Return the ValidationResult directly
#
#   NOTE on db:
#       Pass db=None for now (duplicate detection stub doesn't need it).
#       When Phase 5 is ready, add: db: Session = Depends(get_db)
#       and pass it to validate_document().
#
# IMPORTS YOU WILL NEED:
#   from fastapi import APIRouter
#   from pydantic import BaseModel
#   from models.schemas import DocType, ValidationResult
#   from services.validator.rules_engine import validate_document

from fastapi import APIRouter

router = APIRouter()


@router.post("/validate")
async def validate_document_endpoint():
    # TODO: implement validation endpoint
    return {"status": "not implemented"}
