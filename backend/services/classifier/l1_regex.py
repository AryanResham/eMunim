import re

GSTIN_PATTERN = re.compile(r'\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]')

# Rules evaluated in priority order — first match wins.
# (pattern, doc_type, base_confidence)
_RULES: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r'\bCREDIT\s+NOTE\b', re.I),                              'CREDIT_NOTE',     0.95),
    (re.compile(r'\bDEBIT\s+NOTE\b', re.I),                               'DEBIT_NOTE',      0.95),
    (re.compile(r'\b(TAX\s+INVOICE|GST\s+INVOICE)\b', re.I),              'GST_INVOICE',     0.85),
    (re.compile(r'\bPURCHASE\s+(ORDER|BILL)\b', re.I),                    'PURCHASE_BILL',   0.80),
    (re.compile(r'\b(ELECTRICITY|WATER|GAS|INTERNET|BROADBAND)\b.*\bBILL\b', re.I), 'UTILITY_BILL', 0.80),
    (re.compile(r'\bRECEIPT\b', re.I),                                    'EXPENSE_RECEIPT', 0.70),
]


def classify_l1(text: str) -> tuple[str | None, float]:
    """
    Returns (doc_type, confidence) or (None, 0.0) if no rule matches.
    GSTIN presence adds +0.10 to GST_INVOICE confidence (capped at 0.99).
    """
    has_gstin = bool(GSTIN_PATTERN.search(text))

    for pattern, doc_type, confidence in _RULES:
        if pattern.search(text):
            if has_gstin and doc_type == 'GST_INVOICE':
                confidence = min(confidence + 0.10, 0.99)
            return doc_type, confidence

    # GSTIN present but no keyword matched — likely a GST invoice
    if has_gstin:
        return 'GST_INVOICE', 0.75

    return None, 0.0
