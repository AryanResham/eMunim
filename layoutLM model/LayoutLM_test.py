# basic imports
import re
import json
import random
import numpy as np
from pathlib import Path

# torch
import torch
from torch.utils.data import Dataset

# transformers
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification

# image
from PIL import Image

# -------------------------
# set paths
# -------------------------
MODEL_PATH = r"C:\Users\Aryan\Desktop\eMunim\model\layoutlm-sroie-trained"
SROIE_TEST_DIR = r"C:\Users\Aryan\Desktop\eMunim\model\SROIE2019\test"

# -------------------------
# full label list
# -------------------------
LABEL_LIST = [
    "O",
    "B-INVOICE_NO", "I-INVOICE_NO",
    "B-INVOICE_DATE", "I-INVOICE_DATE",
    "B-VENDOR_NAME", "I-VENDOR_NAME",
    "B-VENDOR_GSTIN", "I-VENDOR_GSTIN",
    "B-BUYER_NAME", "I-BUYER_NAME",
    "B-BUYER_GSTIN", "I-BUYER_GSTIN",
    "B-TAXABLE_AMOUNT", "I-TAXABLE_AMOUNT",
    "B-CGST_AMOUNT", "I-CGST_AMOUNT",
    "B-SGST_AMOUNT", "I-SGST_AMOUNT",
    "B-IGST_AMOUNT", "I-IGST_AMOUNT",
    "B-TOTAL_AMOUNT", "I-TOTAL_AMOUNT",
    "B-DUE_DATE", "I-DUE_DATE",
    "B-PO_NUMBER", "I-PO_NUMBER",
    "B-BILL_NO", "I-BILL_NO",
    "B-BILL_DATE", "I-BILL_DATE",
    "B-SUBTOTAL", "I-SUBTOTAL",
    "B-TAX_AMOUNT", "I-TAX_AMOUNT",
    "B-PAYMENT_TERMS", "I-PAYMENT_TERMS",
    "B-RECEIPT_NO", "I-RECEIPT_NO",
    "B-RECEIPT_DATE", "I-RECEIPT_DATE",
    "B-AMOUNT", "I-AMOUNT",
    "B-PAYMENT_MODE", "I-PAYMENT_MODE",
    "B-CATEGORY", "I-CATEGORY",
    "B-CONSUMER_NO", "I-CONSUMER_NO",
    "B-BILLING_PERIOD", "I-BILLING_PERIOD",
    "B-UNITS_CONSUMED", "I-UNITS_CONSUMED",
    "B-AMOUNT_DUE", "I-AMOUNT_DUE",
    "B-UTILITY_PROVIDER", "I-UTILITY_PROVIDER",
    "B-ACCOUNT_NAME", "I-ACCOUNT_NAME",
    "B-CREDIT_NOTE_NO", "I-CREDIT_NOTE_NO",
    "B-CREDIT_NOTE_DATE", "I-CREDIT_NOTE_DATE",
    "B-ORIGINAL_INVOICE_NO", "I-ORIGINAL_INVOICE_NO",
    "B-REASON", "I-REASON",
    "B-CREDIT_AMOUNT", "I-CREDIT_AMOUNT",
    "B-TAX_CREDIT", "I-TAX_CREDIT",
    "B-DEBIT_NOTE_NO", "I-DEBIT_NOTE_NO",
    "B-DEBIT_NOTE_DATE", "I-DEBIT_NOTE_DATE",
    "B-DEBIT_AMOUNT", "I-DEBIT_AMOUNT",
]

LABEL2ID = {label: idx for idx, label in enumerate(LABEL_LIST)}
ID2LABEL = {idx: label for idx, label in enumerate(LABEL_LIST)}

# -------------------------
# seed
# -------------------------
torch.manual_seed(42)
random.seed(42)
np.random.seed(42)

# -------------------------
# text helpers
# -------------------------
def clean_token(token):
    token = token.lower().strip()
    token = token.strip(",:;*()[]{}<>")
    token = re.sub(r"\s+", " ", token)
    return token

def normalize_field_text(text):
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(",:;*()[]{}<>")
    return text

def tokenize_text(text):
    return [t for t in text.split() if t.strip()]

# -------------------------
# box helpers
# -------------------------
def normalize_box(box, width, height):
    x1, y1, x2, y2 = box

    x1 = int(1000 * x1 / width)
    y1 = int(1000 * y1 / height)
    x2 = int(1000 * x2 / width)
    y2 = int(1000 * y2 / height)

    x1 = max(0, min(1000, x1))
    y1 = max(0, min(1000, y1))
    x2 = max(0, min(1000, x2))
    y2 = max(0, min(1000, y2))

    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    return [x1, y1, x2, y2]

def is_valid_box(box):
    x1, y1, x2, y2 = box
    return all(0 <= v <= 1000 for v in box) and x1 <= x2 and y1 <= y2

def split_line_into_token_boxes(text, line_box):
    tokens = tokenize_text(text)

    if not tokens:
        return [], []

    if len(tokens) == 1:
        return tokens, [line_box]

    x1, y1, x2, y2 = line_box
    if x2 <= x1:
        return tokens, [line_box] * len(tokens)

    char_lengths = [max(len(tok), 1) for tok in tokens]
    total_chars = sum(char_lengths)

    token_boxes = []
    current_x = x1
    used_chars = 0

    for i, tok_len in enumerate(char_lengths):
        if i == len(tokens) - 1:
            next_x = x2
        else:
            used_chars += tok_len
            next_x = x1 + round((x2 - x1) * used_chars / total_chars)

        token_boxes.append([current_x, y1, max(current_x, next_x), y2])
        current_x = next_x

    return tokens, token_boxes

# -------------------------
# sample loader
# -------------------------
def load_sroie_words_boxes_gt(image_path, box_path, entity_path):
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    words = []
    boxes = []

    with open(box_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        parts = raw_line.split(",", 8)
        if len(parts) < 9:
            continue

        coords = list(map(int, parts[:8]))
        text = parts[8].strip()
        if not text:
            continue

        xs = coords[0::2]
        ys = coords[1::2]
        line_box = [min(xs), min(ys), max(xs), max(ys)]

        line_tokens, line_token_boxes = split_line_into_token_boxes(text, line_box)

        for tok, tok_box in zip(line_tokens, line_token_boxes):
            norm_box = normalize_box(tok_box, width, height)
            if not is_valid_box(norm_box):
                raise ValueError(f"Invalid box in {box_path.name}: {norm_box}")
            words.append(tok)
            boxes.append(norm_box)

    with open(entity_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    gt_fields = {
        "VENDOR_NAME": normalize_field_text(gt.get("company", "")),
        "INVOICE_DATE": normalize_field_text(gt.get("date", "")),
        "TOTAL_AMOUNT": normalize_field_text(gt.get("total", "")),
    }

    return image, words, boxes, gt_fields

# -------------------------
# extract fields from labels
# -------------------------
def extract_fields_from_word_labels(words, label_names):
    fields = {
        "VENDOR_NAME": [],
        "INVOICE_DATE": [],
        "TOTAL_AMOUNT": [],
    }

    current_field = None

    for word, label in zip(words, label_names):
        if label == "B-VENDOR_NAME":
            current_field = "VENDOR_NAME"
            fields[current_field].append(word)
        elif label == "I-VENDOR_NAME":
            if current_field == "VENDOR_NAME":
                fields[current_field].append(word)

        elif label == "B-INVOICE_DATE":
            current_field = "INVOICE_DATE"
            fields[current_field].append(word)
        elif label == "I-INVOICE_DATE":
            if current_field == "INVOICE_DATE":
                fields[current_field].append(word)

        elif label == "B-TOTAL_AMOUNT":
            current_field = "TOTAL_AMOUNT"
            fields[current_field].append(word)
        elif label == "I-TOTAL_AMOUNT":
            if current_field == "TOTAL_AMOUNT":
                fields[current_field].append(word)

        else:
            current_field = None

    return {
        k: normalize_field_text(" ".join(v))
        for k, v in fields.items()
    }

# -------------------------
# align token predictions back to words
# -------------------------
def get_word_level_predictions(words, encoding, pred_ids, processor):
    word_ids = encoding.word_ids(batch_index=0)

    word_pred_ids = [None] * len(words)

    for token_idx, word_idx in enumerate(word_ids):
        if word_idx is None:
            continue
        if 0 <= word_idx < len(words) and word_pred_ids[word_idx] is None:
            word_pred_ids[word_idx] = int(pred_ids[token_idx])

    word_label_names = []
    for i in range(len(words)):
        pred_id = word_pred_ids[i]
        if pred_id is None:
            word_label_names.append("O")
        else:
            word_label_names.append(ID2LABEL[pred_id])

    return word_label_names

# -------------------------
# main
# -------------------------
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading processor...")
    processor = LayoutLMv3Processor.from_pretrained(MODEL_PATH, apply_ocr=False)

    print("Loading model...")
    model = LayoutLMv3ForTokenClassification.from_pretrained(MODEL_PATH)
    model.to(device)
    model.eval()

    root_dir = Path(SROIE_TEST_DIR)
    box_dir = root_dir / "box"
    img_dir = root_dir / "img"
    entity_dir = root_dir / "entities"

    box_files = sorted(box_dir.glob("*.txt"))

    vendor_correct = 0
    date_correct = 0
    total_correct = 0
    full_correct = 0
    total_docs = 0

    print("Testing on SROIE test set...")

    for idx, box_path in enumerate(box_files, start=1):
        stem = box_path.stem

        image_path = None
        for ext in [".jpg", ".jpeg", ".png"]:
            candidate = img_dir / f"{stem}{ext}"
            if candidate.exists():
                image_path = candidate
                break

        entity_path = None
        for ext in [".txt", ".json"]:
            candidate = entity_dir / f"{stem}{ext}"
            if candidate.exists():
                entity_path = candidate
                break

        if image_path is None or entity_path is None:
            continue

        try:
            image, words, boxes, gt_fields = load_sroie_words_boxes_gt(
                image_path=image_path,
                box_path=box_path,
                entity_path=entity_path
            )

            if len(words) == 0:
                continue

            cpu_encoding = processor(
                image,
                words,
                boxes=boxes,
                truncation=True,
                padding="max_length",
                max_length=512,
                return_tensors="pt"
            )

            gpu_encoding = {k: v.to(device) for k, v in cpu_encoding.items()}

            with torch.no_grad():
                outputs = model(**gpu_encoding)

            pred_ids = outputs.logits.argmax(-1).squeeze(0).detach().cpu().tolist()

            word_label_names = get_word_level_predictions(
                words=words,
                encoding=cpu_encoding,
                pred_ids=pred_ids,
                processor=processor
            )
            pred_fields = extract_fields_from_word_labels(words, word_label_names)

            vendor_ok = pred_fields["VENDOR_NAME"] == gt_fields["VENDOR_NAME"]
            date_ok = pred_fields["INVOICE_DATE"] == gt_fields["INVOICE_DATE"]
            total_ok = pred_fields["TOTAL_AMOUNT"] == gt_fields["TOTAL_AMOUNT"]

            vendor_correct += int(vendor_ok)
            date_correct += int(date_ok)
            total_correct += int(total_ok)

            if vendor_ok and date_ok and total_ok:
                full_correct += 1

            total_docs += 1

            if idx % 50 == 0:
                print(f"Processed {idx} files... tested docs = {total_docs}")

        except Exception as e:
            print(f"Skipping {stem}: {e}")

    print("\nField-level accuracy results:")
    print(f"Total test docs: {total_docs}")

    vendor_acc = vendor_correct / total_docs if total_docs else 0
    date_acc = date_correct / total_docs if total_docs else 0
    total_acc = total_correct / total_docs if total_docs else 0
    full_acc = full_correct / total_docs if total_docs else 0

    print(f"VENDOR_NAME exact accuracy   : {vendor_acc:.4f} ({vendor_acc * 100:.2f}%)")
    print(f"INVOICE_DATE exact accuracy  : {date_acc:.4f} ({date_acc * 100:.2f}%)")
    print(f"TOTAL_AMOUNT exact accuracy  : {total_acc:.4f} ({total_acc * 100:.2f}%)")
    print(f"FULL RECEIPT exact accuracy  : {full_acc:.4f} ({full_acc * 100:.2f}%)")

if __name__ == "__main__":
    main()