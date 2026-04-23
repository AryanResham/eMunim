import base64
import re
import httpx
from fastapi import HTTPException
from config import settings
from models.schemas import OCRResult, OCRWord

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"

from utils.confidence_config import (
    OCR_CONFIDENCE_THRESHOLD,
    OCR_DEFAULT_WORD_CONFIDENCE,
    format_ocr_confidence
)


def _fix_numeric(text: str) -> str:
    # Strikethrough lines on scanned docs can make "244.62" look like "244.62.00"
    # If we see two decimal points in a number, drop the last segment
    if re.match(r"^\$?\d+\.\d+\.\d+$", text):
        parts = text.split(".")
        return f"{parts[0]}.{parts[1]}"
    return text


async def run_vision_ocr(image_bytes: bytes) -> OCRResult:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "requests": [{
            "image": {"content": image_b64},
            # DOCUMENT_TEXT_DETECTION is better than TEXT_DETECTION for structured docs
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            VISION_URL,
            params={"key": settings.GOOGLE_CLOUD_VISION_API_KEY},
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    annotation = data["responses"][0].get("fullTextAnnotation", {})
    full_text = annotation.get("text", "")

    words: list[OCRWord] = []
    for page in annotation.get("pages", []):
        for block in page.get("blocks", []):
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    text = "".join(s["text"] for s in word.get("symbols", []))
                    text = _fix_numeric(text)

                    vertices = word.get("boundingBox", {}).get("vertices", [])
                    box = [[v.get("x", 0), v.get("y", 0)] for v in vertices]

                    confidence = word.get("confidence", OCR_DEFAULT_WORD_CONFIDENCE)

                    words.append(OCRWord(
                        text=text,
                        bounding_box=box,
                        confidence=format_ocr_confidence(confidence),
                    ))

    return OCRResult(full_text=full_text, words=words, page_count=1)


async def ocr_document(image_bytes: bytes) -> OCRResult:
    if not settings.GOOGLE_CLOUD_VISION_API_KEY:
        raise HTTPException(503, "OCR unavailable — set GOOGLE_CLOUD_VISION_API_KEY in .env")

    try:
        return await run_vision_ocr(image_bytes)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Vision API error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(503, "Could not reach Vision API — check your connection")
