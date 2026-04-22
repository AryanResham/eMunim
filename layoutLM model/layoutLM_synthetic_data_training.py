import os
import json
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

import torch
from torch.utils.data import Dataset, random_split

from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    TrainingArguments,
    Trainer,
    default_data_collator,
)

# -------------------------
# paths
# -------------------------
DATASET_ROOT = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\Synthetic_Data"
IMAGE_DIR = Path(DATASET_ROOT) / "images"
TOKEN_DIR = Path(DATASET_ROOT) / "tokens"
ANNOTATION_DIR = Path(DATASET_ROOT) / "annotations"

# use your current trained model as base
BASE_MODEL_PATH = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\layoutlm-sroie-trained"

OUTPUT_DIR = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\layoutlm-synthetic-output"
FINAL_MODEL_DIR = r"C:\\Users\\Aryan\\Desktop\\eMunim\\layoutLM model\\layoutlm-synthetic-trained"

# -------------------------
# label list
# keep exactly one master schema
# -------------------------
LABEL_LIST = [
    "O",
    "B-INVOICE_NO", "I-INVOICE_NO",
    "B-INVOICE_DATE", "I-INVOICE_DATE",
    "B-VENDOR_NAME", "I-VENDOR_NAME",
    "B-VENDOR_GSTIN", "I-VENDOR_GSTIN",
    "B-BUYER_NAME", "I-BUYER_NAME",
    "B-BUYER_GSTIN", "I-BUYER_GSTIN",
    "B-VENDOR_ADDRESS", "I-VENDOR_ADDRESS",
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

# if your synthetic annotations contain extra labels like VENDOR_ADDRESS / BUYER_ADDRESS,
# either add them here OR ignore them.
IGNORE_UNKNOWN_LABELS = True

# -------------------------
# seed
# -------------------------
torch.manual_seed(42)
random.seed(42)
np.random.seed(42)

# -------------------------
# helper
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

def valid_box(box):
    x1, y1, x2, y2 = box
    return all(0 <= v <= 1000 for v in box) and x1 <= x2 and y1 <= y2

# -------------------------
# build word labels from annotation file
# -------------------------
def build_word_labels(words, annotation_data):
    labels = ["O"] * len(words)

    # map word index by exact order
    # since the annotation preview shows the field token text is repeated from the same master words list,
    # we align by walking through words and matching field token sequences in order
    used = [False] * len(words)

    for field in annotation_data.get("fields", []):
        for tok in field.get("tokens", []):
            text = tok.get("text", "").strip()
            label = tok.get("label", "O").strip()

            if not text or not label:
                continue

            if label not in LABEL2ID:
                if IGNORE_UNKNOWN_LABELS:
                    continue
                raise ValueError(f"Unknown label found: {label}")

            # assign to first unmatched identical word
            matched = False
            for i, w in enumerate(words):
                if not used[i] and w == text:
                    labels[i] = label
                    used[i] = True
                    matched = True
                    break

            if not matched:
                # fallback: leave as O
                pass

    return labels

# -------------------------
# dataset
# -------------------------
class SyntheticInvoiceDataset(Dataset):
    def __init__(self, image_dir, token_dir, annotation_dir, processor, max_length=512):
        self.image_dir = Path(image_dir)
        self.token_dir = Path(token_dir)
        self.annotation_dir = Path(annotation_dir)
        self.processor = processor
        self.max_length = max_length
        self.samples = []

        token_files = sorted(self.token_dir.glob("*.json"))
        print("Found token files:", len(token_files))

        for idx, token_path in enumerate(token_files, start=1):
            stem = token_path.stem

            image_path = self.image_dir / f"{stem}.png"
            if not image_path.exists():
                image_path = self.image_dir / f"{stem}.jpg"

            annotation_path = self.annotation_dir / f"{stem}.json"

            if not image_path.exists() or not annotation_path.exists():
                print(f"Skipping {stem}: missing image or annotation")
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

                if len(words) != len(boxes):
                    raise ValueError(f"words/boxes mismatch in {stem}")

                norm_boxes = [normalize_box_1000(b, width, height) for b in boxes]
                for b in norm_boxes:
                    if not valid_box(b):
                        raise ValueError(f"Invalid normalized box in {stem}: {b}")

                label_names = build_word_labels(words, annotation_data)
                label_ids = [LABEL2ID.get(lbl, LABEL2ID["O"]) for lbl in label_names]

                encoding = self.processor(
                    image,
                    words,
                    boxes=norm_boxes,
                    word_labels=label_ids,
                    truncation=True,
                    padding="max_length",
                    max_length=self.max_length,
                    return_tensors="pt"
                )

                item = {k: v.squeeze(0) for k, v in encoding.items()}
                self.samples.append(item)

            except Exception as e:
                print(f"Error loading {stem}: {e}")

            if idx % 50 == 0:
                print(f"Processed {idx} token files... valid samples = {len(self.samples)}")

        print("Final loaded samples =", len(self.samples))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]

# -------------------------
# metrics
# -------------------------
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=2)

    total = 0
    correct = 0

    for pred_seq, label_seq in zip(preds, labels):
        for p, l in zip(pred_seq, label_seq):
            if l == -100:
                continue
            total += 1
            if int(p) == int(l):
                correct += 1

    acc = correct / total if total else 0.0
    return {"token_accuracy": acc}

# -------------------------
# main
# -------------------------
def main():
    print("Torch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise RuntimeError("GPU not available")

    print("Using GPU:", torch.cuda.get_device_name(0))
    print("Total labels:", len(LABEL_LIST))

    processor = LayoutLMv3Processor.from_pretrained(BASE_MODEL_PATH, apply_ocr=False)

    model = LayoutLMv3ForTokenClassification.from_pretrained(
        BASE_MODEL_PATH,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True
    )

    dataset = SyntheticInvoiceDataset(
        image_dir=IMAGE_DIR,
        token_dir=TOKEN_DIR,
        annotation_dir=ANNOTATION_DIR,
        processor=processor,
        max_length=512
    )

    if len(dataset) == 0:
        raise RuntimeError("No valid samples loaded")

    train_size = int(0.8 * len(dataset))
    eval_size = len(dataset) - train_size

    train_dataset, eval_dataset = random_split(
        dataset,
        [train_size, eval_size],
        generator=torch.Generator().manual_seed(42)
    )

    print("Train samples =", len(train_dataset))
    print("Eval samples  =", len(eval_dataset))

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=4,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_strategy="steps",
        logging_steps=20,
        save_total_limit=4,
        fp16=False,
        remove_unused_columns=False,
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=default_data_collator,
        compute_metrics=compute_metrics
    )

    print("\nStarting training...")
    trainer.train()

    print("\nSaving final model...")
    final_dir = Path(FINAL_MODEL_DIR)
    if final_dir.exists():
        shutil.rmtree(final_dir)

    trainer.save_model(str(final_dir))
    processor.save_pretrained(str(final_dir))

    print("Saved final model at:", final_dir)

if __name__ == "__main__":
    main()