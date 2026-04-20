# ============================================================
# CHAITYA — services/validator/gstin_validator.py
# ============================================================
#
# PURPOSE:
#   Validate an Indian GSTIN (Goods and Services Tax Identification Number).
#   Used by rules_engine.py for all doc types that have vendor/buyer GSTINs.
#
# FUNCTION TO IMPLEMENT:
#
#   def validate_gstin(gstin: str) -> tuple[bool, str]:
#       Returns (is_valid: bool, message: str)
#
#   VALIDATION STEPS (in order):
#
#   1. Strip whitespace and convert to uppercase
#
#   2. Regex format check:
#       Pattern: r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$'
#       Length must be exactly 15 characters
#       If fails: return (False, "GSTIN does not match expected format")
#
#   3. State code check:
#       First 2 digits = state code (int)
#       Valid range: 1 to 37 (Indian state codes)
#       If outside range: return (False, f"Invalid state code '{code}' in GSTIN")
#
#   4. Checksum validation (GSTIN Luhn-like algorithm):
#       Character set: CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
#       For each character in gstin[0:14] (index 0 to 13):
#           val = CHARS.index(char)
#           if position index is ODD (1-based): val = val * 2
#           total += (val // 36) + (val % 36)
#       check_digit = (36 - total % 36) % 36
#       Expected last char = CHARS[check_digit]
#       If mismatch: return (False, "GSTIN checksum digit is invalid")
#
#   5. If all pass: return (True, "Valid GSTIN")
#
# EXAMPLE VALID GSTINs for testing:
#   27AABCU9603R1ZM  (Maharashtra)
#   07AAEFS1234B1Z5  (Delhi)
#   29AABCN7890G1Z1  (Karnataka)
