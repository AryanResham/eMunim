"""Pinned FUNSD and SROIE conversion; official test sets never select checkpoints."""
import io
import json
import random
import zipfile
from pathlib import Path
import requests
from PIL import Image
from common import HERE, FUNSD_LABELS, SROIE_LABELS, SROIE_REVISION, digest, normalize_box, validate_row, write_json, write_rows


def download(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    temporary = path.with_suffix(path.suffix + ".partial")
    with requests.get(url, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        downloaded=0
        with temporary.open("wb") as stream:
            for block in response.iter_content(1024 * 1024):
                stream.write(block)
                downloaded+=len(block)
                if downloaded%(16*1024*1024)==0:
                    print("Downloading",path.name,downloaded//(1024*1024),"MiB",flush=True)
    temporary.replace(path)
    return path


def split_training(rows, seed=42):
    rows = sorted(rows, key=lambda x: x["id"])
    random.Random(seed).shuffle(rows)
    count = max(1, round(len(rows) * .15))
    return rows[count:], rows[:count]


def prepare_funsd():
    root = HERE / "data/public/funsd"
    if (root / "provenance.json").exists():
        return
    url = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
    archive = download(url, HERE / "data/downloads/funsd.zip")
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            target = (root / item.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("Unsafe dataset archive path")
        zipped.extractall(root)
    converted = {}
    for source, split in (("training_data", "train"), ("testing_data", "test")):
        rows = []
        for path in sorted((root / "dataset" / source / "annotations").glob("*.json")):
            annotation = json.loads(path.read_text(encoding="utf-8"))
            image_path = path.parent.parent / "images" / (path.stem + ".png")
            with Image.open(image_path) as image:
                width, height = image.size
            words, boxes, labels = [], [], []
            for entity in annotation["form"]:
                tokens = [w for w in entity["words"] if w["text"].strip()]
                for i, word in enumerate(tokens):
                    words.append(word["text"])
                    boxes.append(normalize_box(word["box"], width, height))
                    labels.append("O" if entity["label"] == "other" else ("B-" if i == 0 else "I-") + entity["label"].upper())
            row = dict(id="funsd-"+path.stem, image=image_path.relative_to(HERE).as_posix(), words=words, boxes=boxes, labels=labels)
            validate_row(row, FUNSD_LABELS)
            rows.append(row)
        if not rows:
            raise ValueError("No FUNSD samples found")
        converted[split] = rows
    training, development = split_training(converted["train"])
    for split, rows in (("train", training), ("development", development), ("test", converted["test"])):
        write_rows(root / (split + ".jsonl"), rows)
    write_json(root / "provenance.json", dict(source=url, archive_sha256=digest(archive), development="15% of official training, seed 42", counts=dict(train=len(training), development=len(development), test=len(converted["test"]))))


def prepare_sroie():
    import pyarrow.parquet as pq
    root = HERE / "data/public/sroie"
    if (root / "provenance.json").exists():
        return
    sources = []
    converted = {}
    for split in ("train", "test"):
        url = f"https://huggingface.co/datasets/mp-02/sroie/resolve/{SROIE_REVISION}/data/{split}-00000-of-00001.parquet"
        path = download(url, HERE / "data/downloads" / ("sroie-" + split + ".parquet"))
        sources.append(dict(url=url, sha256=digest(path)))
        parquet = pq.ParquetFile(path)
        rows = []
        for batch in parquet.iter_batches(batch_size=1):
            for item in batch.to_pylist():
                identity = f"sroie-{split}-{len(rows):04d}"
                image = Image.open(io.BytesIO(item["image"]["bytes"])).convert("RGB")
                image_path = root / "images" / (identity + ".jpg")
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(image_path, quality=95)
                # Mirror schema: S-COMPANY, S-DATE, S-ADDRESS, S-TOTAL, O.
                names = ["COMPANY", "DATE", "ADDRESS", "TOTAL", None]
                labels, previous = [], None
                for tag in item["ner_tags"]:
                    entity = names[int(tag)]
                    labels.append("O" if entity is None else ("I-" if previous == entity else "B-") + entity)
                    previous = entity
                # The mirror stores boxes in the normalized 0–1000 coordinate space.
                boxes = [[int(v) for v in b] for b in item["bboxes"]]
                row = dict(id=identity, image=image_path.relative_to(HERE).as_posix(), words=item["words"], boxes=boxes, labels=labels)
                validate_row(row, SROIE_LABELS)
                rows.append(row)
                image.close()
        converted[split] = rows
    training, development = split_training(converted["train"])
    for split, rows in (("train", training), ("development", development), ("test", converted["test"])):
        write_rows(root / (split + ".jsonl"), rows)
    write_json(root / "provenance.json", dict(mirror="mp-02/sroie", revision=SROIE_REVISION, files=sources, development="15% of official training, seed 42", label_conversion="Consecutive S-field tokens converted to BIO", counts=dict(train=len(training), development=len(development), test=len(converted["test"]))))


if __name__ == "__main__":
    prepare_funsd()
    prepare_sroie()
