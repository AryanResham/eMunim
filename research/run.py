"""CLI for three-pipeline inference and offline review replay. No model-folder writes."""
import argparse
import asyncio
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from config import settings
from models.schemas import OCRResult
from services.field_contract import keys_for
from services.storage import write_json
from services.extractor import pipeline as pipeline_module
from services.ocr_service import ocr_document
from services.errors import HostedError
from utils.image_utils import normalize_image
from PIL import Image
from evaluate import evaluate

PIPELINES = pipeline_module.PIPELINES
HOSTED_TIERS = ("extract_hosted", "extract_hosted_llm")

def budgeted(original,payload,live,max_calls):
    """Serve from cache first; spend live calls only within the shared research budget."""
    def bounded(*a,**kw):
        try: return original(*a,**{**kw,"allow_network":False})
        except HostedError as exc:
            if exc.kind!="network_disabled": raise
        if not live or payload["calls_used"]+settings.HOSTED_VLM_MAX_ATTEMPTS>max_calls:
            raise HostedError("Research call budget exhausted or live inference disabled",kind="budget")
        try:
            result=original(*a,**{**kw,"allow_network":True})
            payload["calls_used"]+=result["metadata"]["attempts"]
            return result
        except HostedError as exc:
            payload["calls_used"]+=exc.attempts
            raise
    return bounded

def load_manifest(path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    entries=payload["documents"]
    ids=set(); groups={}; hashes={}
    for entry in entries:
        if entry["id"] in ids:
            raise ValueError("Duplicate document id")
        ids.add(entry["id"])
        if entry["split"] not in ("development","test"):
            raise ValueError("Use development/test split")
        if set(entry["fields"]) != set(keys_for(entry["doc_type"])):
            raise ValueError(f"Annotation must define every schema field (null for absent): {entry['id']}")
        if any(v is not None and not isinstance(v,str) for v in entry["fields"].values()):
            raise ValueError("Annotation values must be strings or null")
        for name in ("group", "vendor_group", "template_group"):
            group=entry.get(name)
            if name == "group" and (not isinstance(group, str) or not group.strip()):
                raise ValueError("Every document needs a nonempty group")
            if group:
                identity=(name,group)
                if identity in groups and groups[identity]!=entry["split"]:
                    raise ValueError("Vendor/template group crosses splits")
                groups[identity]=entry["split"]
        image=(path.parent/entry["image"]).resolve()
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if entry.get("sha256") and entry["sha256"] != digest:
            raise ValueError("Image identity changed: " + entry["id"])
        if digest in hashes and hashes[digest]!=entry["split"]:
            raise ValueError("Identical image crosses splits")
        hashes[digest]=entry["split"]
    return payload

def policy(path):
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("version")!="policy-v1" or data.get("selected_on")!="development":
        raise ValueError("Policy must identify version policy-v1 and selection on development data")
    for key in ("review_threshold","fallback_threshold"):
        if not 0<=data[key]<=100: raise ValueError("Thresholds must be percentages")
    return data

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    inventory=sub.add_parser("inventory"); inventory.add_argument("--out",type=Path,required=True)
    for command in ("validate","run","score"):
        p=sub.add_parser(command);p.add_argument("--manifest",type=Path,required=True)
        if command in ("run","score"):
            p.add_argument("--split",choices=["development","test"],required=True)
            p.add_argument("--out",type=Path,required=True)
            p.add_argument("--policy",type=Path,required=True)
        if command=="run":
            p.add_argument("--live",action="store_true")
            p.add_argument("--max-calls",type=int,default=0,help="Physical hosted attempts plus fresh OCR calls")
            p.add_argument("--ocr-variant",choices=["default","google","corrected"],default="default")
            p.add_argument("--release-models",action="store_true",help="Release local checkpoint memory between documents")
        if command=="score":
            p.add_argument("--predictions",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="inventory":
        paths=[]
        for folder in ("raw_invoices","backend/data/raw_invoices"):
            for image in (ROOT/folder).glob("*"):
                if image.suffix.lower() in (".jpg",".jpeg",".png"):
                    paths.append({"path":str(image.relative_to(ROOT)),"sha256":hashlib.sha256(image.read_bytes()).hexdigest()})
        write_json(args.out,{"documents":paths,"note":"Inventory only; not verified labels or a benchmark."})
        print(f"Inventoried {len(paths)} images")
        return
    manifest=load_manifest(args.manifest)
    if args.command=="validate":
        print(f"Validated {len(manifest['documents'])} annotations and split groups")
        return
    frozen=policy(args.policy)
    if args.split == "test" and frozen.get("status") != "frozen":
        raise ValueError("Final test runs/scoring require policy status=frozen after development selection.")
    entries=[e for e in manifest["documents"] if e["split"]==args.split]
    if not entries: raise ValueError("Requested split is empty")
    if args.command=="score":
        payload=json.loads(args.predictions.read_text(encoding="utf-8"))
        if payload["manifest_sha256"]!=hashlib.sha256(args.manifest.read_bytes()).hexdigest():
            raise ValueError("Prediction manifest identity mismatch")
        if payload["policy_sha256"]!=hashlib.sha256(args.policy.read_bytes()).hexdigest():
            raise ValueError("Policy changed since extraction; create a distinct labelled ablation")
        if payload["split"]!=args.split: raise ValueError("Prediction split mismatch")
        report=evaluate(entries,payload["predictions"],frozen["review_threshold"])
        report["review_curves"]={str(t):evaluate(entries,payload["predictions"],t)["pipelines"] for t in (25,50,60,75,85,95)}
        write_json(args.out,report)
        lines=["# Pipeline comparison","", "| Pipeline | Documents | Complete accuracy | Macro field F1 | Median ms | Hosted attempts |","| --- | --- | --- | --- | --- | --- |"]
        for name,r in report["pipelines"].items():
            lines.append(f"| {name} | {r['documents']} | {r['complete_document_accuracy']} | {r['macro_field_f1']} | {r['median_ms']} | {r['hosted_attempts']} |")
        lines+=["","See JSON for per-field results, review policies, error rates, paired intervals and threshold curves.",
                "Review flags do not change extraction F1. No manual-effort time savings were measured by this runner."]
        args.out.with_suffix(".md").write_text("\n".join(lines),encoding="utf-8")
        print("Wrote comparison report and review curves")
        return
    if args.live and args.max_calls<=0: raise ValueError("--live requires a positive --max-calls budget")
    payload={"manifest_sha256":hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "policy_sha256":hashlib.sha256(args.policy.read_bytes()).hexdigest(),"split":args.split,
        "policy":frozen,"provider":"groq","model":settings.HOSTED_VLM_MODEL,"llm_model":settings.HOSTED_LLM_MODEL or None,
        "python":platform.python_version(),"platform":platform.platform(),
        "predictions":[],"calls_used":0,"created_at":time.time(),"ocr_variant":args.ocr_variant}
    try:
        payload["git_head"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        payload["working_diff_sha256"]=hashlib.sha256(subprocess.check_output(["git","diff","HEAD"],cwd=ROOT)).hexdigest()
    except subprocess.CalledProcessError:
        payload["git_head"]=None
    # Both hosted tiers draw paid calls, so both share the one research budget.
    originals={name:getattr(pipeline_module,name) for name in HOSTED_TIERS}
    for name,original in originals.items():
        setattr(pipeline_module,name,budgeted(original,payload,args.live,args.max_calls))
    try:
        for entry in entries:
            image=normalize_image((args.manifest.parent/entry["image"]).read_bytes())
            with Image.open(io.BytesIO(image)) as im: width,height=im.size
            ocr=None;ocr_error=None
            ocr_key="ocr" if args.ocr_variant=="default" else "ocr_"+args.ocr_variant
            if entry.get(ocr_key):
                ocr_path=args.manifest.parent/entry[ocr_key]
                ocr_digest=hashlib.sha256(ocr_path.read_bytes()).hexdigest()
                try:
                    saved_ocr=json.loads(ocr_path.read_text(encoding="utf-8"))
                    if args.ocr_variant!="default":
                        from ocr_inputs import check_ocr
                        check_ocr(saved_ocr,image)
                    if args.ocr_variant=="corrected" and saved_ocr.get("verified") is not True:
                        raise ValueError("Corrected OCR must be manually verified: " + entry["id"])
                    ocr=OCRResult.model_validate(saved_ocr).model_dump()
                except ValueError as exc:
                    ocr_error=str(exc)
            elif args.ocr_variant!="default":
                ocr_error="Missing paired OCR input: " + ocr_key
            elif args.live and payload["calls_used"]<args.max_calls:
                payload["calls_used"]+=1
                try: ocr=asyncio.run(ocr_document(image)).model_dump()
                except Exception as exc: ocr_error=type(exc).__name__
            else: ocr_error="No cached OCR and no live-call budget"
            row={"id":entry["id"],"image_sha256":hashlib.sha256(image).hexdigest(),"pipelines":{}}
            if entry.get(ocr_key): row["ocr_sha256"]=ocr_digest
            for name in PIPELINES:
                try:
                    if name!="hosted_vlm" and ocr_error: raise ValueError(ocr_error)
                    row["pipelines"][name]=pipeline_module.run_pipeline(pipeline=name,image_bytes=image,ocr_result=ocr,
                        doc_type=entry["doc_type"],image_width=width,image_height=height,
                        fallback_threshold=frozen["fallback_threshold"],review_threshold=frozen["review_threshold"])
                except Exception as exc:
                    row["pipelines"][name]={"error":str(exc) if isinstance(exc,(HostedError,ValueError)) else type(exc).__name__,
                        "fields":[],"metadata":{"hosted":{"attempts":getattr(exc,"attempts",0)}}}
            payload["predictions"].append(row)
            write_json(args.out,payload)
            print(f"Saved {entry['id']} ({len(payload['predictions'])}/{len(entries)})")
            if args.release_models:
                import gc
                from services.extractor.layoutlm_extractor import _models
                _models.clear()
                gc.collect()
    finally:
        for name,original in originals.items():
            setattr(pipeline_module,name,original)

if __name__=="__main__":
    main()
