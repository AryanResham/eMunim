# basic imports
import os
import re
import json
import shutil
import random
import numpy as np
from pathlib import Path

# torch
import torch
from torch.utils.data import Dataset, random_split

# transformers
from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    TrainingArguments,
    Trainer,
    default_data_collator
)

# image
from PIL import Image

# -------------------------
# set paths
# -------------------------
MODEL_PATH = r"C:\\Users\\Aryan\\Desktop\\eMunim\\model\\layoutlm-funsd-trained"
SROIE_TRAIN_DIR = r"C:\\Users\\Aryan\\Desktop\\eMunim\\model\\SROIE2019\\train"
OUTPUT_DIR = r"C:\\Users\\Aryan\\Desktop\\eMunim\\model\\layoutlm-sroie-output"
FINAL_SAVE_DIR = r"C:\\Users\\Aryan\\Desktop\\eMunim\\model\\layoutlm-sroie-trained"

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
# matching helpers
# -------------------------
def find_exact_spans(words, entity_tokens):
    spans = []
    n = len(entity_tokens)

    if n == 0 or n > len(words):
        return spans

    for i in range(len(words) - n + 1):
        if words[i:i+n] == entity_tokens:
            spans.append((i, i + n - 1))

    return spans

def pick_best_total_span(words, boxes, spans):
    keywords = {"total", "grand", "amount", "due", "payable", "inclusive", "incl", "net", "balance"}

    best_span = None
    best_score = -1e9

    for start, end in spans:
        x1, y1, x2, y2 = boxes[start]

        left = max(0, start - 6)
        right = min(len(words), end + 7)
        nearby_words = words[left:right]

        score = 0

        for w in nearby_words:
            if w in keywords:
                score += 8

        score += y2 / 100.0
        score += x2 / 200.0
        score += start / max(1, len(words))

        if score > best_score:
            best_score = score
            best_span = (start, end)

    return best_span

def apply_bio_labels(label_names, span, entity_name):
    start, end = span
    for i in range(start, end + 1):
        if i == start:
            label_names[i] = f"B-{entity_name}"
        else:
            label_names[i] = f"I-{entity_name}"

# -------------------------
# load one sroie sample
# -------------------------
def load_sroie_sample(image_path, box_path, entity_path):
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
                raise ValueError(f"Invalid box found in {box_path.name}: {norm_box}")

            words.append(tok)
            boxes.append(norm_box)

    if len(words) == 0:
        raise ValueError(f"No words found in {box_path.name}")

    with open(entity_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    company_text = gt.get("company", "")
    date_text = gt.get("date", "")
    total_text = gt.get("total", "")

    clean_words = [clean_token(w) for w in words]
    label_names = ["O"] * len(words)

    # company
    company_tokens = [clean_token(t) for t in tokenize_text(company_text)]
    company_tokens = [t for t in company_tokens if t]
    if company_tokens:
        company_spans = find_exact_spans(clean_words, company_tokens)
        if company_spans:
            apply_bio_labels(label_names, company_spans[0], "VENDOR_NAME")

    # date
    date_tokens = [clean_token(t) for t in tokenize_text(date_text)]
    date_tokens = [t for t in date_tokens if t]
    if date_tokens:
        date_spans = find_exact_spans(clean_words, date_tokens)
        if date_spans:
            apply_bio_labels(label_names, date_spans[0], "INVOICE_DATE")

    # total
    total_tokens = [clean_token(t) for t in tokenize_text(total_text)]
    total_tokens = [t for t in total_tokens if t]
    if total_tokens:
        total_spans = find_exact_spans(clean_words, total_tokens)
        if total_spans:
            best_total_span = pick_best_total_span(clean_words, boxes, total_spans)
            apply_bio_labels(label_names, best_total_span, "TOTAL_AMOUNT")

    assert len(words) == len(boxes) == len(label_names), (
        f"Mismatch: words={len(words)}, boxes={len(boxes)}, labels={len(label_names)}"
    )

    for box in boxes:
        if not is_valid_box(box):
            raise ValueError(f"Invalid box in {box_path.name}: {box}")

    label_ids = [LABEL2ID[label] for label in label_names]
    return image, words, boxes, label_ids

# -------------------------
# dataset
# -------------------------
class SROIEDataset(Dataset):
    def __init__(self, root_dir, processor, max_length=512):
        self.root_dir = Path(root_dir)
        self.processor = processor
        self.max_length = max_length
        self.data = []

        box_dir = self.root_dir / "box"
        img_dir = self.root_dir / "img"
        entity_dir = self.root_dir / "entities"

        if not box_dir.exists():
            raise FileNotFoundError(f"Missing folder: {box_dir}")
        if not img_dir.exists():
            raise FileNotFoundError(f"Missing folder: {img_dir}")
        if not entity_dir.exists():
            raise FileNotFoundError(f"Missing folder: {entity_dir}")

        box_files = sorted(box_dir.glob("*.txt"))
        print("Found box files:", len(box_files))

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
                print(f"Skipping {stem}: missing image or entity file")
                continue

            try:
                image, words, boxes, labels = load_sroie_sample(
                    image_path=image_path,
                    box_path=box_path,
                    entity_path=entity_path
                )

                encoding = self.processor(
                    image,
                    words,
                    boxes=boxes,
                    word_labels=labels,
                    truncation=True,
                    padding="max_length",
                    max_length=self.max_length,
                    return_tensors="pt"
                )

                item = {k: v.squeeze(0) for k, v in encoding.items()}
                self.data.append(item)

            except Exception as e:
                print(f"Error loading {stem}: {e}")
                continue

            if idx % 50 == 0:
                print(f"Loaded {idx} files... valid samples = {len(self.data)}")

        print("Final loaded samples =", len(self.data))

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

# -------------------------
# simple metric print helper
# -------------------------
def print_log_history(trainer):
    print("\nTraining logs:")
    for log in trainer.state.log_history:
        print(log)

# -------------------------
# main
# -------------------------
def main():
    print("Torch version:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. GPU is not being used.")

    print("Using GPU:", torch.cuda.get_device_name(0))
    print("Total labels:", len(LABEL_LIST))

    # create output folders
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # load processor
    print("\nLoading processor...")
    processor = LayoutLMv3Processor.from_pretrained(MODEL_PATH, apply_ocr=False)

    # load model
    print("Loading model...")
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        MODEL_PATH,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True
    )

    print("Model loaded")

    # load dataset
    print("\nLoading dataset...")
    dataset = SROIEDataset(
        root_dir=SROIE_TRAIN_DIR,
        processor=processor,
        max_length=512
    )

    if len(dataset) == 0:
        raise RuntimeError("No samples loaded")

    # split dataset
    train_size = int(0.8 * len(dataset))
    eval_size = len(dataset) - train_size

    split_generator = torch.Generator().manual_seed(42)

    train_dataset, eval_dataset = random_split(
        dataset,
        [train_size, eval_size],
        generator=split_generator
    )

    print("\nDataset split:")
    print("Train samples =", len(train_dataset))
    print("Eval samples  =", len(eval_dataset))

    # training settings
    print("\nSetting training arguments...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=4,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_strategy="steps",
        logging_steps=10,
        save_total_limit=3,
        fp16=False,
        remove_unused_columns=False,
        report_to="none"
    )

    # trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=default_data_collator
    )

    # train
    print("\nStarting training...")
    trainer.train()

    # print logs
    print_log_history(trainer)

    # save final model
    print("\nSaving final model...")
    final_save_path = Path(FINAL_SAVE_DIR)

    if final_save_path.exists():
        shutil.rmtree(final_save_path)

    trainer.save_model(str(final_save_path))
    processor.save_pretrained(str(final_save_path))

    print("Final model saved at:", final_save_path)

    print("\nSaved files:")
    for p in sorted(final_save_path.glob("*")):
        print("-", p.name)

    print("\nDone")

if __name__ == "__main__":
    main()