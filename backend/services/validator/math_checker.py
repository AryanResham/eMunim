import re
from decimal import Decimal, InvalidOperation
from utils.confidence_config import VALIDATION_TAX_MATCH_TOLERANCE, VALIDATION_RATE_MATCH_TOLERANCE

def parse_amount(value: str) -> Decimal | None:
    """Strip ₹ symbol, commas, and whitespace and convert to Decimal."""
    if not value:
        return None
    cleaned = re.sub(r'[₹,\s]', '', value)
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None

def check_gst_math(fields: dict[str, str]) -> list[dict]:
    """Arithmetic cross-checks for GST invoices."""
    rules = []
    
    taxable = parse_amount(fields.get("taxable_amount", "0")) or Decimal("0")
    cgst = parse_amount(fields.get("cgst_amount", "0")) or Decimal("0")
    sgst = parse_amount(fields.get("sgst_amount", "0")) or Decimal("0")
    igst = parse_amount(fields.get("igst_amount", "0")) or Decimal("0")
    total = parse_amount(fields.get("total_amount", "0")) or Decimal("0")

    # RULE 1: Total cross-check
    expected_total = taxable + cgst + sgst + igst
    if total > 0:
        passed = abs(total - expected_total) < Decimal("1.00")
        rules.append({
            "name": "Total Amount Match",
            "passed": passed,
            "message": f"Expected {expected_total}, found {total}" if not passed else "Taxable + GST matches Total",
            "severity": "error"
        })
    else:
        rules.append({
            "name": "Total Amount Match",
            "passed": False,
            "message": "Total amount is missing or zero",
            "severity": "error"
        })

    # RULE 2: CGST == SGST symmetry
    # Skip if IGST is used
    if igst == 0 and (cgst > 0 or sgst > 0):
        passed = abs(cgst - sgst) <= Decimal(str(VALIDATION_TAX_MATCH_TOLERANCE))
        rules.append({
            "name": "Tax Symmetry",
            "passed": passed,
            "message": "CGST and SGST must be equal for intra-state supply" if not passed else "CGST matches SGST",
            "severity": "warning"
        })

    # RULE 3: GST rate sanity
    if taxable > 0 and (cgst + sgst + igst) > 0:
        effective_rate = ((cgst + sgst + igst) / taxable) * 100
        valid_rates = [0, 5, 12, 18, 28]
        rate_passed = any(abs(effective_rate - Decimal(str(r))) < Decimal(str(VALIDATION_RATE_MATCH_TOLERANCE)) for r in valid_rates)
        
        rules.append({
            "name": "GST Rate Sanity",
            "passed": rate_passed,
            "message": f"Calculated GST rate ({effective_rate:.1f}%) is unusual" if not rate_passed else f"GST rate ({effective_rate:.1f}%) is valid",
            "severity": "warning"
        })

    return rules

def check_simple_math(fields: dict[str, str]) -> list[dict]:
    """Basic check for total amount presence."""
    total = parse_amount(fields.get("total_amount") or fields.get("amount", ""))
    passed = total is not None and total > 0
    return [{
        "name": "Amount Present",
        "passed": passed,
        "message": "Total amount extracted and is valid" if passed else "Could not find a valid total amount",
        "severity": "error"
    }]
