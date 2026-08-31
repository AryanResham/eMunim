import uuid
import io
from PIL import Image
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import StoredFile, User
from services.local_storage import read_file, save_file
from utils.image_utils import normalize_image

router = APIRouter()

# In-process cache so repeated reads within the same request cycle avoid a disk hit.
# Disk (services/local_storage.py) is the real source of truth — it survives a restart.
FILE_STORE: dict[str, bytes] = {}

ALLOWED_MIME = {"image/jpeg", "image/png"}


def get_file_bytes(file_id: str) -> bytes | None:
    if file_id in FILE_STORE:
        return FILE_STORE[file_id]
    data = read_file(file_id)
    if data is not None:
        FILE_STORE[file_id] = data
    return data


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}. Send JPEG or PNG.")

    raw = await file.read()
    cleaned = normalize_image(raw)

    img = Image.open(io.BytesIO(cleaned))
    width, height = img.size

    file_id = str(uuid.uuid4())
    FILE_STORE[file_id] = cleaned
    save_file(file_id, cleaned)

    db.add(StoredFile(
        file_id=file_id,
        user_id=current_user.id,
        original_filename=file.filename or "",
        mime_type=file.content_type,
        file_size=len(cleaned),
        page_count=1,
        width=width,
        height=height,
    ))
    db.commit()

    return {
        "file_id": file_id,
        "filename": file.filename,
        "page_count": 1,
        "mime_type": file.content_type,
        "width": width,
        "height": height,
    }
