from __future__ import annotations
import io
from functools import lru_cache
from functools import wraps
import threading
import time

from .field_mapper import (
    get_label_set, get_num_labels, bio_label_to_key, get_field_meta, get_model_folder,
)
from .rule_based_extractor import extract_all_regex
from .ocr_compounds import normalize_compounds,assemble_field_text,VERSION as COMPOUND_VERSION

# Cache one (processor, model, labels) tuple per model_key / per doc_type to
# avoid reloading.
_models: dict[str, tuple | None] = {}
_inference_lock = threading.RLock()


def _serial_inference(function):
    @wraps(function)
    def run(*args, **kwargs):
        with _inference_lock:
            return function(*args, **kwargs)
    return run


def release_models():
    """Explicitly release all cached models when no request is in flight."""
    with _inference_lock:
        _models.clear()
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

@lru_cache(maxsize=16)
def _weight_hash(path: str, modified_ns: int) -> str:
    import hashlib
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

from utils.confidence_config import EXTRACTOR_LAYOUTLM_THRESHOLD, format_confidence


def _normalize_bbox(vertices: list[list[int]], width: int, height: int) -> list[int]:
    """
    Scale a 4-point bounding box from pixel coords to 0-1000 range.
    Input:  [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    Output: [x_min_norm, y_min_norm, x_max_norm, y_max_norm]
    """
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    return [
        int(1000 * min(xs) / width),
        int(1000 * min(ys) / height),
        int(1000 * max(xs) / width),
        int(1000 * max(ys) / height),
    ]


def _model_root() -> str:
    from pathlib import Path
    from config import settings
    return str(Path(settings.LAYOUTLM_MODEL_ROOT).resolve())


def _cache_key(name: str) -> str:
    from config import settings
    return f"{_model_root()}::{settings.LAYOUTLM_DEVICE}::{name}"


def _folder_has_weights(folder: str) -> bool:
    from pathlib import Path
    p = Path(_model_root()) / folder
    if not p.is_dir():
        return False
    return (p / "model.safetensors").is_file() or (p / "pytorch_model.bin").is_file()


def _load_model(folder: str) -> tuple | None:
    """Try to load a LayoutLMv3 processor+model from `folder` under layoutLM model/."""
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
    try:
        model_path = f"{_model_root()}/{folder}"
        processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=False, local_files_only=True)
        model = LayoutLMv3ForTokenClassification.from_pretrained(model_path, local_files_only=True)
        import torch
        from config import settings
        if settings.LAYOUTLM_DEVICE == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")
        device = "cuda" if settings.LAYOUTLM_DEVICE != "cpu" and torch.cuda.is_available() else "cpu"
        model.to(device)
        model.eval()
        labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
        return (processor, model, labels)
    except Exception as e:
        print(f"layoutlm_extractor: failed to load model folder '{folder}': {e}")
        return None


@_serial_inference
def _get_model(model_key="indian"):
    cache_key = _cache_key(model_key)
    if cache_key not in _models:
        folder_map = {
            "indian": "layoutlm-indian-invoice-trained",
            "synthetic": "layoutlm-synthetic-trained"
        }
        folder_name = folder_map.get(model_key, "layoutlm-indian-invoice-trained")
        if _folder_has_weights(folder_name):
            _models[cache_key] = _load_model(folder_name)
        else:
            # No usable merged weights: cache None so we fail fast / fall back.
            _models[cache_key] = None
    return _models[cache_key]


@_serial_inference
def _get_model_for_doc_type(doc_type: str) -> tuple | None:
    """Per-doc-type model, or None if not mapped / missing weights."""
    cache_key = _cache_key(f"doc::{doc_type}")
    if cache_key not in _models:
        folder = get_model_folder(doc_type)
        if folder and _folder_has_weights(folder):
            _models[cache_key] = _load_model(folder)
        else:
            _models[cache_key] = None
    return _models[cache_key]


def _aggregate_bio_predictions(
    words: list[str],
    predictions: list[int],
    confidences: list[float],
    word_ids: list[int | None],
    labels: list[str],
) -> dict[str, tuple[str, float]]:
    """
    Convert token-level BIO predictions → field_key: (value, confidence).
    Groups consecutive B-/I- tokens of the same type into a single field value.
    Confidence is the average softmax probability of the tokens.
    """
    seen_word_ids: set[int] = set()
    current_field: str | None = None
    current_tokens: list[str] = []
    current_confs: list[float] = []
    extracted: dict[str, tuple[str, float]] = {}

    for token_idx, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen_word_ids:
            continue
        seen_word_ids.add(word_id)

        label = labels[predictions[token_idx]]
        word = words[word_id]
        conf = confidences[token_idx]

        if label.startswith("B-"):
            if current_field and current_tokens:
                avg_conf = sum(current_confs) / len(current_confs)
                extracted[current_field] = (assemble_field_text(current_field,current_tokens), avg_conf)
            current_field = bio_label_to_key(label)
            current_tokens = [word]
            current_confs = [conf]
        elif label.startswith("I-") and current_field == bio_label_to_key(label):
            current_tokens.append(word)
            current_confs.append(conf)
        else:
            if current_field and current_tokens:
                avg_conf = sum(current_confs) / len(current_confs)
                extracted[current_field] = (assemble_field_text(current_field,current_tokens), avg_conf)
            current_field = None
            current_tokens = []
            current_confs = []

    if current_field and current_tokens:
        avg_conf = sum(current_confs) / len(current_confs)
        extracted[current_field] = (assemble_field_text(current_field,current_tokens), avg_conf)

    return extracted


def _build_extracted(key: str, value: str, confidence: float) -> dict:
    meta = get_field_meta(key)
    return {
        "key": key,
        "label": meta["label"],
        "value": value,
        "confidence": format_confidence(confidence),
        "editable": meta["editable"],
        "monospace": meta["monospace"],
        "source": "layoutlm",
    }


def _regex_only_result(doc_type: str, ocr_text: str, words: list[str]) -> list[dict]:
    """Regex-only fallback used when no LayoutLMv3 model weights are loadable."""
    try:
        label_keys = [bio_label_to_key(l) for l in get_label_set(doc_type) if l.startswith("B-")]
    except KeyError:
        label_keys = []
    result: list[dict] = []
    for key, (value, conf) in extract_all_regex(doc_type, ocr_text, label_keys).items():
        if value:
            result.append(_build_extracted(key, value, conf))
    return result


@_serial_inference
def extract_fields(
    image_bytes: bytes,
    words: list[str],
    bboxes_raw: list[list[list[int]]],  # raw 4-point vertices per word
    image_width: int,
    image_height: int,
    doc_type: str,
    ocr_text: str,
    model_key: str = "indian",
    strict: bool = False,
    diagnostics: dict | None = None,
    normalize_tokens: bool = True,
) -> list[dict]:
    """
    Run LayoutLMv3 token classification + regex fallback.
    Returns list of ExtractedField dicts ready for the API response.
    """
    import torch
    from PIL import Image
    source_word_count=len(words)
    source_indices=[[i] for i in range(len(words))]
    if normalize_tokens:
        words,bboxes_raw,source_indices=normalize_compounds(words,bboxes_raw)

    # Primary path: use the per-doc-type fine-tuned model when available; fall
    # back to the merged model otherwise. The "synthetic" key keeps using the
    # merged synthetic checkpoint as a complementary head.
    cache_hit = _models.get(_cache_key(f"doc::{doc_type}")) is not None
    loading_started = time.perf_counter()
    per_type = _get_model_for_doc_type(doc_type) if model_key == "indian" else None
    model_load_ms = (time.perf_counter() - loading_started) * 1000
    if strict and per_type is None:
        from services.errors import ServiceUnavailable
        raise ServiceUnavailable(f"Per-type LayoutLM weights unavailable for {doc_type}. Train/configure the model and restart.")
    if per_type is not None:
        processor, model, labels = per_type
    else:
        merged = _get_model(model_key)
        if merged is None:
            # No model weights available at all: return only regex fields.
            return _regex_only_result(doc_type, ocr_text, words)
        processor, model, labels = merged

    try:
        device = next(model.parameters()).device
    except (AttributeError, StopIteration):
        device = torch.device("cpu")
    # Normalize bboxes to 0-1000
    normalized_bboxes = []
    for bbox in bboxes_raw:
        nb = _normalize_bbox(bbox, image_width, image_height)
        x0, y0, x1, y1 = nb
        x0, x1 = sorted([max(0, min(1000, x0)), max(0, min(1000, x1))])
        y0, y1 = sorted([max(0, min(1000, y0)), max(0, min(1000, y1))])
        normalized_bboxes.append([x0, y0, x1, y1])

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if len(words) != len(bboxes_raw) or image_width <= 0 or image_height <= 0:
        raise ValueError("OCR words and boxes must align with valid image dimensions.")

    encoding = processor(
        image,
        words,
        boxes=normalized_bboxes,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding="max_length",
        stride=96,
        return_overflowing_tokens=True,
        return_offsets_mapping=True,
    )
    # Mirror training: overlap windows and retain the highest-confidence first
    # subtoken for each word. Never discard the bottom of a long invoice.
    choices = [None] * len(words)
    window_count = len(encoding["input_ids"])
    for window in range(window_count):
        inputs = {k: encoding[k][window].unsqueeze(0) for k in ("input_ids", "attention_mask", "bbox")}
        inputs["pixel_values"] = torch.as_tensor(encoding["pixel_values"][window]).unsqueeze(0)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device.type == "cuda"):
                outputs = model(**inputs)
        probs = outputs.logits[0].float().softmax(-1)
        confidence, prediction = [value.cpu() for value in probs.max(-1)]
        seen = set()
        for token, word_id in enumerate(encoding.word_ids(batch_index=window)):
            if word_id is None or word_id in seen or int(encoding["offset_mapping"][window][token][0]) != 0:
                continue
            seen.add(word_id)
            candidate = (float(confidence[token]), int(prediction[token]))
            if choices[word_id] is None or candidate[0] > choices[word_id][0]:
                choices[word_id] = candidate
    encoded_words = sum(value is not None for value in choices)
    confidences = [value[0] if value else 0.0 for value in choices]
    predictions = [value[1] if value else labels.index("O") for value in choices]
    model_results = _aggregate_bio_predictions(words, predictions, confidences, list(range(len(words))), labels)

    if diagnostics is not None:
        diagnostics.update(compound_normalization=COMPOUND_VERSION if normalize_tokens else 'disabled',
            original_ocr_words=source_word_count,joined_compounds=sum(len(s)>1 for s in source_indices),
            compound_sources=[s for s in source_indices if len(s)>1])
        import hashlib
        from pathlib import Path
        checkpoint = Path(_model_root()) / str(get_model_folder(doc_type))
        diagnostics.update(checkpoint=str(checkpoint), label_config_sha256=hashlib.sha256((checkpoint / "config.json").read_bytes()).hexdigest(), ocr_words=len(words), encoded_words=encoded_words, truncated=encoded_words < len(words), window_count=window_count, window_merge="maximum first-subtoken confidence")
        diagnostics.update(device=str(device), precision="float16_autocast" if device.type == "cuda" else "float32", model_cache_hit=cache_hit, model_load_ms=round(model_load_ms, 2))
        weights = next((checkpoint / name for name in ("model.safetensors", "pytorch_model.bin") if (checkpoint / name).is_file()), None)
        if weights:
            diagnostics["weights_sha256"] = _weight_hash(str(weights), weights.stat().st_mtime_ns)

    # Filter out low-confidence predictions
    final = {
        key: (value, conf)
        for key, (value, conf) in model_results.items()
        if strict or conf >= EXTRACTOR_LAYOUTLM_THRESHOLD
    }

    # Build ExtractedField list
    result = []
    for key, (value, confidence) in final.items():
        result.append(_build_extracted(key, value, confidence))

    return result
