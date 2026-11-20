"""Dashboard aggregates over saved records.

Billed amounts as printed on documents, never payments, balances or accounting postings.
Direction comes from the business role chosen at extraction: vendor -> money in, buyer -> money out.
Credit and debit notes are shown as adjustments rather than netted into either side.
"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from services.validator.rules_engine import parse_amount, parse_date

DATE_KEY = {"GST_INVOICE": "invoice_date", "PURCHASE_BILL": "bill_date", "EXPENSE_RECEIPT": "receipt_date",
            "UTILITY_BILL": "bill_date", "CREDIT_NOTE": "credit_note_date", "DEBIT_NOTE": "debit_note_date"}
ADJUSTMENTS = {"CREDIT_NOTE", "DEBIT_NOTE"}
TAXES = ("cgst", "sgst", "igst")
NOTE = "Billed amounts as printed on documents. Not payments, outstanding balances or accounting entries."


def direction(record):
    if record["doc_type"] in ADJUSTMENTS:
        return "adjustment"
    role = (record.get("metadata", {}).get("business_identity") or {}).get("business_role", "buyer")
    return "in" if role == "vendor" else "out"


def _money(value):
    return round(float(value), 2)


def _months_between(first, last):
    year, month = first
    while (year, month) <= last:
        yield f"{year:04d}-{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def build(rows, amount_of, today=None):
    """amount_of(fields) returns the document's printed amount as a Decimal, or None."""
    today = today or date.today()
    money = defaultdict(Decimal)
    counts = Counter()
    months = defaultdict(lambda: defaultdict(Decimal))
    by_type = defaultdict(lambda: {"count": 0, "amount": Decimal(0)})
    parties = {"in": defaultdict(lambda: [Decimal(0), 0]), "out": defaultdict(lambda: [Decimal(0), 0])}
    due, corrected, pipelines, pipeline_corrections = [], Counter(), Counter(), Counter()
    for row in rows:
        values = {f["key"]: f.get("value") for f in row["fields"]}
        kind, flow, amount = row["doc_type"], direction(row), amount_of(row["fields"])
        counts["documents"] += 1
        counts["needs_review"] += row.get("status") == "reviewed_with_issues"
        by_type[kind]["count"] += 1
        if amount is not None:
            by_type[kind]["amount"] += amount
            money[flow] += amount
        when = parse_date(values.get(DATE_KEY.get(kind, "")))
        if when is None:
            counts["undated"] += 1
        else:
            month = months[when.strftime("%Y-%m")]
            month["documents"] += 1
            if amount is not None:
                month[flow] += amount
            for tax in TAXES:
                printed = parse_amount(values.get(tax + "_amount"))
                if printed:
                    month[tax] += printed
        party = values.get("buyer_name") if flow == "in" else values.get("vendor_name") or values.get("utility_provider")
        if flow in parties and party and amount is not None:
            totals = parties[flow][party.strip()]
            totals[0] += amount
            totals[1] += 1
        due_on = parse_date(values.get("due_date"))
        if due_on:
            due.append({"id": row["id"], "doc_type": kind, "party": party, "due_date": due_on.isoformat(),
                        "days": (due_on - today).days, "amount": None if amount is None else _money(amount),
                        "direction": flow})
        changes = [c["key"] for entry in row.get("audit", []) for c in entry.get("changes", [])]
        corrected.update(changes)
        counts["corrected_documents"] += bool(changes)
        pipeline = row.get("pipeline") or "unknown"
        pipelines[pipeline] += 1
        pipeline_corrections[pipeline] += len(changes)
    keys = sorted(months)
    timeline = []
    if keys:
        first, last = (tuple(map(int, k.split("-"))) for k in (keys[0], keys[-1]))
        for name in _months_between(first, last):
            month = months.get(name, {})
            timeline.append({"month": name, "documents": int(month.get("documents", 0)),
                             **{key: _money(month.get(key, 0)) for key in ("in", "out", "adjustment", *TAXES)}})
    top = lambda flow: [{"name": name, "amount": _money(total), "count": n} for name, (total, n) in
                        sorted(parties[flow].items(), key=lambda item: -item[1][0])[:6]]
    # Upcoming first (soonest), then overdue (most recent first).
    due.sort(key=lambda d: (d["days"] < 0, abs(d["days"])))
    return {
        "totals": {"documents": counts["documents"], "needs_review": counts["needs_review"],
                   "undated": counts["undated"], "corrected_documents": counts["corrected_documents"],
                   "billed_in": _money(money["in"]), "billed_out": _money(money["out"]),
                   "adjustments": _money(money["adjustment"])},
        "months": timeline,
        "by_type": [{"type": kind, "count": g["count"], "amount": _money(g["amount"])}
                    for kind, g in sorted(by_type.items(), key=lambda item: -item[1]["count"])],
        "top_vendors": top("out"),
        "top_customers": top("in"),
        "due": due[:10],
        "quality": {"corrected_fields": [{"key": k, "count": n} for k, n in corrected.most_common(8)],
                    "pipelines": [{"name": k, "count": n, "corrections": pipeline_corrections[k],
                                   "corrections_per_document": round(pipeline_corrections[k] / n, 2)}
                                  for k, n in pipelines.most_common()]},
        "note": NOTE,
    }
