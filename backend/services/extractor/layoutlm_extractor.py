from __future__ import annotations
import io

from .field_mapper import get_label_set, get_num_labels, bio_label_to_key, get_field_meta
from .rule_based_extractor import extract_all_regex

# Cache one (processor, model, labels) tuple per doc_type to avoid reloading
_models: dict[str, tuple] = {}

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


def _get_model(model_key="indian"):
    if model_key not in _models:
        from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
        from pathlib import Path
        
        folder_map = {
            "indian": "layoutlm-indian-invoice-trained",
            "synthetic": "layoutlm-synthetic-trained"
        }
        folder_name = folder_map.get(model_key, "layoutlm-indian-invoice-trained")
        
        model_path = str(Path(__file__).resolve().parent.parent.parent.parent / "layoutLM model" / folder_name)
        
        processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=False)
        model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)
        model.eval()
        
        labels = list(model.config.id2label.values())
        _models[model_key] = (processor, model, labels)
    return _models[model_key]


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
                extracted[current_field] = (" ".join(current_tokens), avg_conf)
            current_field = bio_label_to_key(label)
            current_tokens = [word]
            current_confs = [conf]
        elif label.startswith("I-") and current_field == bio_label_to_key(label):
            current_tokens.append(word)
            current_confs.append(conf)
        else:
            if current_field and current_tokens:
                avg_conf = sum(current_confs) / len(current_confs)
                extracted[current_field] = (" ".join(current_tokens), avg_conf)
            current_field = None
            current_tokens = []
            current_confs = []

    if current_field and current_tokens:
        avg_conf = sum(current_confs) / len(current_confs)
        extracted[current_field] = (" ".join(current_tokens), avg_conf)

    return extracted


def extract_fields(
    image_bytes: bytes,
    words: list[str],
    bboxes_raw: list[list[list[int]]],  # raw 4-point vertices per word
    image_width: int,
    image_height: int,
    doc_type: str,
    ocr_text: str,
    model_key: str = "indian",
) -> list[dict]:
    """
    Run LayoutLMv3 token classification + regex fallback.
    Returns list of ExtractedField dicts ready for the API response.
    """
    import torch
    from PIL import Image

    processor, model, labels = _get_model(model_key)

    # Normalize bboxes to 0-1000
    normalized_bboxes = []
    for bbox in bboxes_raw:
        nb = _normalize_bbox(bbox, image_width, image_height)
        x0, y0, x1, y1 = nb
        x0, x1 = sorted([max(0, min(1000, x0)), max(0, min(1000, x1))])
        y0, y1 = sorted([max(0, min(1000, y0)), max(0, min(1000, y1))])
        normalized_bboxes.append([x0, y0, x1, y1])

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

    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
    predictions = probs.argmax(-1).squeeze().tolist()
    confidences = probs.max(-1).values.squeeze().tolist()
    
    word_ids = encoding.word_ids(batch_index=0)

    model_results = _aggregate_bio_predictions(words, predictions, confidences, word_ids, labels)

    # Filter out low-confidence predictions
    final = {
        key: (value, conf)
        for key, (value, conf) in model_results.items()
        if conf >= EXTRACTOR_LAYOUTLM_THRESHOLD
    }

    # Build ExtractedField list
    result = []
    for key, (value, confidence) in final.items():
        meta = get_field_meta(key)
        result.append({
            "key": key,
            "label": meta["label"],
            "value": value,
            "confidence": format_confidence(confidence),
            "editable": meta["editable"],
            "monospace": meta["monospace"],
        })

    return result
