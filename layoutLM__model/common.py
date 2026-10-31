"""Shared schema, reproducibility and safe artifact I/O for staged CUDA training."""
import hashlib
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))
from services.extractor.field_mapper import LABEL_SETS, DOC_TYPE_TO_MODEL

FUNSD_LABELS = ["O", "B-HEADER", "I-HEADER", "B-QUESTION", "I-QUESTION", "B-ANSWER", "I-ANSWER"]
SROIE_LABELS = ["O"] + [p + name for name in ("COMPANY", "DATE", "ADDRESS", "TOTAL") for p in ("B-", "I-")]
MODEL_REVISION = "cfbbbff0762e6aab37086fdd4739ad14fe7d5db4"
SROIE_REVISION = "f845db1c2ccaf883550320fe450d1e723374be32"


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def weight_file(folder):
    for name in ("model.safetensors", "pytorch_model.bin"):
        path = Path(folder) / name
        if path.is_file():
            return path
    raise FileNotFoundError("Missing model weights: " + str(folder))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def validate_row(row, labels):
    if not row["words"] or not len(row["words"]) == len(row["boxes"]) == len(row["labels"]):
        raise ValueError("Unaligned/empty words, boxes and labels: " + row["id"])
    previous = "O"
    for box, label in zip(row["boxes"], row["labels"]):
        if label not in labels:
            raise ValueError("Unknown label " + label)
        if len(box) != 4 or not all(isinstance(x, int) and 0 <= x <= 1000 for x in box) or box[0] > box[2] or box[1] > box[3]:
            raise ValueError("Invalid normalized box")
        if label.startswith("I-") and previous not in ("B-" + label[2:], label):
            raise ValueError("Invalid BIO continuation")
        previous = label


def seed_all(seed=42):
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def normalize_box(box, width, height):
    return [max(0, min(1000, round(v * 1000 / (width if i % 2 == 0 else height)))) for i, v in enumerate(box)]
