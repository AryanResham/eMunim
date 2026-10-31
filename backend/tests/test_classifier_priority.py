"""Specific document headings must win over incidental generic invoice text."""
import pytest
from services.classifier.l1_regex import classify_l1


@pytest.mark.parametrize("text,expected", [
    ("UTILITY BILL\nExample Electricity Services\nAmount due 500", "UTILITY_BILL"),
    ("PURCHASE BILL\nVendor invoice reference INV-1", "PURCHASE_BILL"),
    ("EXPENSE RECEIPT\nInvoice reference INV-1", "EXPENSE_RECEIPT"),
    ("CREDIT NOTE\nOriginal invoice INV-1", "CREDIT_NOTE"),
    ("DEBIT NOTE\nOriginal invoice INV-1", "DEBIT_NOTE"),
    ("TAX INVOICE\nGSTIN: 27AAPFU0939F1ZV", "GST_INVOICE"),
])
def test_specific_heading_priority(text, expected):
    assert classify_l1(text)[0] == expected
