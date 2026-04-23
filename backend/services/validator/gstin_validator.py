import re

def validate_gstin(gstin: str) -> tuple[bool, str]:
    """
    Validate an Indian GSTIN (Goods and Services Tax Identification Number).
    Returns (is_valid: bool, message: str)
    """
    if not gstin:
        return False, "GSTIN is missing"

    # 1. Strip whitespace and convert to uppercase
    gstin = re.sub(r'\s+', '', gstin).upper()

    # 2. Regex format check
    if len(gstin) != 15:
        return False, f"GSTIN must be 15 characters (got {len(gstin)})"
    
    pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$'
    if not re.match(pattern, gstin):
        return False, "GSTIN does not match expected format"

    # 3. State code check
    try:
        state_code = int(gstin[:2])
        if not (1 <= state_code <= 37):
            return False, f"Invalid state code '{state_code}' in GSTIN"
    except ValueError:
        return False, "Invalid state code format in GSTIN"

    # 4. Checksum validation (GSTIN Luhn-like algorithm)
    CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    try:
        total = 0
        for i in range(14):
            char = gstin[i]
            val = CHARS.index(char)
            # Factor starts at 1 for 1st char, then 2, then 1...
            factor = 1 if (i % 2 == 0) else 2
            digit = val * factor
            total += (digit // 36) + (digit % 36)
        
        remainder = total % 36
        check_code = (36 - remainder) % 36
        expected_checksum = CHARS[check_code]
        
        if gstin[14] != expected_checksum:
            return False, f"GSTIN checksum digit is invalid (expected {expected_checksum})"
    except ValueError:
        return False, "Invalid characters in GSTIN"

    return True, "Valid GSTIN"
