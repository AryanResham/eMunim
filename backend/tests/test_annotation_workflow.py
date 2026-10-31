"""Dataset integrity and paired OCR research safeguards."""
import hashlib
import json
import sys
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research"))
from annotate import prepare, export, validate_annotation
from run import load_manifest
from ocr_inputs import check_ocr
from compare_ocr import compare


def workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (80, 100), "white").save(source / "one.png")
    Image.new("RGB", (80, 100), "black").save(source / "two.png")
    target = tmp_path / "labels"
    assert prepare(source, target, "GST_INVOICE") == 2
    assert prepare(source, target, "GST_INVOICE") == 0
    return target


def verify(document):
    document.update(status="verified", annotator="Researcher", group=document["id"],
                    vendor_group=document["id"], template_group=document["id"],
                    reviewed_fields=list(document["fields"]))


def test_unknown_fields_cannot_be_exported_as_absent(tmp_path):
    target = workspace(tmp_path)
    path = target / "annotations.json"
    data = json.loads(path.read_text())
    document = data["documents"][0]
    verify(document)
    document["reviewed_fields"].pop()
    with pytest.raises(ValueError, match="Review every field"):
        validate_annotation(document)
    verify(document)
    path.write_text(json.dumps(data))
    out = tmp_path / "benchmark/manifest.json"
    assert export(target, out) == 1
    assert len(load_manifest(out)["documents"]) == 1
    doc = data["documents"][0]
    (target / doc["image"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="Image changed"):
        export(target, out)


@pytest.mark.parametrize("leaking_key", ["vendor_group", "template_group"])
def test_export_rejects_vendor_or_template_leakage(tmp_path, leaking_key):
    target = workspace(tmp_path)
    path = target / "annotations.json"
    data = json.loads(path.read_text())
    for i, document in enumerate(data["documents"]):
        verify(document)
        document["split"] = "test" if i else "development"
        document[leaking_key] = "shared"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="crosses splits"):
        export(target, tmp_path / "benchmark/manifest.json")


def test_ocr_rejects_wrong_image_and_invalid_boxes(tmp_path):
    import io
    stream = io.BytesIO()
    Image.new("RGB", (80, 100)).save(stream, format="PNG")
    image = stream.getvalue()
    payload = {"full_text": "invoice", "words": [{"text": "invoice", "bounding_box": [[0,0],[20,0],[20,10],[0,10]]}],
               "image_sha256": hashlib.sha256(image).hexdigest()}
    check_ocr(payload, image)
    payload["image_sha256"] = "wrong"
    with pytest.raises(ValueError, match="different normalized image"):
        check_ocr(payload, image)
    payload["words"][0]["bounding_box"][0][0] = -1
    with pytest.raises(ValueError, match="within the image"):
        check_ocr(payload, image)


def test_annotation_http_save_and_origin_guard(tmp_path, monkeypatch):
    import threading
    import urllib.request
    import urllib.error
    from http.server import HTTPServer
    import annotate
    target = workspace(tmp_path)
    servers = []
    def factory(address, handler):
        server = HTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        return server
    # Start only after constructing the server, without polling or a background process.
    class RunningServer:
        def __init__(self, address, handler):
            self.server = factory(address, handler)
        def serve_forever(self):
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
    monkeypatch.setattr(annotate, "HTTPServer", RunningServer)
    annotate.serve(target, 8765)
    server = servers[0]
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/", timeout=3) as response:
            assert b"Research annotation" in response.read()
        with urllib.request.urlopen(base + "/api/schema", timeout=3) as response:
            assert "GST_INVOICE" in json.load(response)
        with urllib.request.urlopen(base + "/api/annotations", timeout=3) as response:
            document = json.load(response)["documents"][0]
        document["notes"] = "Manually checked document"
        request = urllib.request.Request(base + "/api/annotations", data=json.dumps(document).encode(), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request, timeout=3) as response:
            assert json.load(response)["saved"]
        assert json.loads((target / "annotations.json").read_text())["documents"][0]["notes"] == document["notes"]
        request.add_header("Origin", "https://unrelated.example")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=3)
        assert exc.value.code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_paired_ocr_comparison_counts_improvement_and_failures(tmp_path):
    target = workspace(tmp_path)
    path = target / "annotations.json"
    data = json.loads(path.read_text())
    verify(data["documents"][0])
    data["documents"][0]["fields"]["invoice_no"] = "INV-1"
    path.write_text(json.dumps(data))
    manifest = tmp_path / "benchmark/manifest.json"
    export(target, manifest)
    identity = data["documents"][0]["id"]
    metadata = dict(manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(), policy_sha256="fixed", split="development", model="same")
    google = {**metadata, "ocr_variant":"google", "predictions":[{"id":identity,"image_sha256":"same","pipelines":{
        p:{"fields":[]} for p in ("ocr_layoutlm","hosted_vlm","layoutlm_hosted_fallback")}}]}
    corrected = json.loads(json.dumps(google))
    corrected["ocr_variant"] = "corrected"
    corrected["predictions"][0]["pipelines"]["ocr_layoutlm"]["fields"] = [{"key":"invoice_no","value":"INV-1"}]
    corrected["predictions"][0]["pipelines"]["layoutlm_hosted_fallback"]["error"] = "unavailable"
    result = compare(manifest, google, corrected)
    assert result["pipelines"]["ocr_layoutlm"]["improved"] == 1
    assert result["pipelines"]["hosted_vlm"]["unchanged"] == 1
    assert result["pipelines"]["layoutlm_hosted_fallback"]["failed_pairs"] == 1
    corrected["policy_sha256"] = "changed"
    with pytest.raises(ValueError, match="Unmatched run metadata"):
        compare(manifest, google, corrected)
