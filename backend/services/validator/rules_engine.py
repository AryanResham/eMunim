"""Versioned extraction consistency checks; not tax compliance certification."""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from config import settings
from services.field_contract import REQUIRED, AMOUNT_KEYS, DATE_KEYS
from services.validator.gstin_validator import validate_gstin

RULE_VERSION = "consistency-v2"
POLICIES = ("extraction_only", "validation_review", "validation_confidence_review")

def parse_amount(value):
    if value is None or not str(value).strip():
        return None
    cleaned = re.sub(r"\s+", "", str(value))
    cleaned = re.sub(r"^(?:rs\.?|inr|\u20b9)", "", cleaned, count=1, flags=re.I)
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
        cleaned = re.sub(r"^(?:rs\.?|inr|\u20b9)", "", cleaned, count=1, flags=re.I)
        if cleaned.startswith(("-", "+")):
            return None
    cleaned = ("-" if negative else "") + cleaned.replace(",", "")
    try:
        number = Decimal(cleaned)
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None

def parse_date(value):
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None

def validate_document(doc_type, fields, db=None):
    if doc_type not in REQUIRED:
        raise ValueError("Unsupported document type")
    rules = []
    def add(name, passed, message, keys, severity="error", status=None):
        rules.append(dict(name=name, passed=passed, status=status or ("insufficient_evidence" if passed is None else "passed" if passed else "failed"),
                          message=message, fields=keys, severity=severity))
    for key in REQUIRED[doc_type]:
        present = fields.get(key) is not None and bool(str(fields[key]).strip())
        add("Required: " + key, present, "Present" if present else "Required field is missing", [key])
    for key, value in fields.items():
        if value is None or not str(value).strip():
            continue
        if key.endswith("gstin"):
            passed, message = validate_gstin(str(value))
            add("Format: " + key, passed, message, [key])
        if key in DATE_KEYS or key.endswith("_date"):
            parsed = parse_date(str(value))
            add("Date: " + key, parsed is not None, "Date parsed" if parsed else "Unrecognized date; verify against source", [key])
            if parsed and key != "due_date":
                add("Future date: " + key, parsed <= date.today(), "Document date is in the future" if parsed > date.today() else "Not in the future", [key], "warning")
        if key in AMOUNT_KEYS:
            number = parse_amount(value)
            add("Amount: " + key, number is not None, "Amount parsed" if number is not None else "Invalid amount", [key])
    amount_key = {"UTILITY_BILL": "amount_due", "CREDIT_NOTE": "credit_amount", "DEBIT_NOTE": "debit_amount", "EXPENSE_RECEIPT": "amount"}.get(doc_type, "total_amount")
    amount = parse_amount(fields.get(amount_key))
    add("Positive document amount", amount is not None and amount > 0, "Amount must be present and positive", [amount_key])
    if doc_type == "GST_INVOICE":
        keys = ["taxable_amount", "cgst_amount", "sgst_amount", "igst_amount", "total_amount"]
        nums = {key: parse_amount(fields.get(key)) for key in keys}
        present_taxes = [key for key in keys[1:4] if fields.get(key) is not None and str(fields[key]).strip()]
        if not present_taxes or nums["taxable_amount"] is None or nums["total_amount"] is None or any(nums[k] is None for k in present_taxes):
            add("Total reconciliation", None, "Cannot reconcile without taxable/total and legible tax evidence (explicit zero is allowed)", keys)
        else:
            expected = nums["taxable_amount"] + sum((nums[k] for k in present_taxes), Decimal(0))
            delta = abs(expected - nums["total_amount"])
            add("Total reconciliation", delta <= Decimal("1"), f"Taxable + printed taxes = {expected}; total = {nums['total_amount']} (tolerance 1)", keys)
        cgst, sgst, igst = (nums[k] for k in keys[1:4])
        if (cgst is not None and cgst > 0) or (sgst is not None and sgst > 0):
            add("Tax symmetry", cgst is not None and sgst is not None and abs(cgst - sgst) <= Decimal("0.01"), "Printed CGST and SGST should agree; check missing counterpart", ["cgst_amount", "sgst_amount"], "warning")
        if igst is not None and igst > 0:
            mixed = any(x is not None and x > 0 for x in (cgst, sgst))
            add("Tax structure", not mixed, "Review simultaneous positive IGST and CGST/SGST" if mixed else "No mixed positive components", keys[1:4], "warning")
    errors = [r for r in rules if r["passed"] is False and r["severity"] == "error"]
    warnings = [r for r in rules if r["passed"] is False and r["severity"] == "warning"]
    return dict(rules=rules, errors=errors, warnings=warnings, overall_passed=not errors,
                rule_version=RULE_VERSION)

def review_document(doc_type, fields, policy="validation_review", operational_reasons=None, conflicts=None, threshold=None):
    if policy not in POLICIES:
        raise ValueError("Unknown review policy")
    values = {f["key"]: f.get("value") for f in fields}
    result = validate_document(doc_type, values)
    flagged, reasons = set(), list(operational_reasons or [])
    if policy != "extraction_only":
        for rule in result["rules"]:
            if rule["passed"] is not True and rule["status"] != "not_applicable":
                flagged.update(rule["fields"])
                reasons.append(rule["name"] + ": " + rule["message"])
    limit = settings.REVIEW_THRESHOLD if threshold is None else threshold
    if policy == "validation_confidence_review":
        for field in fields:
            if field.get("value") and field.get("source") == "layoutlm" and field.get("confidence") is not None and field["confidence"] < limit:
                flagged.add(field["key"])
                reasons.append("Low model confidence: " + field["key"])
    for key in conflicts or []:
        flagged.add(key)
        reasons.append("Unresolved extractor disagreement: " + key)
    result.update(review_required=bool(reasons), review_reasons=list(dict.fromkeys(reasons)),
                  flagged_fields=sorted(flagged), policy=policy, policy_version="review-v1",
                  threshold=limit if policy == "validation_confidence_review" else None)
    return result
