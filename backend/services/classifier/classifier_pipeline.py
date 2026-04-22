from __future__ import annotations
import re
from datetime import datetime

from .l1_regex import classify_l1
from .l2_finbert import classify_l2

_L1_THRESHOLD = 0.80
_L2_THRESHOLD = 0.60

_DOC_TYPE_METADATA: dict[str, dict] = {
    "GST_INVOICE": {
        "label": "GST Tax Invoice",
        "suggested_sub_categories": ["Accounts Payable", "Input Tax Credit", "Supplier Invoice", "Import Bill"],
    },
    "PURCHASE_BILL": {
        "label": "Purchase Bill",
        "suggested_sub_categories": ["Raw Materials", "Office Supplies", "Capital Goods", "Trade Purchase"],
    },
    "EXPENSE_RECEIPT": {
        "label": "Expense Receipt",
        "suggested_sub_categories": ["Travel & Conveyance", "Meals & Entertainment", "Petrol & Fuel", "Office Expenses", "Software Subscription"],
    },
    "UTILITY_BILL": {
        "label": "Utility Bill",
        "suggested_sub_categories": ["Electricity", "Water", "Internet / Broadband", "Telephone", "Gas"],
    },
    "CREDIT_NOTE": {
        "label": "Credit Note",
        "suggested_sub_categories": ["Sales Return", "Discount Allowed", "Price Adjustment"],
    },
    "DEBIT_NOTE": {
        "label": "Debit Note",
        "suggested_sub_categories": ["Purchase Return", "Charge Back", "Penalty"],
    },
}

# Common Indian date formats
_DATE_PATTERNS = [
    re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'),          # DD/MM/YYYY
    re.compile(r'\b(\d{4})[/-](\d{2})[/-](\d{2})\b'),               # YYYY-MM-DD
    re.compile(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b', re.I),
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _extract_date(text: str) -> str:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return ""


def _extract_merchant(text: str) -> str:
    # Look for "Invoice from:", "Vendor:", "Billed by:" prefixes first
    prefix_match = re.search(
        r'(?:invoice\s+from|vendor|billed\s+by|from)\s*[:\-]?\s*([A-Z][A-Za-z\s\.&,]{3,50})',
        text, re.I
    )
    if prefix_match:
        return prefix_match.group(1).strip()

    # Fall back to first all-caps line that looks like a company name
    for line in text.splitlines()[:8]:
        line = line.strip()
        if len(line) > 4 and line == line.upper() and not any(c.isdigit() for c in line):
            return line.title()

    return ""


def classify_document(ocr_text: str) -> dict:
    """
    Run the 3-level classification pipeline and return a ClassificationResult dict.

    Level L1: regex rules — handles ~70-80% of clear documents
    Level L2: zero-shot NLP model — handles ambiguous documents
    Level L3: returned when L2 confidence < threshold — frontend shows human picker
    """
    # L1 — regex
    l1_type, l1_conf = classify_l1(ocr_text)
    if l1_type and l1_conf >= _L1_THRESHOLD:
        meta = _DOC_TYPE_METADATA[l1_type]
        return {
            "type": l1_type,
            "label": meta["label"],
            "sub_category": meta["suggested_sub_categories"][0],
            "confidence": round(l1_conf * 100, 1),
            "classifier_level": "L1",
            "top_predictions": [{"type": l1_type, "confidence": round(l1_conf, 3)}],
            "merchant": _extract_merchant(ocr_text),
            "date": _extract_date(ocr_text),
            "suggested_sub_categories": meta["suggested_sub_categories"],
        }

    # L2 — zero-shot NLP
    l2_type, l2_conf, predictions = classify_l2(ocr_text)
    level = "L2" if l2_conf >= _L2_THRESHOLD else "L3"
    meta = _DOC_TYPE_METADATA[l2_type]

    return {
        "type": l2_type,
        "label": meta["label"],
        "sub_category": meta["suggested_sub_categories"][0],
        "confidence": round(l2_conf * 100, 1),
        "classifier_level": level,
        "top_predictions": predictions,
        "merchant": _extract_merchant(ocr_text),
        "date": _extract_date(ocr_text),
        "suggested_sub_categories": meta["suggested_sub_categories"],
    }
