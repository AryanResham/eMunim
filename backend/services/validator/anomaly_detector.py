from services.validator.math_checker import parse_amount
from services.vendor_service import get_vendor_amount_stats

# How many standard deviations away from a vendor's historical mean before
# an amount is flagged as unusual. 2 sigma catches genuine outliers without
# flagging normal invoice-to-invoice variation.
_ANOMALY_STDDEV_THRESHOLD = 2.0


def check_amount_anomaly(
    doc_type: str,
    vendor_key: str | None,
    total_amount,
    db=None,
    user_id=None,
    exclude_document_id=None,
    doc_direction: str = "payable",
) -> dict | None:
    """
    Flags an invoice amount that's a statistical outlier against this
    vendor's/customer's own history (scoped to `doc_direction` so a payable
    is never compared against receivable history from the same GSTIN).
    Returns None (no rule at all, not a pass) when there isn't enough history
    to say anything meaningful — a vendor's first few invoices can't be
    "unusual" relative to a history that barely exists.
    """
    if db is None or not vendor_key or not total_amount:
        return None

    parsed_amount = parse_amount(total_amount)
    if parsed_amount is None:
        return None

    stats = get_vendor_amount_stats(db, user_id, vendor_key, doc_type, exclude_document_id, direction=doc_direction)
    if stats is None or stats["stddev"] == 0:
        return None

    amount = float(parsed_amount)
    deviation = abs(amount - stats["mean"]) / stats["stddev"]

    if deviation < _ANOMALY_STDDEV_THRESHOLD:
        return None

    comparison = "higher" if amount > stats["mean"] else "lower"
    counterparty = "customer's" if doc_direction == "receivable" else "vendor's"
    return {
        "name": "Amount Anomaly",
        "passed": False,
        "message": (
            f"₹{amount:,.2f} is {comparison} than this {counterparty} usual range "
            f"(avg ₹{stats['mean']:,.2f} over their last {stats['count']} invoices)"
        ),
        "severity": "warning",
    }
