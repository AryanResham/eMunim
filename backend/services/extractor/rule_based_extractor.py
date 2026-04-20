"""
Regex-based fallback extractor.
Used when LayoutLMv3 confidence for a field is below 0.50,
or when the model is not yet fine-tuned.
"""

from __future__ import annotations
import re

# Patterns for each field key — each is tried against the full OCR text.
# Returns the first match group (stripped), or None if not found.
_PATTERNS: dict[str, list[re.Pattern]] = {
    "invoice_no": [
        re.compile(r'Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)', re.I),
        re.compile(r'INV[.\-/]?\d{2,}', re.I),
    ],
    "invoice_date": [
        re.compile(r'Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', re.I),
        re.compile(r'Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', re.I),
        re.compile(r'Date\s*[:\-]?\s*(\d{1,2}\s+\w{3,9}\s+\d{4})', re.I),
    ],
    "vendor_gstin": [
        re.compile(r'(?:GSTIN|GST\s*No\.?|GST\s*IN)\s*[:\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d])', re.I),
        re.compile(r'(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d])'),
    ],
    "buyer_gstin": [
        re.compile(r'(?:Buyer|Bill\s*To|Recipient)\s*(?:GSTIN|GST)\s*[:\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d])', re.I),
    ],
    "total_amount": [
        re.compile(r'(?:Grand\s*Total|Total\s*Amount|Total\s*Due|Amount\s*Payable)\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
        re.compile(r'Total\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "taxable_amount": [
        re.compile(r'(?:Taxable\s*(?:Value|Amount)|Sub\s*Total)\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "cgst_amount": [
        re.compile(r'CGST\s*(?:@\s*\d+%?)?\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "sgst_amount": [
        re.compile(r'SGST\s*(?:@\s*\d+%?)?\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "igst_amount": [
        re.compile(r'IGST\s*(?:@\s*\d+%?)?\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "amount_due": [
        re.compile(r'(?:Amount\s*Due|Total\s*Due|Net\s*Amount)\s*[:\-]?\s*[₹Rs.]?\s*([\d,]+\.?\d*)', re.I),
    ],
    "consumer_no": [
        re.compile(r'(?:Consumer\s*No\.?|Account\s*No\.?|Meter\s*No\.?)\s*[:\-]?\s*([A-Z0-9\-/]+)', re.I),
    ],
    "due_date": [
        re.compile(r'(?:Due\s*Date|Payment\s*Due)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', re.I),
        re.compile(r'(?:Due\s*Date|Payment\s*Due)\s*[:\-]?\s*(\d{1,2}\s+\w{3,9}\s+\d{4})', re.I),
    ],
}


def extract_field_regex(key: str, text: str) -> tuple[str | None, float]:
    """
    Try all patterns for a given field key against the full OCR text.
    Returns (matched_value, confidence) or (None, 0.0).
    Confidence is fixed at 0.65 for regex matches — lower than LayoutLMv3
    so the UI shows them as less certain.
    """
    for pattern in _PATTERNS.get(key, []):
        m = pattern.search(text)
        if m:
            value = m.group(1).strip() if m.lastindex else m.group(0).strip()
            return value, 0.65
    return None, 0.0


def extract_all_regex(doc_type: str, text: str, label_keys: list[str]) -> dict[str, tuple[str, float]]:
    """
    Run regex extraction for all keys in label_keys.
    Returns dict: { key: (value, confidence) }
    Only includes keys where a match was found.
    """
    results: dict[str, tuple[str, float]] = {}
    for key in label_keys:
        value, conf = extract_field_regex(key, text)
        if value:
            results[key] = (value, conf)
    return results
