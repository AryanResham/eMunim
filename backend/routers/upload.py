# ============================================================
# ARYAN — routers/upload.py
# ============================================================
#
# PURPOSE:
#   Accept a file upload from the frontend and store it temporarily
#   so the OCR router can retrieve it by file_id.
#
# ENDPOINT TO IMPLEMENT:
#
#   POST /api/upload
#   - Accept multipart/form-data with field named "file" (UploadFile)
#   - Validate MIME type: only allow application/pdf, image/jpeg, image/png
#     If invalid: raise HTTPException(status_code=415, detail="Unsupported file type")
#   - If PDF: call pdf_to_images() and concatenate all page bytes (store as list)
#   - If image: call normalize_image() on the raw bytes
#   - Generate a UUID as file_id
#   - Store in module-level dict: FILE_STORE[file_id] = image_bytes  (bytes or list[bytes])
#   - Return: { "file_id": str, "filename": str, "page_count": int, "mime_type": str }
#
# FILE_STORE NOTE:
#   Use a simple in-memory dict for MVP. This is fine for single-user demo.
#   In Phase 5 this will be replaced by saving to disk or object storage.
#
# IMPORTS YOU WILL NEED:
#   import uuid
#   from fastapi import APIRouter, UploadFile, File, HTTPException
#   from utils.image_utils import pdf_to_images, normalize_image

from fastapi import APIRouter

router = APIRouter()

# Temporary in-memory store: { file_id: bytes }
# Aryan: replace the stub below with real implementation
FILE_STORE: dict[str, bytes] = {}


@router.post("/upload")
async def upload_file():
    # TODO: implement file upload
    return {"status": "not implemented"}
