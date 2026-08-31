"""
Finance-specific intelligence built on top of already-extracted document
data: potential GST input tax credit, payables aging (from extracted due
dates), and vendor line-item price trends. Nothing here needs new fields
on the Document model — it all reads extracted_fields / line items that
the extraction pipeline already captures.
"""
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy.orm import Session

from models.db_models import Document, DocumentLineItem
from services.validator.gstin_validator import validate_gstin
from services.validator.math_checker import parse_amount
from services.vendor_service import vendor_key_expr

# A vendor's line-item rate counts as a price hike once it rises by more
# than this fraction versus its previous invoice — matches the "unusual"
# bar used elsewhere (amount anomaly uses 2 sigma; this is a simpler
# single-item ratio since there's rarely enough history per SKU for stats).
_PRICE_INCREASE_THRESHOLD = 0.10

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B %Y", "%d %b %Y"]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def get_itc_summary(db: Session, user_id) -> dict:
    """
    Input Tax Credit only exists on tax the business paid to a supplier —
    restricted to direction == "payable" so the output GST on a sales
    invoice the business issued never gets counted as claimable ITC.
    """
    rows = (
        db.query(Document.id, Document.vendor_name, Document.vendor_gstin, Document.extracted_fields)
        .filter(Document.user_id == user_id, Document.direction == "payable")
        .all()
    )

    total_cgst = total_sgst = total_igst = 0.0
    exceptions = []

    for doc_id, vendor_name, vendor_gstin, fields in rows:
        fields = fields or {}
        cgst = parse_amount(fields.get("cgst_amount", "0")) or 0
        sgst = parse_amount(fields.get("sgst_amount", "0")) or 0
        igst = parse_amount(fields.get("igst_amount", "0")) or 0
        cgst, sgst, igst = float(cgst), float(sgst), float(igst)

        if cgst == 0 and sgst == 0 and igst == 0:
            continue

        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst

        is_valid, reason = validate_gstin(vendor_gstin or "")
        if not is_valid:
            exceptions.append(
                {
                    "document_id": str(doc_id),
                    "vendor_name": vendor_name or "Unknown vendor",
                    "itc_amount": round(cgst + sgst + igst, 2),
                    "reason": reason,
                }
            )

    total_itc = total_cgst + total_sgst + total_igst
    return {
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_igst": round(total_igst, 2),
        "total_itc": round(total_itc, 2),
        "exceptions": sorted(exceptions, key=lambda e: e["itc_amount"], reverse=True),
    }


def _aging(db: Session, user_id, today: date | None, direction: str) -> dict:
    today = today or date.today()
    name_col = Document.buyer_name if direction == "receivable" else Document.vendor_name
    rows = (
        db.query(Document.id, name_col, Document.total_amount, Document.extracted_fields)
        .filter(Document.user_id == user_id, Document.total_amount.isnot(None), Document.direction == direction)
        .all()
    )

    items = []
    for doc_id, counterparty_name, total_amount, fields in rows:
        due_date = _parse_date((fields or {}).get("due_date"))
        if due_date is None:
            continue
        days_until_due = (due_date - today).days
        if days_until_due < 0:
            bucket = "overdue"
        elif days_until_due <= 7:
            bucket = "due_soon"
        else:
            bucket = "upcoming"
        items.append(
            {
                "document_id": str(doc_id),
                "vendor_name": counterparty_name or "Unknown",
                "amount": float(total_amount),
                "due_date": due_date.isoformat(),
                "days_until_due": days_until_due,
                "bucket": bucket,
            }
        )

    items.sort(key=lambda i: i["due_date"])
    bucket_totals = defaultdict(float)
    for i in items:
        bucket_totals[i["bucket"]] += i["amount"]

    return {
        "items": items,
        "overdue_total": round(bucket_totals["overdue"], 2),
        "due_soon_total": round(bucket_totals["due_soon"], 2),
        "upcoming_total": round(bucket_totals["upcoming"], 2),
    }


def get_payables_aging(db: Session, user_id, today: date | None = None) -> dict:
    return _aging(db, user_id, today, direction="payable")


def get_receivables_aging(db: Session, user_id, today: date | None = None) -> dict:
    """
    Same aging buckets as payables, mirrored for money owed TO the business —
    receivable GST_INVOICE documents (direction == "receivable") with a
    due_date extracted. Uses buyer_name rather than vendor_name since a
    receivable's counterparty is the customer, not a vendor.
    """
    return _aging(db, user_id, today, direction="receivable")


def get_vendor_price_alerts(db: Session, user_id) -> list[dict]:
    key = vendor_key_expr()
    rows = (
        db.query(
            key.label("vendor_key"),
            Document.vendor_name,
            Document.created_at,
            DocumentLineItem.description,
            DocumentLineItem.rate,
        )
        .join(DocumentLineItem, DocumentLineItem.document_id == Document.id)
        .filter(Document.user_id == user_id, Document.direction == "payable")
        .all()
    )

    groups: dict[tuple[str, str], list[tuple[datetime, float]]] = defaultdict(list)
    vendor_names: dict[str, str] = {}
    for vendor_key, vendor_name, created_at, description, rate in rows:
        if vendor_key is None or not description or not description.strip():
            continue
        parsed_rate = parse_amount(rate)
        if parsed_rate is None or parsed_rate <= 0:
            continue
        vendor_names.setdefault(vendor_key, vendor_name or vendor_key)
        normalized_desc = description.strip().lower()
        groups[(vendor_key, normalized_desc)].append((created_at, float(parsed_rate)))

    alerts = []
    for (vendor_key, normalized_desc), points in groups.items():
        if len(points) < 2:
            continue
        points.sort(key=lambda p: p[0])
        previous_rate = points[-2][1]
        current_rate = points[-1][1]
        if previous_rate <= 0:
            continue
        change = (current_rate - previous_rate) / previous_rate
        if change < _PRICE_INCREASE_THRESHOLD:
            continue
        alerts.append(
            {
                "vendor_key": vendor_key,
                "vendor_name": vendor_names.get(vendor_key, vendor_key),
                "description": normalized_desc,
                "previous_rate": round(previous_rate, 2),
                "current_rate": round(current_rate, 2),
                "pct_increase": round(change * 100, 1),
            }
        )

    alerts.sort(key=lambda a: a["pct_increase"], reverse=True)
    return alerts
