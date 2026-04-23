from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from config import settings
from services.extractor.field_mapper import get_field_meta, get_label_set
from utils.confidence_config import LAYOUTLLM_LLM_CONFIDENCE


TESTS_DIR = Path(__file__).resolve().parent
RESPONSE_PATH = TESTS_DIR / "response.txt"


def _doc_field_keys(doc_type: str) -> list[str]:
    return [
        label[2:].lower()
        for label in get_label_set(doc_type)
        if label.startswith("B-")
    ]


def _image_data_url(image_bytes: bytes, filename: str | None = None) -> str:
    mime_type, _ = mimetypes.guess_type(filename or "")
    mime_type = mime_type or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


def _group_ocr_words_into_lines(ocr_words: list[dict[str, Any]], tolerance: int = 12) -> list[dict[str, Any]]:
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


def _build_prompt_payload(doc_type: str, ocr_text: str, ocr_words: list[dict[str, Any]]) -> str:
    field_keys = _doc_field_keys(doc_type)
    layout_lines = _group_ocr_words_into_lines(ocr_words)

    instructions = {
        "task": "Extract structured accounting fields from the document.",
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
        "ocr_text": ocr_text[:15000],
        "layout_lines": layout_lines[:120],
    }
    return json.dumps(instructions, ensure_ascii=False, indent=2)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_response_text(payload: dict[str, Any]) -> str:
    if "choices" in payload:
        message = payload["choices"][0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            return "\n".join(part for part in text_parts if part)

    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    if isinstance(payload.get("output"), list):
        text_parts: list[str] = []
        for item in payload["output"]:
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    text_parts.append(content["text"])
        return "\n".join(text_parts)

    raise ValueError("Could not find text content in the provider response")


def _normalize_fields(doc_type: str, fields_payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in _doc_field_keys(doc_type):
        value = fields_payload.get(key)
        if value is None:
            continue
        value_str = str(value).strip()
        if not value_str:
            continue
        meta = get_field_meta(key)
        result.append(
            {
                "key": key,
                "label": meta["label"],
                "value": value_str,
                "confidence": LAYOUTLLM_LLM_CONFIDENCE,
                "editable": meta["editable"],
                "monospace": meta["monospace"],
                "source": "layoutllm",
            }
        )
    return result


def _write_response_file(
    doc_type: str,
    fields: list[dict[str, Any]],
    request_payload: dict[str, Any],
    raw_response: dict[str, Any],
) -> None:
    sanitized_request = json.loads(json.dumps(request_payload))
    try:
        sanitized_request["messages"][1]["content"][1]["image_url"]["url"] = "<omitted data url>"
    except (KeyError, IndexError, TypeError):
        pass

    payload = {
        "timestamp": datetime.now().isoformat(),
        "doc_type": doc_type,
        "response_path": str(RESPONSE_PATH),
        "request_model": settings.LAYOUTLLM_MODEL,
        "request_base_url": settings.LAYOUTLLM_BASE_URL,
        "fields": fields,
        "raw_response": raw_response,
    }

    lines = [
        "LayoutLLM Test Inference",
        "=" * 60,
        f"doc_type: {doc_type}",
        f"model: {settings.LAYOUTLLM_MODEL}",
        f"base_url: {settings.LAYOUTLLM_BASE_URL}",
        f"timestamp: {payload['timestamp']}",
        "",
        "Selected Fields:",
    ]

    if not fields:
        lines.append("No fields were returned by the LayoutLLM engine.")
    else:
        for field in fields:
            lines.append(f"- {field['key']}: {field['value']} (source={field['source']})")

    lines.extend(
        [
            "",
            "Request Payload:",
            json.dumps(sanitized_request, indent=2, ensure_ascii=False),
            "",
            "Raw Provider Response:",
            json.dumps(raw_response, indent=2, ensure_ascii=False),
            "",
            "JSON:",
            json.dumps(payload, indent=2, ensure_ascii=False),
        ]
    )
    RESPONSE_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_error_response(doc_type: str, error_message: str) -> None:
    lines = [
        "LayoutLLM Test Inference",
        "=" * 60,
        f"doc_type: {doc_type}",
        f"model: {settings.LAYOUTLLM_MODEL}",
        f"base_url: {settings.LAYOUTLLM_BASE_URL}",
        f"timestamp: {datetime.now().isoformat()}",
        "",
        "Status: ERROR",
        error_message,
    ]
    RESPONSE_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_layoutllm_real_flow(
    *,
    image_bytes: bytes,
    file_name: str | None,
    ocr_result: dict[str, Any],
    doc_type: str,
) -> dict[str, Any]:
    if not settings.LAYOUTLLM_API_KEY:
        error = "LAYOUTLLM_API_KEY is not set in backend/.env"
        _write_error_response(doc_type, error)
        raise RuntimeError(error)

    request_payload = {
        "model": settings.LAYOUTLLM_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a document extraction engine. "
                            "Use the image and OCR together. Return JSON only."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_prompt_payload(
                            doc_type=doc_type,
                            ocr_text=str(ocr_result.get("full_text", "")),
                            ocr_words=list(ocr_result.get("words", [])),
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(image_bytes, file_name)},
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.LAYOUTLLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{settings.LAYOUTLLM_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()
            raw_response = response.json()

        response_text = _extract_response_text(raw_response)
        parsed_json = json.loads(_strip_json_fence(response_text))
        fields_payload = parsed_json.get("fields", parsed_json)
        if not isinstance(fields_payload, dict):
            raise ValueError("LLM response did not contain a valid object-like 'fields' payload")

        fields = _normalize_fields(doc_type, fields_payload)
        _write_response_file(doc_type, fields, request_payload, raw_response)

        return {
            "doc_type": doc_type,
            "response_path": str(RESPONSE_PATH),
            "fields": fields,
            "raw_response": raw_response,
        }
    except Exception as exc:
        _write_error_response(doc_type, str(exc))
        raise
