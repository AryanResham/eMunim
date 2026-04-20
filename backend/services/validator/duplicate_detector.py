# ============================================================
# CHAITYA — services/validator/duplicate_detector.py
# ============================================================
#
# PURPOSE:
#   Check if an incoming document is a duplicate or near-duplicate
#   of a document already saved in the database.
#   Implement this AFTER Phase 5 (PostgreSQL) is set up.
#   For now, return a passing rule (stub) so the rest of the pipeline works.
#
# FUNCTION TO IMPLEMENT:
#
#   def check_duplicate(
#       doc_type: str,
#       invoice_no: str | None,
#       vendor_name: str | None,
#       total_amount: str | None,
#       db  # SQLAlchemy Session
#   ) -> dict:
#       Returns a single ValidationRule dict: { name, passed, message, severity }
#
#   STEP 1 — Exact duplicate check:
#       If invoice_no is not None:
#           Query: SELECT * FROM documents
#                  WHERE doc_type = doc_type AND invoice_no = invoice_no
#                  LIMIT 1
#           If found: return error — "Invoice {invoice_no} already exists
#                                    (uploaded {existing.created_at.date()})"
#
#   STEP 2 — Near-duplicate check (run only if exact check passes):
#       If vendor_name and total_amount are not None:
#           Query last 30 days of documents with same doc_type
#           For each, compute:
#               name_similarity = difflib.SequenceMatcher(
#                   None, vendor_name.lower(), existing.vendor_name.lower()
#               ).ratio()
#               amount_diff_pct = abs(parsed_total - existing.total_amount) / existing.total_amount
#           If name_similarity > 0.85 AND amount_diff_pct < 0.05:
#               return warning — "Possible near-duplicate: similar vendor and amount found"
#
#   STUB (use this until Phase 5 DB is ready):
#       return { "name": "Duplicate Check", "passed": True,
#                "message": "No duplicate found", "severity": "warning" }
#
# IMPORTS YOU WILL NEED (Phase 5):
#   import difflib
#   from sqlalchemy.orm import Session
#   from models.db_models import Document
#   from decimal import Decimal, InvalidOperation
