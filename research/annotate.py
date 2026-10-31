"""Local annotation workbench. No model calls or checkpoint writes."""
import argparse
import hashlib
import json
import sys
import shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.field_contract import keys_for
from services.extractor.field_mapper import LABEL_SETS
from utils.image_utils import normalize_image


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def prepare(source, workspace, doc_type):
    """Import single-page images, deduplicating normalized content."""
    path = workspace / "annotations.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": "annotations-v1", "documents": []}
    known = {d["sha256"] for d in data["documents"]}
    files = [source] if source.is_file() else sorted(source.rglob("*"))
    imported = 0
    for image in files:
        if image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            continue
        content = normalize_image(image.read_bytes())
        digest = hashlib.sha256(content).hexdigest()
        if digest in known:
            continue
        identity = digest[:20]
        target = workspace / "images" / (identity + ".jpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        data["documents"].append({"id": identity, "image": "images/" + target.name,
            "original_name": image.name, "sha256": digest, "doc_type": doc_type,
            "group": "", "vendor_group": "", "template_group": "", "split": "development",
            "annotator": "", "verifier": "", "notes": "", "status": "draft",
            "fields": {k: None for k in keys_for(doc_type)}, "reviewed_fields": []})
        known.add(digest)
        imported += 1
    write(path, data)
    return imported


def validate_annotation(document):
    keys = set(keys_for(document["doc_type"]))
    if set(document["fields"]) != keys:
        raise ValueError("Fields must match document type")
    if document["split"] not in ("development", "test"):
        raise ValueError("Invalid split")
    if document.get("status") not in ("draft", "verified", "excluded"):
        raise ValueError("Invalid annotation status")
    if not set(document.get("reviewed_fields", [])).issubset(keys):
        raise ValueError("Unknown reviewed field")
    if any(v is not None and (not isinstance(v, str) or not v.strip()) for v in document["fields"].values()):
        raise ValueError("Use nonempty strings or null for absent fields")
    if document["status"] == "verified":
        if set(document["reviewed_fields"]) != keys:
            raise ValueError("Review every field, including absent fields, before verification")
        if not all(str(document.get(k, "")).strip() for k in ("annotator", "group", "vendor_group", "template_group")):
            raise ValueError("Verified documents need annotator, group, vendor and template groups")


def export(workspace, out):
    from run import load_manifest
    data = json.loads((workspace / "annotations.json").read_text(encoding="utf-8"))
    entries = []
    for document in data["documents"]:
        validate_annotation(document)
        if document["status"] != "verified":
            continue
        digest = hashlib.sha256((workspace / document["image"]).read_bytes()).hexdigest()
        if digest != document["sha256"]:
            raise ValueError("Image changed after import: " + document["id"])
        entry = {k: document[k] for k in ("id", "doc_type", "group", "vendor_group", "template_group", "split", "fields", "annotator", "verifier", "notes")}
        # Bundle images with the manifest, avoiding absolute machine-specific paths.
        target = out.parent / "images" / (document["id"] + ".jpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = workspace / document["image"]
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        entry.update(image="images/" + target.name, sha256=digest)
        entries.append(entry)
    if not entries:
        raise ValueError("No verified annotations to export")
    # Validate a candidate before replacing an existing manifest.
    candidate = out.with_suffix(".candidate.json")
    write(candidate, {"version": "manifest-v1", "documents": entries})
    try:
        load_manifest(candidate)
        candidate.replace(out)
    finally:
        candidate.unlink(missing_ok=True)
    return len(entries)


def serve(workspace, port):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, content, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(content if isinstance(content, bytes) else content.encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Normal when a browser cancels an image while changing documents.

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self.send(200, (Path(__file__).with_name("annotation.html")).read_bytes(), "text/html; charset=utf-8")
            if path == "/api/annotations":
                return self.send(200, (workspace / "annotations.json").read_bytes())
            if path == "/api/schema":
                return self.send(200, json.dumps({t: keys_for(t) for t in LABEL_SETS}))
            data = json.loads((workspace / "annotations.json").read_text(encoding="utf-8"))
            document = next((d for d in data["documents"] if path == "/image/" + d["id"]), None)
            if document:
                return self.send(200, (workspace / document["image"]).read_bytes(), "image/jpeg")
            self.send(404, '{}')

        def do_POST(self):
            # Reject cross-origin writes; this server intentionally binds only loopback.
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self.send(403, '{"error":"Invalid origin"}')
            try:
                if self.path != "/api/annotations":
                    return self.send(404, '{}')
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 1_000_000:
                    raise ValueError("Invalid request size")
                update = json.loads(self.rfile.read(length))
                path = workspace / "annotations.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                document = next(d for d in data["documents"] if d["id"] == update["id"])
                allowed = ("doc_type", "fields", "reviewed_fields", "group", "vendor_group", "template_group", "split", "annotator", "verifier", "notes", "status")
                candidate = {**document, **{k: update[k] for k in allowed if k in update}}
                validate_annotation(candidate)
                data["documents"][data["documents"].index(document)] = candidate
                write(path, data)
                self.send(200, '{"saved":true}')
            except (ValueError, KeyError, StopIteration, TypeError) as exc:
                self.send(400, json.dumps({"error": str(exc)}))

    print(f"Annotation workbench: http://127.0.0.1:{port} (Ctrl+C to stop)", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "serve", "export"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", type=Path, default=ROOT / "research/local/annotations")
        if name == "prepare":
            p.add_argument("--source", type=Path, required=True)
            p.add_argument("--doc-type", choices=list(LABEL_SETS), default="GST_INVOICE")
        elif name == "serve":
            p.add_argument("--port", type=int, default=8765)
        else:
            p.add_argument("--out", type=Path, default=ROOT / "research/local/manifest.json")
    args = parser.parse_args()
    if args.command == "prepare":
        print(f"Imported {prepare(args.source, args.workspace, args.doc_type)} new images")
    elif args.command == "export":
        print(f"Exported {export(args.workspace, args.out)} verified annotations")
    else:
        serve(args.workspace, args.port)


if __name__ == "__main__":
    main()
