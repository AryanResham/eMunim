from services.validator.gstin_validator import validate_gstin
from services.validator.math_checker import check_gst_math, check_simple_math
from services.validator.duplicate_detector import check_duplicate

def validate_document(doc_type: str, fields: dict[str, str], db=None) -> dict:
    """
    Orchestrate all validators for a given doc_type and return
    a complete ValidationResult.
    """
    rules = []

    # 1. GSTIN Validations
    if doc_type in ["GST_INVOICE", "PURCHASE_BILL", "CREDIT_NOTE", "DEBIT_NOTE"]:
        vendor_gstin = fields.get("vendor_gstin", "")
        if vendor_gstin:
            passed, message = validate_gstin(vendor_gstin)
            rules.append({
                "name": "Vendor GSTIN Validation",
                "passed": passed,
                "message": message,
                "severity": "error"
            })
        
        if doc_type == "GST_INVOICE":
            buyer_gstin = fields.get("buyer_gstin", "")
            if buyer_gstin:
                passed, message = validate_gstin(buyer_gstin)
                rules.append({
                    "name": "Buyer GSTIN Validation",
                    "passed": passed,
                    "message": message,
                    "severity": "error"
                })

    # 2. Math Checks
    if doc_type == "GST_INVOICE":
        rules.extend(check_gst_math(fields))
    elif doc_type in ["PURCHASE_BILL", "EXPENSE_RECEIPT", "CREDIT_NOTE", "DEBIT_NOTE"]:
        rules.extend(check_simple_math(fields))

    # 3. Date Presence Checks
    if doc_type in ["EXPENSE_RECEIPT", "UTILITY_BILL"]:
        date_key = "receipt_date" if doc_type == "EXPENSE_RECEIPT" else "bill_date"
        date_val = fields.get(date_key, "")
        rules.append({
            "name": "Date Presence",
            "passed": bool(date_val),
            "message": "Document date found" if date_val else "Document date is missing",
            "severity": "warning"
        })

    # 4. Duplicate Check
    if doc_type in ["GST_INVOICE", "PURCHASE_BILL"]:
        invoice_no = fields.get("invoice_no") or fields.get("bill_no")
        vendor_name = fields.get("vendor_name")
        total_amount = fields.get("total_amount")
        rules.append(check_duplicate(doc_type, invoice_no, vendor_name, total_amount, db))

    # Aggregate results
    errors = [r for r in rules if not r["passed"] and r["severity"] == "error"]
    warnings = [r for r in rules if not r["passed"] and r["severity"] == "warning"]
    overall_passed = len(errors) == 0

    return {
        "rules": rules,
        "overall_passed": overall_passed,
        "errors": errors,
        "warnings": warnings
    }
