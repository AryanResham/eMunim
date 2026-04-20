# ============================================================
# CHAITYA — services/validator/math_checker.py
# ============================================================
#
# PURPOSE:
#   Arithmetic cross-checks on extracted financial fields.
#   Returns a list of ValidationRule dicts (not objects — plain dicts).
#
# FUNCTIONS TO IMPLEMENT:
#
#   def parse_amount(value: str) -> Decimal | None:
#       - Strip ₹ symbol, commas, and whitespace: re.sub(r'[₹,\s]', '', value)
#       - Try Decimal(cleaned); return None if it raises InvalidOperation
#       - Example: "₹1,23,456.78" → Decimal("123456.78")
#
#   def check_gst_math(fields: dict[str, str]) -> list[dict]:
#       fields keys: vendor_gstin, taxable_amount, cgst_amount, sgst_amount,
#                    igst_amount, total_amount (all string values, may be missing)
#
#       RULE 1 — Total cross-check:
#           expected_total = taxable_amount + cgst_amount + sgst_amount + igst_amount
#           actual_total   = total_amount
#           allowed tolerance: abs(actual - expected) < Decimal("1.00")  (rounding)
#           severity: "error" if fails
#
#       RULE 2 — CGST == SGST symmetry:
#           For intra-state supply, CGST and SGST must be equal
#           If both present and differ by more than ₹0.01: severity "warning"
#           (IGST is used instead for inter-state — if igst is present and cgst/sgst
#            are zero, skip this rule)
#
#       RULE 3 — GST rate sanity:
#           If taxable_amount > 0 and (cgst + sgst) > 0:
#               effective_rate = (cgst + sgst) / taxable_amount * 100
#               Valid rates: {0, 5, 12, 18, 28}
#               Allow 0.5% tolerance around each valid rate
#               If no valid rate matches: severity "warning"
#
#       Return list of rule dicts with keys: name, passed, message, severity
#
#   def check_simple_math(fields: dict[str, str]) -> list[dict]:
#       For EXPENSE_RECEIPT / PURCHASE_BILL where there's no CGST/SGST split.
#       Just check that total_amount or amount is present and > 0.
#       Return single rule: "Amount Present" — error if missing.
