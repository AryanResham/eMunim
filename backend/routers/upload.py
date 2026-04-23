import uuid
import io
import os
from pathlib import Path
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils.image_utils import normalize_image

router = APIRouter()

# In-memory store: { file_id: bytes }
FILE_STORE: dict[str, bytes] = {}

UPLOAD_DIR = Path("data/raw_invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}. Send JPEG or PNG.")

    raw = await file.read()
    cleaned = normalize_image(raw)

    img = Image.open(io.BytesIO(cleaned))
    width, height = img.size

    file_id = str(uuid.uuid4())
    
    # Save to disk
    file_extension = "jpg" if file.content_type == "image/jpeg" else "png"
    file_path = UPLOAD_DIR / f"{file_id}.{file_extension}"
    with open(file_path, "wb") as f:
        f.write(cleaned)

    FILE_STORE[file_id] = cleaned

    return [{
        "file_id": file_id,
        "filename": file.filename,
        "file_path": str(file_path),
        "page_count": 1,
        "mime_type": file.content_type,
        "width": width,
        "height": height,
    }]
