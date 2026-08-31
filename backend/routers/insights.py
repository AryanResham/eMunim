from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import Document, FieldCorrection, User
from services.document_intelligence_service import get_credit_debit_netting, get_low_confidence_queue
from services.expense_analytics_service import get_customer_concentration, get_expense_analytics, get_lapsed_vendors
from services.finance_insights_service import (
    get_itc_summary,
    get_payables_aging,
    get_receivables_aging,
    get_vendor_price_alerts,
)
from services.validator.duplicate_detector import find_duplicate_clusters

router = APIRouter()


@router.get("/insights/expenses")
def expense_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Vendor concentration risk, monthly spend trend, recurring-vendor
    detection, and vendor-level month-over-month spend anomalies.
    """
    return get_expense_analytics(db, current_user.id)


@router.get("/insights/finance")
def finance_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    GST input-tax-credit summary, payables aging (from extracted due dates),
    and vendor line-item price-increase alerts.
    """
    return {
        "itc": get_itc_summary(db, current_user.id),
        "payables": get_payables_aging(db, current_user.id),
        "price_alerts": get_vendor_price_alerts(db, current_user.id),
    }


@router.get("/insights/receivables")
def receivables_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    The revenue-side mirror of /insights/finance and /insights/expenses:
    customer concentration and receivables aging, both restricted to
    Document.direction == "receivable" (invoices the business issued).
    """
    customer = get_customer_concentration(db, current_user.id)
    return {
        "total_revenue": customer["total_revenue"],
        "customer_concentration": customer["customer_concentration"],
        "receivables_aging": get_receivables_aging(db, current_user.id),
    }


@router.get("/insights/documents")
def document_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Credit/debit note netting per vendor, vendors that used to bill
    regularly but have gone quiet, a retrospective duplicate scan across
    all stored documents, and documents whose extraction confidence was
    too low to trust without a second look.
    """
    return {
        "credit_debit_netting": get_credit_debit_netting(db, current_user.id),
        "lapsed_vendors": get_lapsed_vendors(db, current_user.id),
        "duplicate_clusters": find_duplicate_clusters(db, current_user.id),
        "low_confidence_queue": get_low_confidence_queue(db, current_user.id),
    }


@router.get("/insights/notifications")
def insights_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    A flat, ranked list of things that need attention right now, pulled from
    the various insight sources — the data behind the header notification bell.
    """
    notifications = []

    expenses = get_expense_analytics(db, current_user.id)
    for a in expenses["monthly_anomalies"][:5]:
        notifications.append(
            {
                "id": f"anomaly-{a['vendor_key']}-{a['month']}",
                "severity": "warning",
                "message": f"{a['name']} spend is up {a['pct_increase']:.0f}% this month vs their average",
            }
        )
    if expenses["vendor_concentration"]:
        top = expenses["vendor_concentration"][0]
        if top["share"] >= 0.4:
            notifications.append(
                {
                    "id": f"concentration-{top['vendor_key']}",
                    "severity": "warning",
                    "message": f"{round(top['share'] * 100)}% of spend depends on a single vendor ({top['name']})",
                }
            )

    itc = get_itc_summary(db, current_user.id)
    for e in itc["exceptions"][:5]:
        notifications.append(
            {
                "id": f"itc-{e['document_id']}",
                "severity": "error",
                "message": f"₹{e['itc_amount']:,.0f} ITC on {e['vendor_name']} may not be claimable — {e['reason']}",
            }
        )

    payables = get_payables_aging(db, current_user.id)
    overdue = [i for i in payables["items"] if i["bucket"] == "overdue"]
    due_soon = [i for i in payables["items"] if i["bucket"] == "due_soon"]
    if overdue:
        notifications.append(
            {
                "id": "payables-overdue",
                "severity": "error",
                "message": f"₹{payables['overdue_total']:,.0f} across {len(overdue)} payment(s) overdue",
            }
        )
    if due_soon:
        notifications.append(
            {
                "id": "payables-due-soon",
                "severity": "warning",
                "message": f"₹{payables['due_soon_total']:,.0f} across {len(due_soon)} payment(s) due within 7 days",
            }
        )

    for p in get_vendor_price_alerts(db, current_user.id)[:5]:
        notifications.append(
            {
                "id": f"price-{p['vendor_key']}-{p['description']}",
                "severity": "warning",
                "message": f"{p['vendor_name']} raised the price of \"{p['description']}\" by {p['pct_increase']:.0f}%",
            }
        )

    # Documents that failed a validation rule (GSTIN checksum, GST math, duplicate
    # check, amount anomaly, ...) — the flags a reviewer would clear from the
    # Document Review workspace. Each links straight to that document in Records.
    flagged_docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id, Document.overall_passed.is_(False))
        .order_by(Document.created_at.desc())
        .limit(10)
        .all()
    )
    for doc in flagged_docs:
        rules = (doc.validation_result or {}).get("errors") or (doc.validation_result or {}).get("warnings") or []
        if not rules:
            continue
        top_issue = rules[0]
        label = doc.invoice_no or doc.file_name or doc.file_id
        notifications.append(
            {
                "id": f"document-{doc.id}",
                "severity": top_issue["severity"],
                "message": f"{label}: {top_issue['message']}",
                "document_id": str(doc.id),
            }
        )

    for v in get_lapsed_vendors(db, current_user.id)[:3]:
        notifications.append(
            {
                "id": f"lapsed-{v['vendor_key']}",
                "severity": "warning",
                "message": (
                    f"{v['name']} used to bill ~₹{v['avg_monthly_amount']:,.0f}/mo but hasn't "
                    f"invoiced in {v['months_since_last_invoice']} months — check if this was cancelled"
                ),
            }
        )

    for n in get_credit_debit_netting(db, current_user.id):
        if not n["high_credit_note_rate"]:
            continue
        notifications.append(
            {
                "id": f"credit-rate-{n['vendor_key']}",
                "severity": "warning",
                "message": f"{n['name']} issues credit notes on {round(n['credit_note_rate'] * 100)}% of invoices",
            }
        )

    receivables = get_receivables_aging(db, current_user.id)
    overdue_receivables = [i for i in receivables["items"] if i["bucket"] == "overdue"]
    if overdue_receivables:
        notifications.append(
            {
                "id": "receivables-overdue",
                "severity": "error",
                "message": f"₹{receivables['overdue_total']:,.0f} across {len(overdue_receivables)} customer payment(s) overdue",
            }
        )

    customer = get_customer_concentration(db, current_user.id)
    if customer["customer_concentration"]:
        top_customer = customer["customer_concentration"][0]
        if top_customer["share"] >= 0.4:
            notifications.append(
                {
                    "id": f"customer-concentration-{top_customer['vendor_key']}",
                    "severity": "warning",
                    "message": f"{round(top_customer['share'] * 100)}% of revenue depends on a single customer ({top_customer['name']})",
                }
            )

    for c in find_duplicate_clusters(db, current_user.id)[:3]:
        notifications.append(
            {
                "id": f"duplicate-{c['document_id']}-{c['other_document_id']}",
                "severity": "error" if c["score"] >= 90 else "warning",
                "message": f"Possible duplicate documents from {c['vendor_name']} ({c['score']}% match)",
                "document_id": c["document_id"],
            }
        )

    return {"notifications": notifications}


@router.get("/insights/corrections")
def correction_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Which extracted fields humans correct most often, and how confident the
    model was when it got them wrong. The signal this is for: "the model keeps
    confusing X for Y" shows up here as a field with a high correction count
    and a high average confidence-at-correction (confidently wrong, not just uncertain).
    """
    rows = (
        db.query(
            FieldCorrection.field_name,
            func.count(FieldCorrection.id),
            func.avg(FieldCorrection.model_confidence),
        )
        .join(Document, Document.id == FieldCorrection.document_id)
        .filter(Document.user_id == current_user.id)
        .group_by(FieldCorrection.field_name)
        .order_by(func.count(FieldCorrection.id).desc())
        .all()
    )

    return {
        "fields": [
            {
                "field_name": field_name,
                "correction_count": count,
                "avg_model_confidence": float(avg_confidence) if avg_confidence is not None else None,
            }
            for field_name, count, avg_confidence in rows
        ]
    }
