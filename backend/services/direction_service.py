"""
Decides whether a document represents money the business owes (payable) or
money it's owed (receivable) — entirely derived from already-extracted
fields, with no changes to Upload/OCR/Classify/Extract.

Every document type except GST_INVOICE only ever extracts one party
(vendor_name/vendor_gstin) — a purchase bill, expense receipt, or utility
bill is always something the business bought, never something it sold, so
those are always 'payable'. GST_INVOICE is the only ambiguous case, because
it's the same document shape whether the business received it from a
supplier or issued it to a customer — the only way to tell is by comparing
the extracted GSTINs against the business's own GSTIN (Settings).
"""

DEFAULT_DIRECTION = "payable"


def determine_direction(fields: dict[str, str], business_gstin: str | None) -> str:
    business_gstin = (business_gstin or "").strip().upper()
    if not business_gstin:
        return DEFAULT_DIRECTION

    vendor_gstin = (fields.get("vendor_gstin") or "").strip().upper()
    if vendor_gstin and vendor_gstin == business_gstin:
        # The business is the seller on this document — money coming in.
        return "receivable"

    # Any other case (business GSTIN matches buyer_gstin, or matches nothing,
    # or the doc type has no buyer_gstin at all) is a bill the business received.
    return DEFAULT_DIRECTION
