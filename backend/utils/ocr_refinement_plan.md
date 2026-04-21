# OCR Refinement Plan

**Baseline accuracy:** ~95% (tested on scanned typewriter invoice via Google Cloud Vision `DOCUMENT_TEXT_DETECTION`)  
**Target:** ~98%  
**Why it matters:** OCR output feeds directly into the document classifier and LayoutLM v3 — garbage in, garbage out.

---

## Known Failure Modes (from baseline test)

| Error | Example | Root Cause |
|-------|---------|------------|
| Missing characters in words | `Betw` → `Bet` | Low DPI / scan blur causing thin strokes to drop |
| Numeric hallucination from strikethroughs | `$244.62` → `244.62.00` | Strikethrough line read as digits |
| Word segmentation splits | `Gianninoto` → `Giannino` + `to` | Spacing artifacts in scan |
| Missing single character | `Txxxx` → `xxxx` | Low contrast at word boundary |

---

## Phase A — Preprocessing (`utils/image_utils.py`)

These run before bytes are sent to Vision API. Priority order:

1. **DPI enforcement** — upscale to 300 DPI minimum using Pillow. Vision API degrades below 200 DPI. Most scanned docs come in at 150-200.

2. **Contrast stretch** — apply `ImageOps.autocontrast()` to sharpen faded typewriter/print ink and reduce background noise.

3. **Binarization** — convert to grayscale + Otsu threshold. Removes scan artifacts, improves edge clarity for character recognition.

4. **Deskew** — detect and correct tilt (even 1-2° causes character splits). Use Pillow rotate after detecting skew angle via projection profile.

5. **Strikethrough removal** — morphological horizontal erosion to strip horizontal lines that overlap numeric regions. Prevents `244.62` → `244.62.00` class errors.

> Steps 1-3 are MVP. Steps 4-5 are stretch goals if accuracy is still short after initial testing.

---

## Phase B — Post-processing (`utils/ocr_service.py`)

These run on Vision API's JSON output before returning `OCRWord` objects:

1. **Numeric validator** — regex check: if a number contains more than one decimal point, truncate at the second. Catches the `244.62.00` class of errors.

2. **Confidence thresholding** — Vision returns per-symbol confidence scores. Flag any word with mean confidence < 0.85 with a `low_confidence: true` field instead of silently passing bad text to the classifier.

3. **Whitespace normalization** — merge adjacent word tokens that are suspiciously close (bounding box gap < 3px) and share no punctuation boundary. Fixes `Gianninoto` splits.

> Do NOT add dictionary-based correction or NLP here — that's LayoutLM's job.

---

## Definition of "Good Enough" for Downstream

For the **classifier** (teammate's work):
- All document-type keywords must be present: `INVOICE`, `RECEIPT`, `PO`, `TAX`, etc.
- Word order within a line must be correct.
- ~96% word accuracy is the minimum viable threshold.

For **LayoutLM v3**:
- Bounding boxes must be accurate (Vision already provides these — do not discard them).
- Words must map 1:1 to their bounding box — no merged tokens without merged boxes.
- Confidence scores should be passed through as an additional feature if the model supports it.

---

## Implementation Order

```
Phase A (preprocessing):
  normalize_image() in image_utils.py
    └── DPI upscale
    └── autocontrast
    └── binarization
    └── deskew (stretch)
    └── strikethrough removal (stretch)

Phase B (post-processing):
  ocr_document() in ocr_service.py
    └── numeric validator
    └── confidence thresholding
    └── whitespace normalization
```

Both phases slot into the existing Phase 2 work from the main implementation plan.
