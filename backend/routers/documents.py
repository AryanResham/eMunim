from fastapi import APIRouter

router = APIRouter()


# TODO (Phase 5 — All):
# POST /api/documents  — save validated document to PostgreSQL
# GET  /api/documents  — paginated list with filters (doc_type, from_date, to_date)
# GET  /api/documents/summary — count + total_amount per doc_type for dashboard
# GET  /api/documents/export/csv — stream CSV of filtered documents

@router.get("/documents")
def list_documents():
    return {"status": "not implemented"}
