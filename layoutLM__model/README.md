# Staged CUDA LayoutLMv3 training

For the separately generated, annotated `msme_6000` synthetic dataset, run
`python -u layoutLM__model/train_msme.py --run-id msme-6000-20261031`.
This continues the six existing per-type checkpoints, retaining their heads,
with 800 training / 100 development / 100 held-out test documents per type.
New models are saved under `runs/<run-id>/models/`; existing models are preserved.
The dataset audit records missing target fields and checks party/document split
isolation. Layout families are shared across splits, so these are not unseen-layout
generalization results. Only visible annotated values become training targets.
This synthetic corpus is distinct from real Indian MSME final-test documents.

Evaluate existing versus candidate checkpoints using
`python layoutLM__model/evaluate_msme.py --run-id msme-6000-20261031`, then replay
semantic field scoring with `python layoutLM__model/review_msme.py --run-id msme-6000-20261031`.
The replay collapses identical repeated gold spans into one field value; original
metrics/predictions remain unchanged. Results and real-document spot checks are
under `runs/<run-id>/evaluation/`. Read `findings.md` and `activation_decision.json`
before selecting a candidate root with `LAYOUTLM_MODEL_ROOT`.

Mandatory order: microsoft/layoutlmv3-base → FUNSD → SROIE → six independent
synthetic document-type models. Indian MSME images are final-test-only and are
never read by these training scripts. All target schemas come from the backend.

`legacy_data/` and `legacy_evaluation/` preserve prior datasets and evidence;
none of the new stages loads them. Obsolete weights and legacy scripts were
removed. Outputs retain the per-type folder names expected by the backend.

Run in the foreground from the repository root:

```powershell
python -u layoutLM__model/run_all.py --run-id cuda-20261024
```

On Windows, to run without a visible console and survive the terminal closing:

```powershell
powershell -ExecutionPolicy Bypass -File layoutLM__model/launch_training.ps1
```

Review `runs/<run-id>/status.json`, per-stage `status.json`, logs, dataset audits,
sanity metrics, history and source/parent-weight hashes. Failures stop the chain;
there is no CPU fallback, hidden layer freezing or stage skipping. Rerun with
the same ID to resume from the last completed epoch. Interrupted epochs restart.
Only one supervisor can hold the training lock. Do not change code/config/data
during a run. Completed stages are reused only with matching parent weights.

Mixed precision, microbatch 1, accumulation 8, gradient checkpointing, overlapping
512-token windows (stride 96) and on-demand image decoding reduce memory. A real
CUDA tiny-set fit gate runs before each stage. Full fine-tuning may still exceed
4 GB VRAM; any OOM is reported and stops rather than silently changing the method.

Public training splits reserve 15% for development, seed 42. Official public test
sets are preserved and not used for selection. Synthetic data uses disjoint
parametric layout/vendor families across train/development/test. The generator
currently creates 40 parameterized families, not 40 independently authored layouts.
Exact generated OCR is used for this first training cohort; Google OCR alignment
is a separate controlled experiment. No Google or Groq key is required to train.

Current checkpoints are selected by development entity F1 (public tasks) or
normalized field F1 (synthetic), with early stopping after two unimproved epochs.
Every label schema change initializes a fresh token-classification head while
transferring the preceding encoder. Synthetic siblings all start from SROIE.

Sources: official FUNSD archive https://guillaumejaume.github.io/FUNSD/dataset.zip;
SROIE mirror https://huggingface.co/datasets/mp-02/sroie at pinned revision recorded
in common.py, with mirror S-field tags converted explicitly to contiguous BIO;
LayoutLMv3 base pinned in common.py. Downloads and converted split provenance
include SHA-256 checksums. Review dataset terms before any non-research reuse.
