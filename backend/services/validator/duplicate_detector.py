import difflib
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from models.db_models import Document
from services.validator.math_checker import parse_amount

# Scoring weights — tuned so an exact invoice-number match alone is already
# a near-certain duplicate, while everything else needs to stack up.
_SCORE_INVOICE_NO_EXACT = 50
_SCORE_INVOICE_NO_FUZZY = 30
_SCORE_GSTIN_MATCH = 25
_SCORE_AMOUNT_EXACT = 15
_SCORE_AMOUNT_CLOSE = 7
_SCORE_DATE_MATCH = 10

_INVOICE_NO_FUZZY_THRESHOLD = 0.7
_AMOUNT_CLOSE_TOLERANCE = Decimal("0.05")
_AMOUNT_EXACT_TOLERANCE = Decimal("0.01")

_SCORE_EXACT_DUPLICATE = 90
_SCORE_POSSIBLE_DUPLICATE = 50


def _normalize_invoice_no(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _score_against(
    invoice_no: str | None,
    vendor_gstin: str | None,
    total_amount: Decimal | None,
    document_date: str | None,
    existing: Document,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if invoice_no and existing.invoice_no:
        if _normalize_invoice_no(invoice_no) == _normalize_invoice_no(existing.invoice_no):
            score += _SCORE_INVOICE_NO_EXACT
            reasons.append("same invoice number")
        else:
            similarity = difflib.SequenceMatcher(None, invoice_no.lower(), existing.invoice_no.lower()).ratio()
            if similarity >= _INVOICE_NO_FUZZY_THRESHOLD:
                score += _SCORE_INVOICE_NO_FUZZY
                reasons.append("similar invoice number")

    if vendor_gstin and existing.vendor_gstin and vendor_gstin.upper() == existing.vendor_gstin.upper():
        score += _SCORE_GSTIN_MATCH
        reasons.append("same vendor GSTIN")

    if total_amount is not None and existing.total_amount is not None:
        try:
            existing_amount = Decimal(str(existing.total_amount))
            if existing_amount != 0:
                diff_pct = abs(total_amount - existing_amount) / existing_amount
                if diff_pct <= _AMOUNT_EXACT_TOLERANCE:
                    score += _SCORE_AMOUNT_EXACT
                    reasons.append("same amount")
                elif diff_pct <= _AMOUNT_CLOSE_TOLERANCE:
                    score += _SCORE_AMOUNT_CLOSE
                    reasons.append("similar amount")
        except InvalidOperation:
            pass

    if document_date and existing.document_date and document_date == existing.document_date:
        score += _SCORE_DATE_MATCH
        reasons.append("same date")

    return score, reasons


def check_duplicate(
    doc_type: str,
    invoice_no: str | None,
    vendor_name: str | None,
    total_amount: str | None,
    db: Session | None = None,
    user_id=None,
    exclude_document_id=None,
    vendor_gstin: str | None = None,
    document_date: str | None = None,
    direction: str | None = None,
) -> dict:
    """
    Score an incoming document against recently-saved documents of the same
    type for this user, combining invoice number, GSTIN, amount, and date
    matches into a single duplicate-likelihood score (0-100).

    `exclude_document_id` excludes the document being re-validated itself —
    otherwise editing a saved document's fields would flag it as a duplicate of itself.

    `direction` ('payable'/'receivable'), when given, restricts candidates to
    the same direction — an invoice you issued should never be compared against
    a bill you received, even if both happen to be GST_INVOICE.
    """
    if db is None:
        return {
            "name": "Duplicate Check",
            "passed": True,
            "message": "No duplicate found",
            "severity": "warning",
        }

    parsed_total = parse_amount(total_amount) if total_amount else None

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    query = db.query(Document).filter(Document.doc_type == doc_type, Document.created_at >= cutoff)
    if user_id is not None:
        query = query.filter(Document.user_id == user_id)
    if exclude_document_id is not None:
        query = query.filter(Document.id != exclude_document_id)
    if direction is not None:
        query = query.filter(Document.direction == direction)
    candidates = query.all()

    best_score = 0
    best_reasons: list[str] = []
    best_existing: Document | None = None

    for existing in candidates:
        score, reasons = _score_against(invoice_no, vendor_gstin, parsed_total, document_date, existing)
        if score > best_score:
            best_score, best_reasons, best_existing = score, reasons, existing

    if best_existing is None or best_score < _SCORE_POSSIBLE_DUPLICATE:
        return {
            "name": "Duplicate Check",
            "passed": True,
            "message": "No duplicate found",
            "severity": "warning",
        }

    reason_text = ", ".join(best_reasons)
    if best_score >= _SCORE_EXACT_DUPLICATE:
        return {
            "name": "Duplicate Check",
            "passed": False,
            "message": (
                f"Likely duplicate of the invoice uploaded {best_existing.created_at.date()} "
                f"({best_score}% match — {reason_text})"
            ),
            "severity": "error",
        }

    return {
        "name": "Duplicate Check",
        "passed": False,
        "message": (
            f"Possible duplicate of the invoice uploaded {best_existing.created_at.date()} "
            f"({best_score}% match — {reason_text})"
        ),
        "severity": "warning",
    }


def find_duplicate_clusters(db: Session, user_id) -> list[dict]:
    """
    Retrospective batch scan across every stored document for this user,
    unlike `check_duplicate` which only ever compares an incoming document
    against a rolling 90-day window at upload time. Catches duplicates that
    slipped through because they were uploaded more than 90 days apart, or
    in sessions far enough apart that the single-document check never saw
    both sides of the pair.
    """
    docs = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.asc())
        .all()
    )

    # Group by (doc_type, direction) — an invoice you issued should never be
    # compared against a bill you received, even if both are GST_INVOICE.
    by_type: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for doc in docs:
        by_type[(doc.doc_type, doc.direction)].append(doc)

    pairs = []
    for group in by_type.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                parsed_total = Decimal(str(a.total_amount)) if a.total_amount is not None else None
                score, reasons = _score_against(a.invoice_no, a.vendor_gstin, parsed_total, a.document_date, b)
                if score < _SCORE_POSSIBLE_DUPLICATE:
                    continue
                pairs.append(
                    {
                        "document_id": str(a.id),
                        "other_document_id": str(b.id),
                        "vendor_name": a.vendor_name or b.vendor_name or "Unknown vendor",
                        "doc_type": a.doc_type,
                        "score": score,
                        "reasons": reasons,
                        "first_uploaded": a.created_at.isoformat(),
                        "second_uploaded": b.created_at.isoformat(),
                    }
                )

    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs
