"""
Prompt construction for the on-device vision-language model (Qwen3-VL).

Builds a JSON-instruction prompt with the doc-type field keys, extraction rules
and optional OCR context so the hybrid and VLM-only pipelines share one shape.
"""

from __future__ import annotations

import json
import re
from typing import Any

from services.extractor.field_mapper import get_label_set


def _doc_field_keys(doc_type: str) -> list[str]:
    return [
        label[2:].lower()
        for label in get_label_set(doc_type)
        if label.startswith("B-")
    ]


def _group_ocr_words_into_lines(
    ocr_words: list[dict[str, Any]], tolerance: int = 12
) -> list[dict[str, Any]]:
    """Flatten OCR words (bounding_box + text) into left-to-right text lines."""
    if not ocr_words:
        return []

    flattened: list[dict[str, Any]] = []
    for word in ocr_words:
        bbox = word.get("bounding_box") or []
        if not bbox:
            continue
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        flattened.append(
            {
                "text": text,
                "x_min": min(xs),
                "y_min": min(ys),
                "x_max": max(xs),
                "y_max": max(ys),
            }
        )

    if not flattened:
        return []

    flattened.sort(key=lambda word: (word["y_min"], word["x_min"]))
    rows: list[list[dict[str, Any]]] = []
    current_row = [flattened[0]]
    current_y = flattened[0]["y_min"]

    for word in flattened[1:]:
        if abs(word["y_min"] - current_y) <= tolerance:
            current_row.append(word)
        else:
            rows.append(sorted(current_row, key=lambda item: item["x_min"]))
            current_row = [word]
            current_y = word["y_min"]

    if current_row:
        rows.append(sorted(current_row, key=lambda item: item["x_min"]))

    return [
        {
            "text": " ".join(word["text"] for word in row),
            "bbox": [
                row[0]["x_min"],
                min(word["y_min"] for word in row),
                row[-1]["x_max"],
                max(word["y_max"] for word in row),
            ],
        }
        for row in rows
    ]


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def build_prompt(
    *,
    doc_type: str,
    ocr_text: str | None = None,
    ocr_words: list[dict[str, Any]] | None = None,
) -> str:
    """
    Build the JSON instruction prompt for the vision-language model.

    When OCR text/words are provided (ocr_vlm / layoutlm fallback pipelines),
    the prompt includes the OCR transcript plus spatially re-arranged lines so
    the model can cross-check the image text. For vlm_only the model works
    directly from the image alone.
    """
    field_keys = _doc_field_keys(doc_type)

    instructions: dict[str, Any] = {
        "task": "Extract structured accounting fields from the document image.",
        "doc_type": doc_type,
        "required_fields": field_keys,
        "rules": [
            "Return valid JSON only.",
            "Use null when a field is not present.",
            "Do not invent values.",
            "Prefer visible label-value pairs and clear totals over incidental text.",
            "For GSTIN fields, return only valid 15-character GSTIN strings.",
            "For amount fields, return the exact amount string as printed in the document.",
            "For date fields, return the exact date string as printed in the document.",
        ],
        "output_schema": {
            "doc_type": doc_type,
            "fields": {key: None for key in field_keys},
            "reasoning_notes": [],
        },
    }

    if ocr_text:
        instructions["ocr_text"] = ocr_text[:15000]
    if ocr_words:
        instructions["layout_lines"] = _group_ocr_words_into_lines(ocr_words)[:120]

    return json.dumps(instructions, ensure_ascii=False, indent=2)


def reinforce_json(prompt: str) -> str:
    """Nudge prompt for the single parse-retry after a non-JSON response."""
    return (
        prompt
        + "\n\nIMPORTANT: Your previous response was not valid JSON. "
        "Return ONLY valid JSON matching output_schema exactly. "
        "No markdown fences, no commentary."
    )