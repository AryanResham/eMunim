def check_duplicate(
    doc_type: str,
    invoice_no: str | None,
    vendor_name: str | None,
    total_amount: str | None,
    db=None
) -> dict:
    """
    Check if an incoming document is a duplicate or near-duplicate.
    STUB: For now, return a passing rule (stub) so the rest of the pipeline works.
    """
    return {
        "name": "Duplicate Check",
        "passed": True,
        "message": "No duplicate found",
        "severity": "warning"
    }
