import uuid
import io
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils.image_utils import normalize_image

router = APIRouter()

# In-memory store: { file_id: bytes }
FILE_STORE: dict[str, bytes] = {}

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
    FILE_STORE[file_id] = cleaned

    return {
        "file_id": file_id,
        "filename": file.filename,
        "page_count": 1,
        "mime_type": file.content_type,
        "width": width,
        "height": height,
    }
