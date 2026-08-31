"""
Vendor/customer intelligence, computed live from the documents table rather
than kept in a separate synced table — there's no identity normalization yet
(name variants aren't merged), so a materialized table would just be a cache
with nothing to normalize. Grouping by GSTIN (falling back to name) is the
closest thing to real identity we have right now.

Every document has a `direction`: 'payable' (a bill this business received —
the counterparty is a vendor) or 'receivable' (an invoice this business
issued — the counterparty is a customer, captured in buyer_name/buyer_gstin
rather than vendor_name/vendor_gstin). Every function here takes a
`direction` and picks the right pair of columns accordingly.
"""
from decimal import Decimal

from sqlalchemy import String, case, func
from sqlalchemy.orm import Session

from models.db_models import Document

_PAYABLE = "payable"
_RECEIVABLE = "receivable"
_UNKNOWN_CUSTOMER_PREFIX = "unknown:"


def vendor_key_expr(direction: str = _PAYABLE):
    """
    The counterparty identity column for a given direction — GSTIN preferred,
    falling back to name. 'payable' reads vendor_name/vendor_gstin (who you
    bought from); 'receivable' reads buyer_name/buyer_gstin (who you sold to).
    """
    if direction == _RECEIVABLE:
        return func.coalesce(Document.buyer_gstin, Document.buyer_name)
    return func.coalesce(Document.vendor_gstin, Document.vendor_name)


def _name_col(direction: str):
    return Document.buyer_name if direction == _RECEIVABLE else Document.vendor_name


def _gstin_col(direction: str):
    return Document.buyer_gstin if direction == _RECEIVABLE else Document.vendor_gstin


def vendor_key_expr_with_fallback(direction: str = _PAYABLE):
    """
    Same as vendor_key_expr, but a document with no counterparty identity at
    all (most commonly a 'receivable' whose buyer_name/buyer_gstin was never
    captured) gets a synthetic per-document key instead of NULL — so it still
    shows up as its own "Unknown Customer" entry, and folder drill-down
    (GET /documents?vendor_key=...) can still find it by that same key.
    """
    return func.coalesce(vendor_key_expr(direction), func.concat(_UNKNOWN_CUSTOMER_PREFIX, Document.id.cast(String)))


def list_vendor_profiles(db: Session, user_id, direction: str = _PAYABLE) -> list[dict]:
    name_col = _name_col(direction)
    gstin_col = _gstin_col(direction)
    key = vendor_key_expr_with_fallback(direction)

    rows = (
        db.query(
            key.label("vendor_key"),
            func.max(name_col).label("display_name"),
            func.max(gstin_col).label("gstin"),
            func.count(Document.id).label("document_count"),
            func.coalesce(func.sum(Document.total_amount), 0).label("total_amount"),
            func.coalesce(func.avg(Document.total_amount), 0).label("avg_amount"),
            func.min(Document.created_at).label("first_seen"),
            func.max(Document.created_at).label("last_seen"),
            func.sum(case((Document.overall_passed.is_(False), 1), else_=0)).label("flagged_count"),
        )
        .filter(Document.user_id == user_id, Document.direction == direction)
        .group_by(key)
        .order_by(func.count(Document.id).desc())
        .all()
    )

    label = "Unknown Customer" if direction == _RECEIVABLE else "Unknown Vendor"
    return [
        {
            "vendor_key": r.vendor_key,
            "name": r.display_name or label,
            "gstin": r.gstin,
            "document_count": r.document_count,
            "total_amount": float(r.total_amount),
            "avg_amount": float(r.avg_amount),
            "first_seen": r.first_seen.isoformat(),
            "last_seen": r.last_seen.isoformat(),
            "flagged_count": r.flagged_count,
        }
        for r in rows
    ]


def list_customer_profiles(db: Session, user_id) -> list[dict]:
    return list_vendor_profiles(db, user_id, direction=_RECEIVABLE)


def get_vendor_amount_stats(
    db: Session,
    user_id,
    vendor_key: str,
    doc_type: str,
    exclude_document_id=None,
    direction: str = _PAYABLE,
) -> dict | None:
    """
    Mean and (sample) standard deviation of this vendor's/customer's past
    invoice amounts, for anomaly detection. Returns None if there isn't
    enough history to say anything statistically meaningful (fewer than 3
    prior documents in the same direction — a receivable should never be
    compared against payable history from the same GSTIN or vice versa).
    """
    key = vendor_key_expr(direction)
    query = db.query(Document.total_amount).filter(
        Document.user_id == user_id,
        Document.doc_type == doc_type,
        Document.direction == direction,
        key == vendor_key,
        Document.total_amount.isnot(None),
    )
    if exclude_document_id is not None:
        query = query.filter(Document.id != exclude_document_id)
    rows = query.all()
    amounts = [float(r[0]) for r in rows]
    if len(amounts) < 3:
        return None

    n = len(amounts)
    mean = sum(amounts) / n
    variance = sum((a - mean) ** 2 for a in amounts) / (n - 1)
    stddev = variance ** 0.5
    return {"mean": mean, "stddev": stddev, "count": n}
