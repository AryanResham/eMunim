import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from models.schemas import ExtractedField, ReviewPolicy
from services.storage import load_run, list_records, insert_record, upload_path
from services.validator.rules_engine import review_document, parse_amount
from services.field_contract import keys_for
router = APIRouter()

def records():
    try:
        return list_records()
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable. Check DATABASE_URL and initialize the database.")

class SaveRequest(BaseModel):
    run_id: str
    fields: list[ExtractedField]
    review_policy: ReviewPolicy = "validation_review"
    confirmed: bool = False
    override_reason: str = Field("", max_length=1000)

def values(fields):
    return {f["key"]: f.get("value") for f in fields}

@router.post("/documents")
def save_document(request: SaveRequest):
    if not request.confirmed:
        raise HTTPException(422, "Confirm review before saving.")
    try:
        run = load_run(request.run_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Extraction run not found.")
    submitted = [f.model_dump() for f in request.fields]
    if len(submitted) != len({f["key"] for f in submitted}) or set(values(submitted)) != set(keys_for(run["doc_type"])):
        raise HTTPException(422, "Fields must contain each schema key exactly once.")
    original = {f["key"]: f for f in run["fields"]}
    # Source/confidence are server-derived, never trusted from client.
    fields = []
    changes = []
    for f in submitted:
        before = original[f["key"]]
        changed = f["value"] != before.get("value")
        if changed:
            changes.append(dict(key=f["key"], before=before.get("value"), after=f["value"]))
        fields.append({**before, "value": f["value"], "source": "human" if changed else before.get("source", "missing"),
                       "confidence": None if changed else before.get("confidence")})
    metadata = run["metadata"]
    unchanged_conflicts = [key for key in metadata.get("conflicts", []) if not any(c["key"] == key for c in changes)]
    # Saving uses actual validation regardless of offline extraction-only comparator.
    validation = review_document(run["doc_type"], fields, "validation_review",
        metadata.get("operational_reasons"), unchanged_conflicts)
    existing = records()
    identity_key = next((k for k in ("invoice_no","bill_no","receipt_no","credit_note_no","debit_note_no","consumer_no") if k in values(fields)), "")
    current = values(fields)
    duplicate_ids = [r["id"] for r in existing if r["run_id"] != request.run_id and r["doc_type"] == run["doc_type"]
        and identity_key and current.get(identity_key)
        and str(values(r["fields"]).get(identity_key, "")).strip().casefold() == str(current[identity_key]).strip().casefold()
        and str(values(r["fields"]).get("vendor_name", values(r["fields"]).get("utility_provider",""))).strip().casefold() == str(current.get("vendor_name", current.get("utility_provider",""))).strip().casefold()
        and document_amount(fields) is not None and document_amount(r["fields"]) == document_amount(fields)]
    if duplicate_ids:
        validation["review_required"] = True
        validation["review_reasons"].append("Possible exact duplicate of " + ", ".join(duplicate_ids))
    if (validation["review_required"] or not validation["overall_passed"]) and not request.override_reason.strip():
        raise HTTPException(409, "Unresolved checks require an explicit review/override reason.")
    now = datetime.now(timezone.utc).isoformat()
    record = dict(id=str(uuid.uuid4()), run_id=request.run_id, file_id=run["file_id"],
        doc_type=run["doc_type"], pipeline=run["pipeline"], created_at=now,
        fields=fields, original_fields=run["fields"], line_items=run["line_items"],
        metadata=metadata, validation=validation, duplicate_ids=duplicate_ids,
        status="reviewed_with_issues" if validation["review_required"] else "reviewed",
        audit=[{"at":now, "action":"confirmed", "changes":changes, "reason":request.override_reason.strip()}])
    try:
        return insert_record(record)
    except SQLAlchemyError:
        raise HTTPException(503, "Could not save record. Check database availability.")

def document_amount(fields):
    data = values(fields)
    for key in ("total_amount","amount_due","credit_amount","debit_amount","amount"):
        if key in data:
            return parse_amount(data[key])
    return None

def filtered(doc_type=None, search="", pipeline=None):
    return [r for r in records() if (not doc_type or r["doc_type"] == doc_type)
        and (not pipeline or r["pipeline"] == pipeline)
        and (not search or search.casefold() in " ".join(str(f.get("value") or "") for f in r["fields"]).casefold())]

@router.get("/documents")
def list_documents(doc_type: str | None=None, search: str="", pipeline: str | None=None,
                   offset: int=Query(0, ge=0), limit: int=Query(25, ge=1, le=200)):
    rows = filtered(doc_type, search, pipeline)
    return {"items":rows[offset:offset+limit], "total":len(rows)}

@router.get("/documents/summary")
def summary():
    rows = records()
    groups = {}
    for row in rows:
        group = groups.setdefault(row["doc_type"], {"count":0,"printed_amount_total":Decimal(0),"amount_count":0})
        group["count"] += 1
        amount = document_amount(row["fields"])
        if amount is not None:
            group["printed_amount_total"] += amount
            group["amount_count"] += 1
    for group in groups.values():
        group["printed_amount_total"] = str(group["printed_amount_total"])
    return {"count":len(rows), "with_issues":sum(r["status"] == "reviewed_with_issues" for r in rows),
            "by_type":groups, "note":"Printed document amounts; not profit, cash flow or accounting postings."}

def csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

@router.get("/documents/export/csv")
def export(doc_type: str | None=None, search: str="", pipeline: str | None=None):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["record_id","created_at","document_type","pipeline","status","field","value","source"])
    for r in filtered(doc_type, search, pipeline):
        for f in r["fields"]:
            writer.writerow([csv_safe(v) for v in [r["id"],r["created_at"],r["doc_type"],r["pipeline"],r["status"],f["key"],f["value"],f["source"]]])
    return Response(stream.getvalue(), media_type="text/csv", headers={"Content-Disposition":'attachment; filename="emunim-records.csv"'})

@router.get("/documents/{document_id}")
def detail(document_id: str):
    for r in records():
        if r["id"] == document_id:
            return r
    raise HTTPException(404, "Record not found.")

@router.get("/files/{file_id}")
def source(file_id: str):
    try:
        path = upload_path(file_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Upload not found.")
    return FileResponse(path, media_type="image/jpeg")
