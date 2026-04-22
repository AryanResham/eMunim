import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

import torch
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
from seqeval.metrics import precision_score, recall_score, f1_score, accuracy_score, classification_report

# -------------------------
# paths
# -------------------------
DATASET_ROOT = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\Synthetic_Test_Data"
IMAGE_DIR = Path(DATASET_ROOT) / "images"
TOKEN_DIR = Path(DATASET_ROOT) / "tokens"
ANNOTATION_DIR = Path(DATASET_ROOT) / "annotations"

MODEL_PATH = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\layoutlm-synthetic-trained"

# -------------------------
# label list
# keep exactly same as training
# -------------------------
LABEL_LIST = [
    "O",
    "B-INVOICE_NO", "I-INVOICE_NO",
    "B-INVOICE_DATE", "I-INVOICE_DATE",
    "B-VENDOR_NAME", "I-VENDOR_NAME",
    "B-VENDOR_GSTIN", "I-VENDOR_GSTIN",
    "B-VENDOR_ADDRESS", "I-VENDOR_ADDRESS",
    "B-BUYER_NAME", "I-BUYER_NAME",
    "B-BUYER_GSTIN", "I-BUYER_GSTIN",
    "B-BUYER_ADDRESS", "I-BUYER_ADDRESS",
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
# fields to measure exact accuracy on
# -------------------------
TARGET_FIELDS = [
    "INVOICE_NO",
    "INVOICE_DATE",
    "VENDOR_NAME",
    "VENDOR_GSTIN",
    "VENDOR_ADDRESS",
    "BUYER_NAME",
    "BUYER_GSTIN",
    "BUYER_ADDRESS",
    "TAXABLE_AMOUNT",
    "CGST_AMOUNT",
    "SGST_AMOUNT",
    "IGST_AMOUNT",
    "TOTAL_AMOUNT",
    "DUE_DATE",
    "PO_NUMBER",
    "SUBTOTAL",
    "PAYMENT_TERMS",
]

# -------------------------
# helpers
# -------------------------
def normalize_box_1000(box, width, height):
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

def normalize_text(text):
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text

def build_word_labels(words, annotation_data):
    labels = ["O"] * len(words)
    used = [False] * len(words)

    for field in annotation_data.get("fields", []):
        for tok in field.get("tokens", []):
            text = tok.get("text", "").strip()
            label = tok.get("label", "O").strip()

            if not text or not label:
                continue
            if label not in LABEL2ID:
                continue

            matched = False
            for i, w in enumerate(words):
                if not used[i] and w == text:
                    labels[i] = label
                    used[i] = True
                    matched = True
                    break

            if not matched:
                pass

    return labels

def extract_fields_from_labels(words, label_names):
    results = {field: [] for field in TARGET_FIELDS}
    current_field = None

    for word, label in zip(words, label_names):
        if label == "O":
            current_field = None
            continue

        if label.startswith("B-"):
            current_field = label[2:]
            if current_field in results:
                results[current_field].append(word)
            else:
                current_field = None

        elif label.startswith("I-"):
            field = label[2:]
            if current_field == field and field in results:
                results[field].append(word)
            else:
                current_field = None
        else:
            current_field = None

    return {k: normalize_text(" ".join(v)) for k, v in results.items()}

def extract_gt_fields(annotation_data):
    gt = {field: "" for field in TARGET_FIELDS}

    for field in annotation_data.get("fields", []):
        label = field.get("label", "").strip()
        text = normalize_text(field.get("text", ""))

        if label in gt and not gt[label]:
            gt[label] = text

    return gt

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

    token_files = sorted(TOKEN_DIR.glob("*.json"))
    print("Found token files:", len(token_files))

    all_true_labels = []
    all_pred_labels = []

    field_correct = {field: 0 for field in TARGET_FIELDS}
    full_doc_correct = 0
    tested_docs = 0

    for idx, token_path in enumerate(token_files, start=1):
        stem = token_path.stem

        image_path = IMAGE_DIR / f"{stem}.png"
        if not image_path.exists():
            image_path = IMAGE_DIR / f"{stem}.jpg"

        annotation_path = ANNOTATION_DIR / f"{stem}.json"

        if not image_path.exists() or not annotation_path.exists():
            print(f"Skipping {stem}: missing file")
            continue

        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token_data = json.load(f)

            with open(annotation_path, "r", encoding="utf-8") as f:
                annotation_data = json.load(f)

            image = Image.open(image_path).convert("RGB")
            width, height = image.size

            words = token_data["words"]
            boxes = token_data["boxes"]
            norm_boxes = [normalize_box_1000(b, width, height) for b in boxes]

            gt_word_labels = build_word_labels(words, annotation_data)

            cpu_encoding = processor(
                image,
                words,
                boxes=norm_boxes,
                truncation=True,
                padding="max_length",
                max_length=512,
                return_tensors="pt"
            )

            gpu_encoding = {k: v.to(device) for k, v in cpu_encoding.items()}

            with torch.no_grad():
                outputs = model(**gpu_encoding)

            pred_ids = outputs.logits.argmax(-1).squeeze(0).cpu().tolist()
            word_ids = cpu_encoding.word_ids(batch_index=0)

            word_pred_ids = [None] * len(words)
            for token_idx, word_idx in enumerate(word_ids):
                if word_idx is None:
                    continue
                if 0 <= word_idx < len(words) and word_pred_ids[word_idx] is None:
                    word_pred_ids[word_idx] = int(pred_ids[token_idx])

            pred_word_labels = []
            for i in range(len(words)):
                pid = word_pred_ids[i]
                if pid is None:
                    pred_word_labels.append("O")
                else:
                    pred_word_labels.append(ID2LABEL[pid])

            all_true_labels.append(gt_word_labels)
            all_pred_labels.append(pred_word_labels)

            gt_fields = extract_gt_fields(annotation_data)
            pred_fields = extract_fields_from_labels(words, pred_word_labels)

            doc_ok = True
            for field in TARGET_FIELDS:
                if pred_fields[field] == gt_fields[field]:
                    field_correct[field] += 1
                else:
                    doc_ok = False

            if doc_ok:
                full_doc_correct += 1

            tested_docs += 1

            if idx % 25 == 0:
                print(f"Processed {idx} files... tested docs = {tested_docs}")

        except Exception as e:
            print(f"Skipping {stem}: {e}")

    print("\n==============================")
    print("TOKEN-LEVEL METRICS")
    print("==============================")
    print(f"Token accuracy : {accuracy_score(all_true_labels, all_pred_labels):.4f}")
    print(f"Precision      : {precision_score(all_true_labels, all_pred_labels):.4f}")
    print(f"Recall         : {recall_score(all_true_labels, all_pred_labels):.4f}")
    print(f"F1             : {f1_score(all_true_labels, all_pred_labels):.4f}")

    print("\nClassification report:")
    print(classification_report(all_true_labels, all_pred_labels, digits=4))

    print("\n==============================")
    print("FIELD-LEVEL EXACT ACCURACY")
    print("==============================")
    print(f"Tested docs: {tested_docs}")

    for field in TARGET_FIELDS:
        acc = field_correct[field] / tested_docs if tested_docs else 0
        print(f"{field:20s}: {acc:.4f} ({acc * 100:.2f}%)")

    full_acc = full_doc_correct / tested_docs if tested_docs else 0
    print(f"\nFULL DOCUMENT EXACT MATCH: {full_acc:.4f} ({full_acc * 100:.2f}%)")

if __name__ == "__main__":
    main()