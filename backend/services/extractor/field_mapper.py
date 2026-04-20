"""
Defines the BIO label set and display metadata for each document type.
LayoutLMv3 is fine-tuned separately per doc type, each with its own label set.
"""

from __future__ import annotations

# BIO label sets — "O" (outside) must always be at index 0.
# Each B- label is followed immediately by its I- continuation.
LABEL_SETS: dict[str, list[str]] = {
    "GST_INVOICE": [
        "O",
        "B-INVOICE_NO",    "I-INVOICE_NO",
        "B-INVOICE_DATE",  "I-INVOICE_DATE",
        "B-VENDOR_NAME",   "I-VENDOR_NAME",
        "B-VENDOR_GSTIN",  "I-VENDOR_GSTIN",
        "B-BUYER_NAME",    "I-BUYER_NAME",
        "B-BUYER_GSTIN",   "I-BUYER_GSTIN",
        "B-TAXABLE_AMOUNT","I-TAXABLE_AMOUNT",
        "B-CGST_AMOUNT",   "I-CGST_AMOUNT",
        "B-SGST_AMOUNT",   "I-SGST_AMOUNT",
        "B-IGST_AMOUNT",   "I-IGST_AMOUNT",
        "B-TOTAL_AMOUNT",  "I-TOTAL_AMOUNT",
        "B-DUE_DATE",      "I-DUE_DATE",
        "B-PO_NUMBER",     "I-PO_NUMBER",
    ],
    "PURCHASE_BILL": [
        "O",
        "B-BILL_NO",       "I-BILL_NO",
        "B-BILL_DATE",     "I-BILL_DATE",
        "B-VENDOR_NAME",   "I-VENDOR_NAME",
        "B-VENDOR_GSTIN",  "I-VENDOR_GSTIN",
        "B-SUBTOTAL",      "I-SUBTOTAL",
        "B-TAX_AMOUNT",    "I-TAX_AMOUNT",
        "B-TOTAL_AMOUNT",  "I-TOTAL_AMOUNT",
        "B-PAYMENT_TERMS", "I-PAYMENT_TERMS",
    ],
    "EXPENSE_RECEIPT": [
        "O",
        "B-VENDOR_NAME",   "I-VENDOR_NAME",
        "B-RECEIPT_DATE",  "I-RECEIPT_DATE",
        "B-RECEIPT_NO",    "I-RECEIPT_NO",
        "B-AMOUNT",        "I-AMOUNT",
        "B-TAX_AMOUNT",    "I-TAX_AMOUNT",
        "B-PAYMENT_MODE",  "I-PAYMENT_MODE",
        "B-CATEGORY",      "I-CATEGORY",
    ],
    "UTILITY_BILL": [
        "O",
        "B-CONSUMER_NO",      "I-CONSUMER_NO",
        "B-BILL_DATE",        "I-BILL_DATE",
        "B-DUE_DATE",         "I-DUE_DATE",
        "B-BILLING_PERIOD",   "I-BILLING_PERIOD",
        "B-UNITS_CONSUMED",   "I-UNITS_CONSUMED",
        "B-AMOUNT_DUE",       "I-AMOUNT_DUE",
        "B-UTILITY_PROVIDER", "I-UTILITY_PROVIDER",
        "B-ACCOUNT_NAME",     "I-ACCOUNT_NAME",
    ],
    "CREDIT_NOTE": [
        "O",
        "B-CREDIT_NOTE_NO",       "I-CREDIT_NOTE_NO",
        "B-CREDIT_NOTE_DATE",     "I-CREDIT_NOTE_DATE",
        "B-ORIGINAL_INVOICE_NO",  "I-ORIGINAL_INVOICE_NO",
        "B-VENDOR_NAME",          "I-VENDOR_NAME",
        "B-VENDOR_GSTIN",         "I-VENDOR_GSTIN",
        "B-REASON",               "I-REASON",
        "B-CREDIT_AMOUNT",        "I-CREDIT_AMOUNT",
        "B-TAX_CREDIT",           "I-TAX_CREDIT",
    ],
    "DEBIT_NOTE": [
        "O",
        "B-DEBIT_NOTE_NO",        "I-DEBIT_NOTE_NO",
        "B-DEBIT_NOTE_DATE",      "I-DEBIT_NOTE_DATE",
        "B-ORIGINAL_INVOICE_NO",  "I-ORIGINAL_INVOICE_NO",
        "B-VENDOR_NAME",          "I-VENDOR_NAME",
        "B-VENDOR_GSTIN",         "I-VENDOR_GSTIN",
        "B-REASON",               "I-REASON",
        "B-DEBIT_AMOUNT",         "I-DEBIT_AMOUNT",
        "B-TAX_AMOUNT",           "I-TAX_AMOUNT",
    ],
}

# Human-readable labels and display flags per field key
FIELD_META: dict[str, dict] = {
    "invoice_no":          {"label": "Invoice No.",       "editable": False, "monospace": True},
    "invoice_date":        {"label": "Invoice Date",      "editable": True,  "monospace": False},
    "vendor_name":         {"label": "Vendor Name",       "editable": True,  "monospace": False},
    "vendor_gstin":        {"label": "Vendor GSTIN",      "editable": False, "monospace": True},
    "buyer_name":          {"label": "Buyer Name",        "editable": True,  "monospace": False},
    "buyer_gstin":         {"label": "Buyer GSTIN",       "editable": False, "monospace": True},
    "taxable_amount":      {"label": "Taxable Amount",    "editable": True,  "monospace": True},
    "cgst_amount":         {"label": "CGST",              "editable": True,  "monospace": True},
    "sgst_amount":         {"label": "SGST",              "editable": True,  "monospace": True},
    "igst_amount":         {"label": "IGST",              "editable": True,  "monospace": True},
    "total_amount":        {"label": "Total Amount",      "editable": True,  "monospace": True},
    "due_date":            {"label": "Due Date",          "editable": True,  "monospace": False},
    "po_number":           {"label": "PO Number",         "editable": True,  "monospace": True},
    "bill_no":             {"label": "Bill No.",          "editable": False, "monospace": True},
    "bill_date":           {"label": "Bill Date",         "editable": True,  "monospace": False},
    "subtotal":            {"label": "Subtotal",          "editable": True,  "monospace": True},
    "tax_amount":          {"label": "Tax Amount",        "editable": True,  "monospace": True},
    "payment_terms":       {"label": "Payment Terms",     "editable": True,  "monospace": False},
    "receipt_date":        {"label": "Receipt Date",      "editable": True,  "monospace": False},
    "receipt_no":          {"label": "Receipt No.",       "editable": False, "monospace": True},
    "amount":              {"label": "Amount",            "editable": True,  "monospace": True},
    "payment_mode":        {"label": "Payment Mode",      "editable": True,  "monospace": False},
    "category":            {"label": "Category",          "editable": True,  "monospace": False},
    "consumer_no":         {"label": "Consumer No.",      "editable": False, "monospace": True},
    "billing_period":      {"label": "Billing Period",    "editable": True,  "monospace": False},
    "units_consumed":      {"label": "Units Consumed",    "editable": True,  "monospace": True},
    "amount_due":          {"label": "Amount Due",        "editable": True,  "monospace": True},
    "utility_provider":    {"label": "Provider",          "editable": True,  "monospace": False},
    "account_name":        {"label": "Account Name",      "editable": True,  "monospace": False},
    "credit_note_no":      {"label": "Credit Note No.",   "editable": False, "monospace": True},
    "credit_note_date":    {"label": "Date",              "editable": True,  "monospace": False},
    "original_invoice_no": {"label": "Ref Invoice No.",   "editable": True,  "monospace": True},
    "reason":              {"label": "Reason",            "editable": True,  "monospace": False},
    "credit_amount":       {"label": "Credit Amount",     "editable": True,  "monospace": True},
    "tax_credit":          {"label": "GST Reversal",      "editable": True,  "monospace": True},
    "debit_note_no":       {"label": "Debit Note No.",    "editable": False, "monospace": True},
    "debit_note_date":     {"label": "Date",              "editable": True,  "monospace": False},
    "debit_amount":        {"label": "Debit Amount",      "editable": True,  "monospace": True},
}


def get_label_set(doc_type: str) -> list[str]:
    return LABEL_SETS[doc_type]


def get_num_labels(doc_type: str) -> int:
    return len(LABEL_SETS[doc_type])


def bio_label_to_key(bio_label: str) -> str:
    """Convert 'B-INVOICE_NO' → 'invoice_no'"""
    return bio_label[2:].lower()


def get_field_meta(key: str) -> dict:
    return FIELD_META.get(key, {"label": key.replace("_", " ").title(), "editable": True, "monospace": False})
