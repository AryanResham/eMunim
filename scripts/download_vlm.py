#!/usr/bin/env python3
"""
Clear any previous Qwen3-VL-2B download and re-download fresh into the repo.

Usage:
  python scripts/download_vlm.py          # run from repo root
  python -m scripts.download_vlm          # alternative
"""

import os
import shutil
import sys
from pathlib import Path

# Ensure repo root is on sys.path for backend imports if ever needed.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
LOCAL_DIR = REPO_ROOT / "models" / "qwen3-vl-2b"
CACHE_DIR = Path(os.path.expanduser("~/.cache/huggingface/hub")).resolve()
MODEL_CACHE = CACHE_DIR / f"models--{MODEL_ID.replace('/', '--')}"


def _rm(path: Path) -> None:
    if path.exists():
        print(f"  Removing: {path}")
        shutil.rmtree(path, ignore_errors=True)


print("[1/4] Clearing previous local download …")
_rm(LOCAL_DIR)

print("[2/4] Clearing HF cache for this model …")
_rm(MODEL_CACHE)

LOCAL_DIR.mkdir(parents=True, exist_ok=True)

# New Xet backend (replaces the deprecated HF_HUB_ENABLE_HF_TRANSFER).
os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
# Backward compat for older huggingface_hub versions.
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

print(f"[3/4] Downloading {MODEL_ID} into {LOCAL_DIR}  (this takes a while) …")
saved = snapshot_download(
    repo_id=MODEL_ID,
    local_dir=str(LOCAL_DIR),
    max_workers=8,
)

print(f"[4/4] Done — saved to {saved}")
print(f"       Dir size: {sum(f.stat().st_size for f in LOCAL_DIR.rglob('*') if f.is_file()) / 1e9:.1f} GB")
