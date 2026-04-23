from decimal import Decimal
from services.validator.gstin_validator import validate_gstin
from services.validator.math_checker import parse_amount, check_gst_math, check_simple_math
from services.validator.rules_engine import validate_document

def test_gstin():
    print("Testing GSTIN Validator...")
    valid_gstin = "27AABCU9603R1ZN"
    invalid_gstin = "27AABCU9603R1Z0" # wrong checksum
    
    passed, msg = validate_gstin(valid_gstin)
    print(f"Valid GSTIN: {passed}, {msg}")
    
    passed, msg = validate_gstin(invalid_gstin)
    print(f"Invalid GSTIN: {passed}, {msg}")

def test_math():
    print("\nTesting Math Checker...")
    fields = {
        "taxable_amount": "100.00",
        "cgst_amount": "9.00",
        "sgst_amount": "9.00",
        "total_amount": "118.00"
    }
    rules = check_gst_math(fields)
    for r in rules:
        print(f"Rule: {r['name']}, Passed: {r['passed']}, Msg: {r['message']}")

    bad_fields = {
        "taxable_amount": "100.00",
        "cgst_amount": "9.00",
        "sgst_amount": "5.00",
        "total_amount": "118.00"
    }
    rules = check_gst_math(bad_fields)
    for r in rules:
        print(f"Rule: {r['name']}, Passed: {r['passed']}, Msg: {r['message']}")

def test_engine():
    print("\nTesting Rules Engine...")
    fields = {
        "vendor_gstin": "27AABCU9603R1ZN",
        "taxable_amount": "₹1,000.00",
        "cgst_amount": "90.00",
        "sgst_amount": "90.00",
        "total_amount": "1180.00"
    }
    result = validate_document("GST_INVOICE", fields)
    print(f"Overall Passed: {result['overall_passed']}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Warnings: {len(result['warnings'])}")

if __name__ == "__main__":
    test_gstin()
    test_math()
    test_engine()
