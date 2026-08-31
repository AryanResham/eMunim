"""
Aggregate spend intelligence computed over the documents table: vendor
concentration risk, month-over-month spend trend, recurring-vendor
detection, and vendor-level spend anomalies. "Spend" means payable
documents only — Document.direction == "payable" — so a receivable (a
sales invoice the business issued) never gets counted as an expense
against itself. See services/direction_service.py for how direction is decided.
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from models.db_models import Document
from services.vendor_service import vendor_key_expr

# A vendor counts as "recurring" once it has appeared in at least this many
# distinct calendar months — enough to distinguish a subscription cadence
# from a couple of one-off purchases that happened to land in different months.
_RECURRING_MIN_MONTHS = 3

# Recurring amounts don't need to be identical (prices drift), just stable
# enough that a large swing in a given month stands out. Coefficient of
# variation (stddev / mean) below this reads as "regular".
_RECURRING_MAX_CV = 0.25

# A vendor's current-month spend counts as an anomaly once it exceeds this
# multiple of their trailing average from prior months.
_MONTHLY_ANOMALY_MULTIPLIER = 1.5

# Only EXPENSE_RECEIPT extraction actually captures a free-text "category"
# field today. Everything else still has a real accounting category — it's
# just implied by the document type rather than typed on the receipt.
_DOC_TYPE_CATEGORY_FALLBACK = {
    "GST_INVOICE": "GST Purchases",
    "PURCHASE_BILL": "Purchases",
    "UTILITY_BILL": "Utilities",
    "CREDIT_NOTE": "Credit Adjustments",
    "DEBIT_NOTE": "Debit Adjustments",
}


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _month_diff(earlier: str, later: str) -> int:
    """Number of calendar months between two 'YYYY-MM' keys (later - earlier)."""
    y1, m1 = (int(p) for p in earlier.split("-"))
    y2, m2 = (int(p) for p in later.split("-"))
    return (y2 - y1) * 12 + (m2 - m1)


def build_vendor_monthly(db: Session, user_id) -> tuple[dict, dict, dict, float]:
    """
    Shared aggregation: total amount spent per vendor per calendar month.
    Returns (vendor_monthly, vendor_names, monthly_totals, total_spend).
    """
    key = vendor_key_expr()
    rows = (
        db.query(
            key.label("vendor_key"),
            Document.vendor_name,
            Document.total_amount,
            Document.created_at,
        )
        .filter(Document.user_id == user_id, Document.total_amount.isnot(None), Document.direction == "payable")
        .all()
    )

    total_spend = 0.0
    vendor_totals: dict[str, float] = defaultdict(float)
    vendor_names: dict[str, str] = {}
    vendor_monthly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    monthly_totals: dict[str, float] = defaultdict(float)

    for vendor_key, vendor_name, amount, created_at in rows:
        if vendor_key is None or amount is None:
            continue
        amt = float(amount)
        month = _month_key(created_at)

        total_spend += amt
        vendor_totals[vendor_key] += amt
        vendor_names.setdefault(vendor_key, vendor_name or vendor_key)
        vendor_monthly[vendor_key][month] += amt
        monthly_totals[month] += amt

    return vendor_monthly, vendor_names, monthly_totals, total_spend


def get_expense_analytics(db: Session, user_id) -> dict:
    vendor_monthly, vendor_names, monthly_totals, total_spend = build_vendor_monthly(db, user_id)
    vendor_totals = {vk: sum(months.values()) for vk, months in vendor_monthly.items()}

    concentration = _vendor_concentration(vendor_totals, vendor_names, total_spend)
    trend = [{"month": m, "total_amount": round(t, 2)} for m, t in sorted(monthly_totals.items())]
    recurring = _recurring_vendors(vendor_monthly, vendor_names)
    anomalies = _monthly_anomalies(vendor_monthly, vendor_names)
    by_category = get_expense_by_category(db, user_id)

    return {
        "total_spend": round(total_spend, 2),
        "vendor_concentration": concentration,
        "monthly_trend": trend,
        "recurring_vendors": recurring,
        "monthly_anomalies": anomalies,
        "by_category": by_category,
    }


def get_expense_by_category(db: Session, user_id) -> list[dict]:
    """
    Spend grouped by category — the extracted "category" field where a
    receipt has one, else a fallback derived from the document type, so
    every priced document lands in a bucket rather than most of them
    piling up under "Uncategorized".
    """
    rows = (
        db.query(Document.doc_type, Document.total_amount, Document.extracted_fields)
        .filter(Document.user_id == user_id, Document.total_amount.isnot(None), Document.direction == "payable")
        .all()
    )

    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for doc_type, amount, fields in rows:
        raw_category = (fields or {}).get("category", "").strip()
        category = raw_category.title() if raw_category else _DOC_TYPE_CATEGORY_FALLBACK.get(doc_type, "Uncategorized")
        totals[category] += float(amount)
        counts[category] += 1

    total_spend = sum(totals.values())
    results = [
        {
            "category": category,
            "total_amount": round(amount, 2),
            "document_count": counts[category],
            "share": round(amount / total_spend, 4) if total_spend else 0,
        }
        for category, amount in totals.items()
    ]
    results.sort(key=lambda r: r["total_amount"], reverse=True)
    return results


def get_lapsed_vendors(db: Session, user_id, today: datetime | None = None) -> list[dict]:
    """
    Vendors that used to bill on a regular monthly cadence (same bar as
    "recurring" above) but haven't shown up in at least 2 calendar months —
    a possible cancelled subscription or a dropped supplier relationship.
    """
    today = today or datetime.utcnow()
    current_month = _month_key(today)
    vendor_monthly, vendor_names, _, _ = build_vendor_monthly(db, user_id)

    results = []
    for vendor_key, months in vendor_monthly.items():
        if len(months) < _RECURRING_MIN_MONTHS:
            continue
        amounts = list(months.values())
        n = len(amounts)
        mean = sum(amounts) / n
        if mean <= 0:
            continue
        variance = sum((a - mean) ** 2 for a in amounts) / n
        cv = (variance ** 0.5) / mean
        if cv > _RECURRING_MAX_CV:
            continue

        last_month = max(months.keys())
        gap = _month_diff(last_month, current_month)
        if gap < 2:
            continue

        results.append(
            {
                "vendor_key": vendor_key,
                "name": vendor_names.get(vendor_key, vendor_key),
                "last_seen_month": last_month,
                "months_since_last_invoice": gap,
                "avg_monthly_amount": round(mean, 2),
            }
        )

    results.sort(key=lambda r: r["months_since_last_invoice"], reverse=True)
    return results


def get_customer_concentration(db: Session, user_id) -> dict:
    """
    Revenue mirror of vendor concentration: how much of the business's
    receivable revenue depends on each customer. Uses buyer_name/buyer_gstin
    (the receivable side) rather than vendor_name/vendor_gstin.
    """
    key = vendor_key_expr(direction="receivable")
    rows = (
        db.query(key.label("customer_key"), Document.buyer_name, Document.total_amount)
        .filter(Document.user_id == user_id, Document.total_amount.isnot(None), Document.direction == "receivable")
        .all()
    )

    total_revenue = 0.0
    customer_totals: dict[str, float] = defaultdict(float)
    customer_names: dict[str, str] = {}

    for customer_key, buyer_name, amount in rows:
        if customer_key is None or amount is None:
            continue
        amt = float(amount)
        total_revenue += amt
        customer_totals[customer_key] += amt
        customer_names.setdefault(customer_key, buyer_name or customer_key)

    return {
        "total_revenue": round(total_revenue, 2),
        "customer_concentration": _vendor_concentration(customer_totals, customer_names, total_revenue),
    }


def _vendor_concentration(vendor_totals, vendor_names, total_spend) -> list[dict]:
    if total_spend <= 0:
        return []
    ranked = sorted(vendor_totals.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {
            "vendor_key": vendor_key,
            "name": vendor_names.get(vendor_key, vendor_key),
            "total_amount": round(amount, 2),
            "share": round(amount / total_spend, 4),
        }
        for vendor_key, amount in ranked[:10]
    ]


def _recurring_vendors(vendor_monthly, vendor_names) -> list[dict]:
    results = []
    for vendor_key, months in vendor_monthly.items():
        if len(months) < _RECURRING_MIN_MONTHS:
            continue
        amounts = list(months.values())
        n = len(amounts)
        mean = sum(amounts) / n
        if mean <= 0:
            continue
        variance = sum((a - mean) ** 2 for a in amounts) / n
        stddev = variance ** 0.5
        cv = stddev / mean
        if cv > _RECURRING_MAX_CV:
            continue
        results.append(
            {
                "vendor_key": vendor_key,
                "name": vendor_names.get(vendor_key, vendor_key),
                "months_seen": n,
                "avg_monthly_amount": round(mean, 2),
                "estimated_annual_amount": round(mean * 12, 2),
            }
        )
    results.sort(key=lambda r: r["estimated_annual_amount"], reverse=True)
    return results


def _monthly_anomalies(vendor_monthly, vendor_names) -> list[dict]:
    results = []
    for vendor_key, months in vendor_monthly.items():
        if len(months) < _RECURRING_MIN_MONTHS + 1:
            continue
        ordered = sorted(months.items())
        current_month, current_amount = ordered[-1]
        prior_amounts = [amt for _, amt in ordered[:-1]]
        prior_avg = sum(prior_amounts) / len(prior_amounts)
        if prior_avg <= 0:
            continue
        if current_amount < prior_avg * _MONTHLY_ANOMALY_MULTIPLIER:
            continue
        results.append(
            {
                "vendor_key": vendor_key,
                "name": vendor_names.get(vendor_key, vendor_key),
                "month": current_month,
                "current_amount": round(current_amount, 2),
                "prior_avg_amount": round(prior_avg, 2),
                "pct_increase": round((current_amount / prior_avg - 1) * 100, 1),
            }
        )
    results.sort(key=lambda r: r["pct_increase"], reverse=True)
    return results
