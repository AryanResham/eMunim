from fastapi import APIRouter
from pydantic import BaseModel
from models.schemas import DocType, ValidationResult, ExtractedField
from services.validator.rules_engine import validate_document

router = APIRouter()

class ValidateRequest(BaseModel):
    doc_type: DocType
    fields: list[ExtractedField]

@router.post("/validate", response_model=ValidationResult)
async def validate_document_endpoint(request: ValidateRequest):
    """
    Receive extracted fields and run the rule-based validation engine.
    """
    # Convert list[ExtractedField] -> dict[str, str] for the rules engine
    fields_dict = {}
    for f in request.fields:
        key = f.key
        if key.startswith("synthetic_"):
            key = key[10:]
        fields_dict[key] = f.value

    # Run validation
    result = validate_document(request.doc_type, fields_dict, db=None)
    
    return result
