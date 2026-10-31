"""Offline, read-only checkpoint diagnosis using saved verification OCR."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    import torch
    from PIL import Image
    from services.extractor.layoutlm_extractor import (
        _get_model_for_doc_type, _normalize_bbox, _aggregate_bio_predictions,
    )

    torch.set_num_threads(4)
    audit = ROOT / "backend/data/verification/20261016T134533Z"
    saved = audit / "isolated_data"
    ocr = json.loads(next((saved / "ocr_cache").glob("*.json")).read_text())
    image = Image.open(next((saved / "raw_invoices").glob("*.jpg"))).convert("RGB")
    words = [w["text"] for w in ocr["words"]]
    boxes = [_normalize_bbox(w["bounding_box"], *image.size) for w in ocr["words"]]
    processor, model, labels = _get_model_for_doc_type("GST_INVOICE")
    result = {"checkpoint": "layoutlm-synthetic-tax_invoice-trained", "samples": {}}

    def inspect(name, image, words, boxes):
        encoding = processor(image, words, boxes=boxes, return_tensors="pt",
                             truncation=True, max_length=512, padding="max_length")
        with torch.no_grad():
            probs = model(**encoding).logits.softmax(-1)[0]
        ids = probs.argmax(-1).tolist()
        conf = probs.max(-1).values.tolist()
        word_ids = encoding.word_ids(0)
        seen, rows = set(), []
        for token, wid in enumerate(word_ids):
            if wid is None or wid in seen:
                continue
            seen.add(wid)
            rows.append({"word": words[wid], "label": labels[ids[token]],
                         "confidence": round(conf[token], 5)})
        entry = {"image_size": image.size, "ocr_words": len(words),
                 "encoded_words": len(seen), "label_counts": dict(Counter(r["label"] for r in rows)),
                 "fields": _aggregate_bio_predictions(words, ids, conf, word_ids, labels),
                 "word_predictions": rows}
        result["samples"][name] = entry
        print(name, json.dumps({k: v for k, v in entry.items() if k != "word_predictions"}), flush=True)

    inspect("live_ocr_smoke", image, words, boxes)
    dataset = ROOT / "layoutLM model/Synthetic_Test"
    stems = [p.stem for p in sorted((dataset / "annotations").glob("*.json"))
             if json.loads(p.read_text(encoding="utf-8")).get("doc_type") == "tax_invoice"][:3]
    for stem in stems:
        tokens = json.loads((dataset / "tokens" / (stem + ".json")).read_text(encoding="utf-8"))
        path = next((dataset / "images").glob(stem + ".*"))
        image = Image.open(path).convert("RGB")
        boxes = [[int(1000 * b[0] / image.width), int(1000 * b[1] / image.height),
                  int(1000 * b[2] / image.width), int(1000 * b[3] / image.height)] for b in tokens["boxes"]]
        inspect(stem, image, tokens["words"], boxes)
    (audit / "layoutlm_diagnosis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
