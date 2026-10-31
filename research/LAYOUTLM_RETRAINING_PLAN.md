# Clean LayoutLM retraining chronology

Status (2026-10-24): obsolete outputs/scripts cleaned from `layoutLM__model`;
original datasets/evaluation evidence preserved in `legacy_data`/`legacy_evaluation`.
The mandatory CUDA sequence completed as native Windows run `cuda-20261024`:
FUNSD, SROIE and all six type-specific synthetic models are exported.
Current progress/failures: `layoutLM__model/runs/cuda-20261024/status.json`.
Export verification: `layoutLM__model/runs/cuda-20261024/artifact_verification.json`.
Reported training/development scores are not held-out Indian MSME test results;
that final evaluation remains pending verified real annotations.
Source: LY_artifacts/LY Project Presentation.pdf, especially slides 3 and 10–11.

## Objective and constraints

Rebuild reproducible LayoutLMv3 field extraction for the six existing document
types. Train the extraction model independently of hosted fallback and validation;
then compare all three production pipelines and their reliability. Fine-tune a
pretrained encoder rather than pretraining a transformer from random weights.

User-confirmed sequence: pretrained LayoutLMv3 → FUNSD fine-tuning → SROIE
fine-tuning → synthetic accounting fine-tuning → held-out Indian MSME testing.
FUNSD and SROIE are mandatory sequential training stages. Indian MSME documents
are a final evaluation dataset, never training, model-selection, calibration or
threshold-tuning data. Development decisions use public/synthetic development
data. This measures transfer to unseen real Indian documents.

Measured hardware: RTX 3050 Laptop GPU, 4 GB VRAM, approximately 3.22 GB free
VRAM during inspection; 13.9 GB system RAM, approximately 2.7 GB currently free.
GPU availability does not establish that full fine-tuning will fit.

The training directory is now named `layoutLM__model` and resolves to the repository's immediate
child with that exact name. The pre-cleanup inventory is saved outside it at
`research/local/layoutlm_cleanup_inventory.json`. Cleanup preserved source data
and historical evaluation evidence and removed obsolete checkpoints/scripts.

## Ordered execution

1. Record the old baseline, checkpoint identities and known failures outside the
   deletion target. Existing research audit outputs already live outside it.
   Stop any training/inference process using these weights before cleanup.
2. After review of this chronology, validate the resolved deletion target stays
   inside the named repository folder and remove its children using PowerShell
   literal paths. Keep the parent directory. Never delete other model folders,
   raw_invoices, LY_artifacts, backend/data or research/local.
3. Rebuild a minimal versioned training workspace: dataset converters, generator,
   shared label schema, split manifests, trainer, evaluator, configuration,
   dependency lock and model export. Separate code from generated data/checkpoints.
4. Freeze each type's BIO schema against the backend contract. Include the GST
   checkpoint's previously missing IGST, due-date and PO-number labels. Count
   actual labels from the schema rather than hard-coding the slide's 81 labels.
   Use null for genuine absence, never unknown ground truth.
5. Acquire public datasets with provenance, access/license checks and official
   splits. Treat their labels as their own tasks. Do not pretend SROIE annotates
   GSTIN or other Indian fields. Any entity-label conversion must be explicit.
6. Create synthetic data with exact word boxes and BIO truth at generation time.
   Vary vendor/template families, layouts, field positions, fonts, dates, tax
   structures, repeated amounts, optional fields, identifiers and document lengths.
   Vary values independently of layout. Include sparse layouts from the failed
   smoke cases as training patterns, but reserve distinct evaluation examples.
7. Make train/development/test splits by vendor/template family before rendering
   augmentations. Keep originals and all variants in the same split. Reject exact
   and near duplicates crossing splits. Preserve official public test sets.
   Never use the existing 34 real-image drafts as verified labels.
8. Apply the same image normalization as production. Cache Google OCR for an
   explicitly bounded subset, retain generator-exact OCR as a control, and align
   labels geometrically with manual checks of ambiguous matches. Never blindly
   reuse exact-token labels after OCR changes segmentation or ordering.
9. Prepare images, words and boxes with LayoutLMv3Processor(apply_ocr=False).
   Scale boxes to 0–1000, verify ordering and alignment, and use the model's BPE
   tokenizer (the slide's WordPiece description needs correction). Label first
   subtokens, mask padding/special/ignored positions with -100 consistently.
10. Handle long documents with overlapping token windows and retained word IDs;
    reconstruct predictions across windows deterministically. Do not silently
    discard totals beyond the first 512-token window. Implement and test matching
    inference behavior before evaluating/exporting window-trained models.
11. Run dataset audits: per-label support, O/entity balance, BIO legality,
    field/token alignment, box overlays and field retention after windowing.
    Overfit 8–16 known examples as a sanity check; failure blocks a full run.
12. Run a short GPU trial to measure peak VRAM, system RAM, step time and estimated
    epoch duration. Try mixed precision, microbatch 1, gradient accumulation and
    gradient checkpointing with streamed/on-demand samples. Do not preload the
    entire encoded dataset. If full fine-tuning does not fit, select a documented
    frozen-backbone/partial-unfreeze experiment or an external GPU environment;
    do not silently change the method or promise local feasibility.
13. Start from a pinned microsoft/layoutlmv3-base revision and fine-tune on FUNSD
    first, using its form entity labels. Save and evaluate this stage separately.
    Continue from the FUNSD-trained encoder on SROIE's receipt extraction task,
    with a newly initialized receipt classification head, and evaluate its official
    held-out split. Transfer encoder weights across tasks and initialize a new task
    head whenever label meanings change, even if label counts happen to match.
    FUNSD teaches supervised form-entity extraction; it does not add a separate OCR
    reader, and the base model already has pretrained document representations.
14. Continue from the FUNSD→SROIE encoder into a GST synthetic pilot with a new
    accounting-label head. All production models follow the full mandatory chain;
    no direct-base shortcut replaces it. Use tentative
    learning rate 2e-5, AdamW, weight decay 0.01 and up to 3–5 epochs with development
    early stopping; finalize settings after the memory/sanity trial, not by assertion.
15. Investigate missing/high-confidence-wrong fields and unseen-layout failures.
    Adjust training data or the loss only from development evidence. Record any
    class balancing or sampling change as an explicit experiment. Train the other
    five type-specific models sequentially from the same FUNSD→SROIE checkpoint,
    each with its own synthetic data and accounting head, after the pilot passes.
    Do not chain one document type's synthetic model into the next type's model.
16. Prepare verified Indian MSME test annotations separately from training work.
    Check field values, spans/boxes where needed, document groups and duplicates.
    Keep these images, OCR and labels out of training and development selection.
    Do not assume the 34 imported drafts or the PPT's ~500 target are already a
    verified dataset. Testing remains pending until the cohort is ready. There is
    no real-Indian-data fine-tuning stage in this protocol.
17. Select checkpoints using public/synthetic development field/entity metrics and complete-document
    accuracy. Token accuracy alone can reward all-O predictions. Report per-field
    precision/recall/F1, missing/wrong/extra values, long-document and unseen-layout
    breakdowns, OCR controls, memory, latency and training curves. Repeat promising
    configurations across seeds if compute permits; disclose seed limitations.
18. Export processor, config, tokenizer and weights to backend-compatible per-type
    directories, with dataset/code/checkpoint hashes and a training-method card.
    Test label alignment, window reconstruction, GPU/CPU inference, memory release,
    and pure local extraction with no hosted/regex assistance hidden in its score.
19. Calibrate confidence/review and hybrid-routing thresholds on public/synthetic development data.
    Freeze model, prompt, rules, schemas and policy. Run P1/P2/P3 on the same untouched
    real test cohort; replay A/B/C reliability policies on saved predictions. Separate
    cold-cache timing/cost trials from cached paired-output analysis. Count failures.
    Do not revise training or thresholds after looking at Indian MSME test results
    and then report the same cohort as untouched; any later adaptation needs a new
    independent final test cohort.
20. Run backend and browser regressions and save reproducibility artifacts, paper
    tables, uncertainty estimates, regressions and limitations. Do not target a
    promised accuracy or copy historical slide scores into the new results.

## Pilot scale and gates

Start with one GST type, roughly 1,000 generated training documents across at least
20 independently designed template families, plus separately grouped development
and synthetic test sets. This is a proposed starting budget, not an adequacy claim.
Extend per-type volume only after diversity/support audits. Do not count different
values on the same template as independent layout families.

Required gates: valid labels/boxes; a successful tiny-set fit; measured hardware
feasibility; extraction beyond an all-O baseline; all target fields retained through
token windows; development improvement and transparent failure reporting. Define
numerical pilot acceptance thresholds before the main pilot after auditing support.

## Dependencies and credentials

Training requires compatible pinned torch/CUDA, transformers, accelerate, image
and dataset tooling, and evaluation packages. Google Vision uses the existing key
only for production-OCR alignment experiments. Groq is for later pipeline comparison,
not training labels. A Hugging Face token is needed only if the selected download
requires authentication/access; verify availability during acquisition. DATABASE_URL
is unrelated to model fitting. No service key replaces verified real labels or GPU
memory. Download and training-time estimates follow the measured pilot.

References:
- Presentation: LY_artifacts/LY Project Presentation.pdf, slides 3, 10 and 11.
- https://huggingface.co/docs/transformers/model_doc/layoutlmv3
- https://guillaumejaume.github.io/FUNSD/
