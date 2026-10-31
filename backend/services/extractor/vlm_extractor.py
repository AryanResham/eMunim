"""
On-device vision-language extraction engine (Qwen3-VL via transformers).

The model is loaded lazily once and cached. Running on an in-process model means
the `vlm_only` and `ocr_vlm` pipelines never round-trip the image bytes through
an external service.

Loading is VRAM-aware: bf16 on CUDA when it fits, optional 4-bit (bitsandbytes)
for small GPUs, and a CPU fp32 fallback instead of a hard out-of-memory error.
"""

from __future__ import annotations

import gc
import io
import json
from pathlib import Path
from typing import Any

import torch
from PIL import Image

from config import ENV_PATH, settings
from services.extractor.field_mapper import get_field_meta
from services.extractor.vlm_prompt import (
    _doc_field_keys,
    _strip_json_fence,
    build_prompt,
    reinforce_json,
)
from utils.confidence_config import VLM_FIELD_CONFIDENCE

_loaded: dict[str, Any] = {
    "processor": None,
    "model": None,
    "device": None,
    "dtype": None,
}
_REPO_ROOT = Path(ENV_PATH).resolve().parent.parent


def _model_source() -> str:
    """Local weights dir if VLM_MODEL_DIR is set and exists, else the HF repo id."""
    raw = settings.VLM_MODEL_DIR.strip()
    if raw:
        local = Path(raw)
        if not local.is_absolute():
            local = _REPO_ROOT / local
        if local.is_dir():
            return str(local)
        print(f"VLM_MODEL_DIR '{local}' not found — falling back to repo id '{settings.VLM_MODEL}'")
    return settings.VLM_MODEL


def _hardware_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_model() -> tuple[Any, Any, str, torch.dtype]:
    """Lazy-load and cache the VLM (processor, model, device, dtype)."""
    if _loaded["model"] is not None:
        return _loaded["model"], _loaded["processor"], _loaded["device"], _loaded["dtype"]

    from transformers import AutoModelForImageTextToText, AutoProcessor

    model_source = _model_source()
    processor = AutoProcessor.from_pretrained(model_source)

    device = _hardware_device()
    model = None
    placed = False
    dtype: torch.dtype = torch.float32

    if device == "cuda":
        try:
            if settings.VLM_LOAD_IN_2BIT:
                from transformers import BitsAndBytesConfig

                quant_config = BitsAndBytesConfig(
                    load_in_2Bit=True, bnb_2Bit_compute_dtype=torch.bfloat16
                )
                model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    quantization_config=quant_config,
                    device_map="auto",
                )
                placed = True
            else:
                dtype = torch.bfloat16
                model = AutoModelForImageTextToText.from_pretrained(
                    model_source,
                    torch_dtype=dtype,
                    attn_implementation="sdpa",
                )
                model.to("cuda")
                placed = True
        except (torch.cuda.OutOfMemoryError, ImportError, RuntimeError, ValueError) as exc:
            print(f"VLM load on CUDA failed ({type(exc).__name__}: {exc}) — falling back to CPU fp32")
            del model
            gc.collect()
            torch.cuda.empty_cache()
            device, dtype = "cpu", torch.float32
            model = None
            placed = False

    if model is None:
        model = AutoModelForImageTextToText.from_pretrained(
            model_source,
            torch_dtype=dtype,
            attn_implementation="sdpa",
        )

    if not placed:
        model.to(device)
    model.eval()

    _loaded.update(processor=processor, model=model, device=device, dtype=dtype)
    return model, processor, device, dtype


def _generate(prompt: str, image_bytes: bytes) -> str:
    """Run one generation pass and return the decoded text (without the prompt)."""
    model, processor, device, dtype = _load_model()
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": pil_image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(device, dtype=dtype)

    # transformers >=4.58 may return a ChatTemplateInput object rather than a
    # plain dict depending on the architecture (Qwen3-VL); handle both.
    input_len = (
        inputs.input_ids.shape[1] if hasattr(inputs, "input_ids") else inputs["input_ids"].shape[1]
    )

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            do_sample=False,
            max_new_tokens=settings.VLM_MAX_NEW_TOKENS,
        )

    output_ids = generated_ids[:, input_len:]
    return processor.batch_decode(output_ids, skip_special_tokens=True)[0]


def _parse_response(text: str) -> dict[str, Any]:
    parsed = json.loads(_strip_json_fence(text))
    if not isinstance(parsed, dict):
        raise ValueError("VLM response was not a JSON object")
    fields_payload = parsed.get("fields", parsed)
    if not isinstance(fields_payload, dict):
        raise ValueError("VLM response did not contain a 'fields' object")
    return fields_payload


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
                "confidence": VLM_FIELD_CONFIDENCE,
                "editable": meta["editable"],
                "monospace": meta["monospace"],
                "source": "vlm",
            }
        )
    return result


def _run_with_retry(prompt: str, image_bytes: bytes, doc_type: str) -> list[dict[str, Any]]:
    try:
        fields_payload = _parse_response(_generate(prompt, image_bytes))
        return _normalize_fields(doc_type, fields_payload)
    except (json.JSONDecodeError, ValueError) as first_exc:
        fields_payload = _parse_response(_generate(reinforce_json(prompt), image_bytes))
        return _normalize_fields(doc_type, fields_payload)


def extract_fields_from_image(*, image_bytes: bytes, doc_type: str) -> list[dict[str, Any]]:
    """Pipeline `vlm_only`: extract directly from the image, no OCR context."""
    prompt = build_prompt(doc_type=doc_type)
    return _run_with_retry(prompt, image_bytes, doc_type)


def extract_fields_from_image_and_ocr(
    *, image_bytes: bytes, doc_type: str, ocr_result: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Pipelines `ocr_vlm` + `layoutlm_fallback_vlm`: image plus OCR context."""
    ocr_text = str(ocr_result.get("full_text", "")) if ocr_result else ""
    ocr_words = list(ocr_result.get("words", [])) if ocr_result else []
    prompt = build_prompt(doc_type=doc_type, ocr_text=ocr_text, ocr_words=ocr_words)
    return _run_with_retry(prompt, image_bytes, doc_type)