"""Compare matched Google/corrected OCR runs; extraction outputs stay fixed."""
import argparse
import json
import hashlib
from pathlib import Path
from run import load_manifest, PIPELINES
from evaluate import normalize
from annotate import write


def compare(manifest_path, google, corrected):
    manifest = load_manifest(manifest_path)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if google.get("ocr_variant") != "google" or corrected.get("ocr_variant") != "corrected":
        raise ValueError("Supply Google and corrected OCR runs respectively")
    for name in ("manifest_sha256", "policy_sha256", "split", "model", "git_head", "working_diff_sha256"):
        if google.get(name) != corrected.get(name):
            raise ValueError("Unmatched run metadata: " + name)
    if google.get("manifest_sha256") != digest:
        raise ValueError("Manifest changed since inference")
    maps = [{r["id"]: r for r in p["predictions"]} for p in (google, corrected)]
    entries = [d for d in manifest["documents"] if d["split"] == google["split"]]
    report = {"documents": len(entries), "pipelines": {}, "note":
              "Paired pilot results, not causal proof. Corrected OCR changes text/boxes; hosted-only should be OCR-independent. Failures remain in cohort."}
    # Runs saved before an arm existed lack it entirely; a partially present arm still fails below.
    produced = {name for mapping in maps for row in mapping.values() for name in row["pipelines"]}
    for pipeline in [name for name in PIPELINES if name in produced]:
        improved = regressed = unchanged = failures = 0
        rows = []
        for entry in entries:
            runs = []
            for mapping in maps:
                row = mapping.get(entry["id"])
                if not row or pipeline not in row["pipelines"]:
                    raise ValueError("Incomplete paired predictions: " + entry["id"])
                runs.append(row["pipelines"][pipeline])
            checkpoint_hashes = [r.get("metadata", {}).get("layoutlm", {}).get("weights_sha256") for r in runs]
            if all(checkpoint_hashes) and checkpoint_hashes[0] != checkpoint_hashes[1]:
                raise ValueError("Paired checkpoint mismatch")
            if maps[0][entry["id"]]["image_sha256"] != maps[1][entry["id"]]["image_sha256"]:
                raise ValueError("Paired image mismatch")
            errors = []
            for run in runs:
                predicted = {f["key"]: f.get("value") for f in run.get("fields", [])}
                errors.append(sum(normalize(k, v) != normalize(k, predicted.get(k)) for k, v in entry["fields"].items()))
            failed = any(r.get("error") or r.get("metadata", {}).get("degraded") for r in runs)
            failures += bool(failed)
            # Operational failures are reported separately, never credited as improvement.
            if not failed:
                improved += errors[1] < errors[0]
                regressed += errors[1] > errors[0]
                unchanged += errors[1] == errors[0]
            rows.append({"id": entry["id"], "google_errors": errors[0], "corrected_errors": errors[1], "operational_failure": bool(failed)})
        report["pipelines"][pipeline] = dict(improved=improved, regressed=regressed, unchanged=unchanged, failed_pairs=failures, documents=rows)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "google", "corrected", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.manifest, json.loads(args.google.read_text(encoding="utf-8")), json.loads(args.corrected.read_text(encoding="utf-8")))
    write(args.out, result)
    print(json.dumps({k: {a: b for a, b in v.items() if a != "documents"} for k, v in result["pipelines"].items()}, indent=2))


if __name__ == "__main__":
    main()
