# Phase 2 — What Was Built

## The Goal
Get images ready for Google Cloud Vision, send them, and get back structured text with positions and confidence scores.

---

## `utils/image_utils.py` — Image Cleaner

Before sending any image to Vision API, we clean it up:

1. **Convert to RGB** — some images are grayscale or have transparency layers. Vision API expects plain RGB.
2. **Boost contrast** — faded scans and old documents have low contrast. This step makes the ink pop so Vision reads it better.
3. **Resize to 2048px max** — Vision API has a 4MB limit. We scale down large images while keeping the shape intact. We never upscale — that adds blur, not detail.
4. **Save as JPEG at 300 DPI** — standard quality for document scanning.

> This is why accuracy improved — Vision gets a clean image instead of a raw noisy scan.

---

## `services/ocr_service.py` — OCR Brain

Three things live here:

### `_fix_numeric(text)`
A small cleanup function. Strikethrough lines on scanned invoices can trick Vision into reading `$244.62` as `$244.62.00`. This detects that pattern and fixes it.

### `run_vision_ocr(image_bytes)`
- Takes the cleaned image bytes
- Sends it to Google Cloud Vision using `DOCUMENT_TEXT_DETECTION` (better than basic `TEXT_DETECTION` for invoices and structured docs)
- Gets back every word, its position on the page (bounding box), and how confident Vision was (0.0 to 1.0)
- Returns everything as a structured `OCRResult` object

### `ocr_document(image_bytes)`
The only function the rest of the app talks to. It:
- Checks that the API key exists before doing anything
- Calls `run_vision_ocr`
- Returns clean errors if Vision is unreachable or the key is wrong

---

## What the Output Looks Like

Every word comes back as:
```
text        → the actual word, e.g. "INVOICE"
bounding_box → where it is on the page [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
confidence  → how sure Vision was, e.g. 0.9821
```

The bounding boxes are what LayoutLM v3 needs to understand document layout. The confidence scores let the classifier know which words to trust.

---

## What's Next
- Wire up the routers (`upload.py`, `ocr.py`) so the frontend can talk to this
- Phase 4: add PDF support
