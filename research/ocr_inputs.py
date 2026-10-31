"""Capture Google OCR once, then prepare independent corrected-OCR drafts."""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from annotate import write
from run import load_manifest
from models.schemas import OCRResult
from services.ocr_service import ocr_document
from utils.image_utils import normalize_image


def check_ocr(payload, image):
    import io
    from PIL import Image
    value = OCRResult.model_validate(payload)
    with Image.open(io.BytesIO(image)) as im:
        width, height = im.size
    if not value.words or not value.full_text.strip():
        raise ValueError("OCR must contain text and word boxes")
    for word in value.words:
        if not word.text.strip() or any(not (0 <= x <= width and 0 <= y <= height) for x, y in word.bounding_box):
            raise ValueError("OCR words need text and boxes within the image")
    if payload.get("image_sha256") != hashlib.sha256(image).hexdigest():
        raise ValueError("OCR belongs to a different normalized image")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Explicitly permit Google OCR calls")
    parser.add_argument("--max-calls", type=int, default=0)
    args = parser.parse_args()
    data = load_manifest(args.manifest)
    used = 0
    for entry in data["documents"]:
        folder = args.manifest.parent / "ocr"
        google = folder / (entry["id"] + ".google.json")
        corrected = folder / (entry["id"] + ".corrected.json")
        image = normalize_image((args.manifest.parent / entry["image"]).read_bytes())
        if not google.exists():
            if not args.live or used >= args.max_calls:
                print(entry["id"] + ": skipped (no live budget)")
                continue
            used += 1
            result = asyncio.run(ocr_document(image)).model_dump()
            result.update(image_sha256=hashlib.sha256(image).hexdigest(), provenance="google")
            write(google, result)
        result = json.loads(google.read_text(encoding="utf-8"))
        check_ocr(result, image)
        if not corrected.exists():
            write(corrected, {**result, "provenance": "human_corrected_google", "verified": False,
                              "instructions": "Correct word text, boxes, ordering and full_text against the image; then set verified=true. Do not copy field labels into OCR."})
        entry["ocr_google"] = google.relative_to(args.manifest.parent).as_posix()
        entry["ocr_corrected"] = corrected.relative_to(args.manifest.parent).as_posix()
        write(args.manifest, data)
        print(entry["id"] + ": OCR inputs ready (corrected draft is not verified)")
    print(f"Fresh OCR calls: {used}")


if __name__ == "__main__":
    main()
