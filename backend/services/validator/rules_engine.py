# ============================================================
# CHAITYA — services/validator/rules_engine.py
# ============================================================
#
# PURPOSE:
#   Orchestrate all validators for a given doc_type and return
#   a complete ValidationResult. This is the only function the
#   router calls — it decides which rules apply to which doc type.
#
# FUNCTION TO IMPLEMENT:
#
#   def validate_document(doc_type: str, fields: dict[str, str], db=None) -> dict:
#       Returns ValidationResult as dict:
#       { "rules": [...], "overall_passed": bool, "errors": [...], "warnings": [...] }
#
#   RULES ACTIVE PER DOC TYPE:
#
#   GST_INVOICE:
#       - gstin_vendor   → validate_gstin(fields.get("vendor_gstin", ""))
#       - gstin_buyer    → validate_gstin(fields.get("buyer_gstin", ""))
#       - math_gst       → check_gst_math(fields)      (returns list — extend rules)
#       - duplicate      → check_duplicate(doc_type, invoice_no, vendor_name, total, db)
#
#   PURCHASE_BILL:
#       - gstin_vendor   → validate_gstin(fields.get("vendor_gstin", ""))
#       - math_simple    → check_simple_math(fields)
#       - duplicate      → check_duplicate(doc_type, bill_no, vendor_name, total, db)
#
#   EXPENSE_RECEIPT:
#       - math_simple    → check_simple_math(fields)
#       - date_present   → check if receipt_date is non-empty (warning if missing)
#
#   UTILITY_BILL:
#       - date_present   → check if bill_date is non-empty (warning if missing)
#       - amount_present → check if amount_due is non-empty (error if missing)
#
#   CREDIT_NOTE:
#       - gstin_vendor    → validate_gstin(fields.get("vendor_gstin", ""))
#       - ref_invoice     → check if original_invoice_no is non-empty (warning if missing)
#       - math_simple     → check_simple_math(fields)
#
#   DEBIT_NOTE:
#       - gstin_vendor    → validate_gstin(fields.get("vendor_gstin", ""))
#       - ref_invoice     → check if original_invoice_no is non-empty (warning if missing)
#       - math_simple     → check_simple_math(fields)
#
#   IMPORTANT:
#   - validate_gstin() returns (bool, str) — wrap it into a rule dict yourself
#   - check_gst_math() and check_simple_math() already return list[dict] — extend rules
#   - check_duplicate() returns a single dict — append it
#   - After collecting all rules:
#       errors   = [r for r in rules if not r["passed"] and r["severity"] == "error"]
#       warnings = [r for r in rules if not r["passed"] and r["severity"] == "warning"]
#       overall_passed = len(errors) == 0
#
# IMPORTS YOU WILL NEED:
#   from services.validator.gstin_validator import validate_gstin
#   from services.validator.math_checker import check_gst_math, check_simple_math
#   from services.validator.duplicate_detector import check_duplicate
