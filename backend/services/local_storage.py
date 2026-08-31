"""
Local disk-backed file storage for uploaded documents.
Dev-stage implementation — swap for S3/R2 in production by keeping this same
save_file/read_file/delete_file interface.
"""
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent.parent / "uploads" / "files"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_file(file_id: str, content: bytes) -> str:
    path = STORAGE_DIR / file_id
    path.write_bytes(content)
    return str(path)


def read_file(file_id: str) -> bytes | None:
    path = STORAGE_DIR / file_id
    if not path.exists():
        return None
    return path.read_bytes()


def delete_file(file_id: str) -> None:
    path = STORAGE_DIR / file_id
    if path.exists():
        path.unlink()
