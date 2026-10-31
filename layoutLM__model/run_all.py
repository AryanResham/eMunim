"""Durable sequential supervisor: FUNSD → SROIE → six CUDA synthetic models."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from common import HERE, ROOT, MODEL_REVISION, LABEL_SETS, DOC_TYPE_TO_MODEL, digest, weight_file, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id",required=True)
    args=parser.parse_args()
    if not args.run_id.replace('-','').replace('_','').isalnum():
        raise ValueError("Invalid run ID")
    config=json.loads((HERE/"training_config.json").read_text())
    run=HERE/"runs"/args.run_id
    run.mkdir(parents=True,exist_ok=True)
    lock=(HERE/"runs/training.lock").open("a+b")
    if sys.platform=="win32":
        import msvcrt
        lock.seek(0);lock.write(b"1");lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=dict(run_id=args.run_id,pid=os.getpid(),status="starting",started_at=datetime.now(timezone.utc).isoformat(),
        cuda_required=True,completed_stages=[],configuration=config,source_code_sha256={p.name:digest(p) for p in HERE.glob("*.py")})
    state_path=run/"status.json"
    def status(phase,**updates):
        state.update(phase=phase,updated_at=datetime.now(timezone.utc).isoformat(),**updates)
        write_json(state_path,state)
        print(json.dumps({"phase":phase,"status":state["status"],**updates}),flush=True)
    env={**os.environ,"TOKENIZERS_PARALLELISM":"false","OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4",
        "HF_HOME":str(HERE/"data/huggingface"),"HF_HUB_DISABLE_XET":"1","HF_HUB_DOWNLOAD_TIMEOUT":"180"}
    os.environ.update({k:env[k] for k in ("HF_HOME","HF_HUB_DISABLE_XET","HF_HUB_DOWNLOAD_TIMEOUT")})
    try:
        status("download_base",status="running")
        import requests
        from prepare_public import download
        response=requests.get(f"https://huggingface.co/api/models/microsoft/layoutlmv3-base/revision/{MODEL_REVISION}",timeout=30)
        response.raise_for_status()
        files=[entry["rfilename"] for entry in response.json()["siblings"]]
        selected="model.safetensors" if "model.safetensors" in files else "pytorch_model.bin"
        source=HERE/"data/pretrained"/MODEL_REVISION
        for filename in files:
            if '/' not in filename and (filename.endswith('.json') or filename in ("vocab.txt","merges.txt",selected)):
                download(f"https://huggingface.co/microsoft/layoutlmv3-base/resolve/{MODEL_REVISION}/{filename}",source/filename)
        status("prepare_public_datasets",base_revision=MODEL_REVISION)
        from prepare_public import prepare_funsd,prepare_sroie
        prepare_funsd();prepare_sroie()
        def stage(name,source,destination,doc_type=None):
            label=name+('-'+doc_type.lower() if doc_type else '')
            status(label,active_stage=label)
            completed=destination/"training_summary.json"
            if completed.exists():
                previous=json.loads(completed.read_text())
                if previous["provenance"]["source_weights_sha256"]!=digest(weight_file(source)):
                    raise ValueError("Completed stage has different parent weights: "+label)
                print("Already complete:",label,flush=True)
            else:
                command=[sys.executable,"-u",str(HERE/"train_stage.py"),"--stage",name,"--source",str(source),
                    "--output",str(destination),"--run-id",args.run_id,"--epochs",str(config["epochs"][name]),
                    "--learning-rate",str(config["learning_rate"]),"--accumulation",str(config["gradient_accumulation"]),
                    "--sanity-steps",str(config["sanity_steps"])]
                if doc_type:
                    command.extend(["--doc-type",doc_type])
                with (run/(label+".log")).open("a",encoding="utf-8") as log:
                    child=subprocess.Popen(command,cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT)
                    status(label,child_pid=child.pid)
                    result=child.wait()
                if result:
                    raise RuntimeError(f"Stage {label} failed (exit {result}); inspect {label}.log. No later stages were started.")
            state["completed_stages"].append(label)
            status(label,child_pid=None)
        funsd=HERE/"layoutlm-funsd-trained"
        sroie=HERE/"layoutlm-sroie-trained"
        stage("funsd",source,funsd)
        stage("sroie",funsd,sroie)
        status("generate_synthetic")
        from synthetic import prepare_synthetic
        prepare_synthetic(config["synthetic"]["train_per_type"],config["synthetic"]["development_per_type"],config["synthetic"]["test_per_type"])
        for doc_type in LABEL_SETS:
            stage("synthetic",sroie,HERE/DOC_TYPE_TO_MODEL[doc_type],doc_type)
        status("complete",status="complete",active_stage=None,finished_at=datetime.now(timezone.utc).isoformat(),
            note="Training complete; Indian MSME final testing still requires verified annotations.")
        return 0
    except Exception as exc:
        status("failed",status="failed",error=str(exc),finished_at=datetime.now(timezone.utc).isoformat())
        traceback.print_exc()
        return 1
    finally:
        lock.close()


if __name__=="__main__":
    sys.exit(main())
