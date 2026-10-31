from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.schemas import DocType, ExtractedField, ReviewPolicy, ValidationResult
from services.validator.rules_engine import review_document
from services.storage import load_run
from services.field_contract import keys_for

router = APIRouter()

class ValidateRequest(BaseModel):
    doc_type: DocType
    fields: list[ExtractedField]
    policy: ReviewPolicy = "validation_review"
    run_id: str | None = None

@router.post("/validate", response_model=ValidationResult)
def validate(request: ValidateRequest):
    fields = [f.model_dump() for f in request.fields]
    if len(fields) != len({f['key'] for f in fields}) or {f['key'] for f in fields} != set(keys_for(request.doc_type.value)):
        raise HTTPException(422, "Include each document field exactly once.")
    operational, conflicts = [], []
    if request.run_id:
        try:
            run = load_run(request.run_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Extraction run not found.")
        if run['doc_type'] != request.doc_type.value:
            raise HTTPException(422, "Document type differs from the original run.")
        original = {f['key']: f for f in run['fields']}
        for field in fields:
            before = original[field['key']]
            changed = field['value'] != before.get('value')
            field.update(source='human' if changed else before.get('source', 'missing'), confidence=None if changed else before.get('confidence'))
        operational = run['metadata'].get('operational_reasons', [])
        conflicts = [k for k in run['metadata'].get('conflicts', []) if original[k].get('value') == next(f['value'] for f in fields if f['key'] == k)]
    return review_document(request.doc_type.value, fields, request.policy, operational, conflicts)
