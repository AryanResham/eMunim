"""Shared field schema; schema membership does not imply mandatory presence."""
from services.extractor.field_mapper import get_label_set, get_field_meta

REQUIRED = {
    "GST_INVOICE": ["invoice_no", "invoice_date", "vendor_name", "vendor_gstin", "taxable_amount", "total_amount"],
    "PURCHASE_BILL": ["bill_no", "bill_date", "vendor_name", "total_amount"],
    "EXPENSE_RECEIPT": ["receipt_date", "vendor_name", "amount"],
    "UTILITY_BILL": ["consumer_no", "bill_date", "utility_provider", "amount_due"],
    "CREDIT_NOTE": ["credit_note_no", "credit_note_date", "vendor_name", "credit_amount"],
    "DEBIT_NOTE": ["debit_note_no", "debit_note_date", "vendor_name", "debit_amount"],
}
DATE_KEYS = {k for keys in REQUIRED.values() for k in keys if k.endswith("_date")} | {"due_date"}
AMOUNT_KEYS = {"taxable_amount", "total_amount", "cgst_amount", "sgst_amount", "igst_amount", "subtotal", "tax_amount", "amount", "amount_due", "credit_amount", "tax_credit", "debit_amount"}

def keys_for(doc_type):
    return [label[2:].lower() for label in get_label_set(doc_type) if label.startswith("B-")]

def canonical_fields(doc_type, fields):
    by_key = {f["key"]: f for f in fields}
    result = []
    for key in keys_for(doc_type):
        meta = get_field_meta(key)
        result.append({"key": key, "label": meta["label"], "value": None, "confidence": None,
                       "editable": True, "monospace": meta["monospace"], "source": "missing",
                       **by_key.get(key, {})})
    return result
