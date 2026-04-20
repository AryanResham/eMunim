from __future__ import annotations
import io

from .field_mapper import get_label_set, get_num_labels, bio_label_to_key, get_field_meta
from .rule_based_extractor import extract_all_regex

# Cache one (processor, model, labels) tuple per doc_type to avoid reloading
_models: dict[str, tuple] = {}

_REGEX_FALLBACK_THRESHOLD = 0.50


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


def _get_model(doc_type: str):
    if doc_type not in _models:
        from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
        labels = get_label_set(doc_type)
        processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base")
        model = LayoutLMv3ForTokenClassification.from_pretrained(
            "microsoft/layoutlmv3-base",
            num_labels=len(labels),
        )
        model.eval()
        _models[doc_type] = (processor, model, labels)
    return _models[doc_type]


def _aggregate_bio_predictions(
    words: list[str],
    predictions: list[int],
    word_ids: list[int | None],
    labels: list[str],
) -> dict[str, tuple[str, float]]:
    """
    Convert token-level BIO predictions → field_key: (value, confidence).
    Groups consecutive B-/I- tokens of the same type into a single field value.
    Confidence is approximated as 0.80 for model predictions (pre-fine-tuning placeholder).
    """
    seen_word_ids: set[int] = set()
    current_field: str | None = None
    current_tokens: list[str] = []
    extracted: dict[str, tuple[str, float]] = {}

    for token_idx, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen_word_ids:
            continue
        seen_word_ids.add(word_id)

        label = labels[predictions[token_idx]]
        word = words[word_id]

        if label.startswith("B-"):
            if current_field and current_tokens:
                extracted[current_field] = (" ".join(current_tokens), 0.80)
            current_field = bio_label_to_key(label)
            current_tokens = [word]
        elif label.startswith("I-") and current_field == bio_label_to_key(label):
            current_tokens.append(word)
        else:
            if current_field and current_tokens:
                extracted[current_field] = (" ".join(current_tokens), 0.80)
            current_field = None
            current_tokens = []

    if current_field and current_tokens:
        extracted[current_field] = (" ".join(current_tokens), 0.80)

    return extracted


def extract_fields(
    image_bytes: bytes,
    words: list[str],
    bboxes_raw: list[list[list[int]]],  # raw 4-point vertices per word
    image_width: int,
    image_height: int,
    doc_type: str,
    ocr_text: str,
) -> list[dict]:
    """
    Run LayoutLMv3 token classification + regex fallback.
    Returns list of ExtractedField dicts ready for the API response.
    """
    import torch
    from PIL import Image

    processor, model, labels = _get_model(doc_type)

    # Normalize bboxes to 0-1000
    normalized_bboxes = [
        _normalize_bbox(bbox, image_width, image_height)
        for bbox in bboxes_raw
    ]

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    encoding = processor(
        image,
        words,
        boxes=normalized_bboxes,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding="max_length",
    )

    with torch.no_grad():
        outputs = model(**encoding)

    predictions = outputs.logits.argmax(-1).squeeze().tolist()
    word_ids = encoding.word_ids(batch_index=0)

    model_results = _aggregate_bio_predictions(words, predictions, word_ids, labels)

    # Regex fallback for any field where model confidence < threshold or field missing
    label_keys = [bio_label_to_key(l) for l in labels if l.startswith("B-")]
    regex_results = extract_all_regex(doc_type, ocr_text, label_keys)

    # Merge: prefer model result if confidence >= threshold, else use regex
    final: dict[str, tuple[str, float]] = {}
    for key in label_keys:
        if key in model_results and model_results[key][1] >= _REGEX_FALLBACK_THRESHOLD:
            final[key] = model_results[key]
        elif key in regex_results:
            final[key] = regex_results[key]

    # Build ExtractedField list
    result = []
    for key, (value, confidence) in final.items():
        meta = get_field_meta(key)
        result.append({
            "key": key,
            "label": meta["label"],
            "value": value,
            "confidence": round(confidence, 2),
            "editable": meta["editable"],
            "monospace": meta["monospace"],
        })

    return result
