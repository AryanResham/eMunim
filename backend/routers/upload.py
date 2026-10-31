import io
import uuid
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import settings
from services.storage import data_dir, write_json
from utils.image_utils import normalize_image
router = APIRouter()
FILE_STORE = {}  # Legacy compatibility only; extraction uses durable files.

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(415, "Send a JPEG or PNG image.")
    raw = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(raw) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Image exceeds {settings.MAX_UPLOAD_MB} MB.")
    try:
        cleaned = normalize_image(raw)
        with Image.open(io.BytesIO(cleaned)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Image cannot be decoded.")
    file_id = str(uuid.uuid4())
    path = data_dir() / "raw_invoices" / (file_id + ".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cleaned)
    result = dict(file_id=file_id, filename=file.filename, page_count=1, mime_type="image/jpeg", width=width, height=height)
    write_json(path.with_suffix(".json"), result)
    return [result]
