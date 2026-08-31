"""
Document-level intelligence that isn't strictly "spend" analytics:
credit/debit note netting against the vendor's invoices, and a queue of
documents whose extraction confidence was too low to trust without a
second look.
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from models.db_models import Document
from services.validator.math_checker import parse_amount
from services.vendor_service import vendor_key_expr

# A vendor's credit-note rate (credit notes / invoices) above this counts as
# unusually high and worth a callout — roughly double what you'd expect from
# ordinary returns/adjustments.
_HIGH_CREDIT_NOTE_RATE = 0.15

# ExtractedField.confidence is stored 0-100 (utils/confidence_config.format_confidence
# converts the model's 0-1 softmax score before it's ever serialized). Below this,
# a field counts as "low confidence" and the document is worth a second look —
# matches the tier boundary DocumentReview.tsx already uses for its per-field colors.
_LOW_CONFIDENCE_THRESHOLD = 70.0


def get_credit_debit_netting(db: Session, user_id) -> list[dict]:
    key = vendor_key_expr()
    rows = (
        db.query(key.label("vendor_key"), Document.vendor_name, Document.doc_type, Document.total_amount, Document.extracted_fields)
        .filter(
            Document.user_id == user_id,
            Document.doc_type.in_(["GST_INVOICE", "PURCHASE_BILL", "CREDIT_NOTE", "DEBIT_NOTE"]),
            # A receivable GST_INVOICE is a sale the business made, not a vendor
            # bill — netting it against credit/debit notes here would be nonsense.
            Document.direction == "payable",
        )
        .all()
    )

    vendor_names: dict[str, str] = {}
    invoiced = defaultdict(float)
    credited = defaultdict(float)
    debited = defaultdict(float)
    invoice_count = defaultdict(int)
    credit_note_count = defaultdict(int)

    for vendor_key, vendor_name, doc_type, total_amount, fields in rows:
        if vendor_key is None:
            continue
        vendor_names.setdefault(vendor_key, vendor_name or vendor_key)
        fields = fields or {}

        if doc_type in ("GST_INVOICE", "PURCHASE_BILL"):
            invoice_count[vendor_key] += 1
            if total_amount is not None:
                invoiced[vendor_key] += float(total_amount)
        elif doc_type == "CREDIT_NOTE":
            credit_note_count[vendor_key] += 1
            amt = parse_amount(fields.get("credit_amount", "0")) or 0
            credited[vendor_key] += float(amt)
        elif doc_type == "DEBIT_NOTE":
            amt = parse_amount(fields.get("debit_amount", "0")) or 0
            debited[vendor_key] += float(amt)

    results = []
    for vendor_key in vendor_names:
        if credit_note_count[vendor_key] == 0 and debited[vendor_key] == 0:
            continue  # nothing to net — no point cluttering the list
        net_payable = invoiced[vendor_key] - credited[vendor_key] + debited[vendor_key]
        credit_note_rate = credit_note_count[vendor_key] / invoice_count[vendor_key] if invoice_count[vendor_key] else None
        results.append(
            {
                "vendor_key": vendor_key,
                "name": vendor_names[vendor_key],
                "invoiced_total": round(invoiced[vendor_key], 2),
                "credited_total": round(credited[vendor_key], 2),
                "debited_total": round(debited[vendor_key], 2),
                "net_payable": round(net_payable, 2),
                "credit_note_count": credit_note_count[vendor_key],
                "credit_note_rate": round(credit_note_rate, 3) if credit_note_rate is not None else None,
                "high_credit_note_rate": bool(credit_note_rate and credit_note_rate > _HIGH_CREDIT_NOTE_RATE),
            }
        )

    results.sort(key=lambda r: r["net_payable"], reverse=True)
    return results


def get_low_confidence_queue(db: Session, user_id, limit: int = 20) -> list[dict]:
    rows = (
        db.query(Document.id, Document.vendor_name, Document.doc_type, Document.extraction_result, Document.created_at)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    results = []
    for doc_id, vendor_name, doc_type, extraction_result, created_at in rows:
        fields = extraction_result or []
        confidences = [f.get("confidence") for f in fields if isinstance(f, dict) and f.get("confidence") is not None]
        if not confidences:
            continue
        avg_confidence = sum(confidences) / len(confidences)
        if avg_confidence >= _LOW_CONFIDENCE_THRESHOLD:
            continue
        low_field_count = sum(1 for c in confidences if c < _LOW_CONFIDENCE_THRESHOLD)
        results.append(
            {
                "document_id": str(doc_id),
                "vendor_name": vendor_name or "Unknown vendor",
                "doc_type": doc_type,
                "avg_confidence": round(avg_confidence, 1),
                "low_confidence_field_count": low_field_count,
                "created_at": created_at.isoformat(),
            }
        )

    results.sort(key=lambda r: r["avg_confidence"])
    return results[:limit]
