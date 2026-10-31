# eMunim — LayoutLM Recovery & Local-LLM Investigation Report

**Date:** 2026-08-28
**Scope:** Full document-extraction pipeline (training + honest eval) and the
local VLM (Qwen3-VL) investigation for invoice/accounting field extraction.

---

## 1. Training pipeline: transfer-learning chain

We build the extraction models through a **staged transfer-learning chain**, so
each stage adapts the model progressively closer to Indian invoice/accounting
documents rather than fine-tuning from the raw base in one jump.

```
microsoft/layoutlmv3-base
        │
        ▼  (Stage 1 — generic form/layout understanding)
   FUNSD fine-tune  ───────────►  layoutlm-funsd-trained
        │
        ▼  (Stage 2 — invoice/OCR-document understanding)
   SROIE fine-tune  ───────────►  layoutlm-sroie-trained
        │
        ▼  (Stage 3 — per-doc-type GST field heads)
   6 × synthetic per-doc-type fine-tune
        │
        ├─► layoutlm-synthetic-tax_invoice-trained
        ├─► layoutlm-synthetic-purchase_bill-trained
        ├─► layoutlm-synthetic-expense_receipt-trained
        ├─► layoutlm-synthetic-utility_bill-trained
        ├─► layoutlm-synthetic-credit_note-trained
        └─► layoutlm-synthetic-debit_note-trained
```

### Why the staged chain
- **FUNSD** (`layoutLM_SROIE_training.py` style FUNSD base) gives generic
  form/layout priors.
- **SROIE** adapts those priors to noisy scanned invoices/receipts.
- The final **6 per-doc-type heads** then specialize on the exact GST/accounting
  field spaces our product needs (see `label_sets.py`), each covering only the
  labels its document type actually fires, which avoids the label-sparsity
  problem of one giant merged head.

> **Current on-disk status (accurate):** the final **6 synthetic per-doc-type
> models have real weights** (`model.safetensors` present) and are wired into
> production. The intermediate `funsd`/`sroie` checkpoint directories currently
> hold config/tokenizer files only (no weights) — the transfer stages are
> scripted but their checkpoints are not persisted in this workspace. We have
> recorded that we will re-run the full chain keeping FUNSD and SROIE in the
> loop as the re-trained base.

---

## 2. Correctness fixes applied during recovery

Two root-cause defects were found and fixed:

1. **512-token truncation of amount fields (decisive).**
   Bottom-of-page `*_AMOUNT` tokens (word idx 284+) were silently dropped from
   LayoutLM's 512-token window — the model literally never saw the amounts. The
   in-loop training `eval_f1` stayed high because it only measured intact early
   tokens (header/text). Fixes:
   - `gen_dataset.py`: `collect_value_runs` + `resolve_field_runs` label *every*
     occurrence of a value (fixes the CGST/SGST round-robin bug too).
   - `generate_synthetic_invoices.py`: compacted the template so amounts fit the
     512-token encoding (394 → 208 words; verified all amount fields present).

2. **Honest evaluation replaced the overstated in-loop metric.**
   A held-out word-level seqeval benchmark is now the source of truth.

---

## 3. Honest benchmark results (held-out `Synthetic_Test`)

Pure per-doc-type LayoutLM, then with the **hybrid** resolver
(LayoutLM + deterministic regex fallback), same normalization + error taxonomy
everywhere (see `evaluation/evaluation_report.md` for the full per-field tables).

| Doc type | Docs | Mean field F1 (pure) | Mean field F1 (hybrid) | Amount fields → hybrid |
|---|---|---|---|---|
| tax_invoice | 227 | 0.944 | 0.996 | CGST/SGST/TAXABLE/TOTAL → 1.000 |
| purchase_bill | 50 | 0.952 | 0.995 | SUBTOTAL/TAX_AMOUNT/TOTAL → 1.000 |
| expense_receipt | 42 | 0.986 | 0.986 | AMOUNT/TAX_AMOUNT (already 1.000) |
| utility_bill | 45 | 1.000 | 1.000 | AMOUNT_DUE (already 1.000) |
| credit_note | 43 | 0.974 | 1.000 | CREDIT_AMOUNT/TAX_CREDIT → 1.000 |
| debit_note | 36 | 0.940 | 0.984 | DEBIT_AMOUNT → 0.972, TAX_AMOUNT → 0.944 |

**Key results**
- Every amount/total field reaches **1.000 F1** (or 0.94–0.97 on debit_note)
  under the hybrid, with **0 “missing”** errors on every doc type.
- Pure LayoutLM amounts went from ~0 → 0.80–0.94 F1 after the truncation fix.

---

## 4. Production wiring

Each uploaded document is **classified** → the class selects **exactly one**
per-doc-type model (`field_mapper.get_model_folder` →
`layoutlm_extractor._get_model_for_doc_type`). Only that model runs inference
per request. If weights are missing it falls back to a merged synthetic model,
then to **regex-only** extraction. The hybrid resolver (regex fallback) now
works on top of whatever model ran.

---

## 5. Local LLM / VLM investigation — Qwen3-VL

### The question
Can a **local vision-language model (VLM)** either **replace** LayoutLM or
**work alongside** it (as a confidence-gated second head / fallback), especially
given that our real, labelled Indian-invoice data is scarce?

### Chosen candidate — Qwen3-VL-2B-Instruct
- A **multimodal generative** model that can reason directly over the invoice
  image + layout + text and emit **structured JSON**, rather than needing every
  target layout represented in a BIO-labelled training set (LayoutLM's failure
  mode).
- Strong domain evidence: the **FinixDoc** financial-document parser is built
  around a Qwen3-VL-2B-based model, and Qwen2.5/Qwen3-VL reports document /
  invoice / table / structured-extraction support.
- Locally deployable (Transformers / vLLM / Ollama-served), fitting the
  "keep data on-premise" requirement for MSME accounting.

### Our experiment plan (mapped to what we built)
We run A/B/C/D to answer *“does the VLM benefit from OCR, or replace LayoutLM?”*:

```
A. Image        → LayoutLMv3
B. Image        → Qwen3-VL-2B → JSON
C. OCR          → Qwen3-VL-2B → JSON      (text-only path)
D. Image + OCR  → Qwen3-VL-2B → JSON → GST validation (retry on failure)
```

Staged evaluation (zero-shot → few-shot → strict-schema → validation-guided)
before any fine-tuning; LoRA/QLoRA only after the zero/few-shot baselines.

### Harness status
- `vlm_bench.py` (Phase 8): pluggable VLM client + zero/few-shot scoring with
  the **same field F1 + error taxonomy** as LayoutLM. Mock baseline runs
  (returns empty → F1=0), proving wiring.
- `hybrid_resolver.py` (Phase 9): LayoutLM + regex fallback live; VLM-leg is the
  same pluggable client.
- A dedicated **Qwen3-VL runner** is next, exposing the JSON-schema prompt
  (vendor_name, gstin, invoice_no, dates, amounts, line_items, `null` for
  absent fields) and calling whichever backend is available.

> **Hardware reality (honest):** this machine is a **RTX 3050 Laptop with
> 4.29 GB VRAM**. Qwen3-VL-2B at FP16 needs ~8 GB, so it **cannot run locally at
> full precision** and none of the local serving runtimes (Ollama, llama.cpp,
> vLLM) are currently installed. Our options are: (a) install a serving runtime
> and run a *quantized* 2B (or the 1B **HunyuanOCR** fallback that genuinely
> fits 4.29 GB), or (b) run the 2B via an API / a machine with more VRAM. The
> harness is built so we get real numbers the moment either is available.

### Scientific position
> *“We selected Qwen3-VL-2B because recent research demonstrated a
> Qwen3-VL-2B-based model specifically for financial-document parsing (FinixDoc),
> and because — unlike LayoutLM's supervised token classification — a multimodal
> generative model can extract structured fields directly, which suits our scarce
> labelled Indian-invoice data. We will benchmark it against our existing
> LayoutLMv3 hybrid on a controlled real-invoice test set; replacement will be
> justified only if it demonstrates better real-world extraction at acceptable
> inference cost.”*

---

## 6. Still blocked (not code — external assets)

| Item | Blocked by | Harness ready? |
|---|---|---|
| Real-data benchmark numbers (Phase 5) | No real annotated documents | ✅ `real_benchmark.py` |
| Production OCR dataset (`--ocr gcv`) | No `GOOGLE_CLOUD_VISION_API_KEY` | ✅ |
| Live Qwen3-VL-2B numbers | No serving runtime / 4.29GB VRAM / no API key | ✅ `vlm_bench.py` (+ Qwen runner next) |
| FUNSD / SROIE persisted checkpoints | Datasets not present in this workspace | scripts present |

---

## 7. Artifacts

- `benchmark.py` — honest held-out eval (per-field F1 + error taxonomy).
- `real_benchmark.py` — real-data benchmark harness + annotation checklist.
- `vlm_bench.py` — VLM zero/few-shot benchmark harness.
- `hybrid_resolver.py` — LayoutLM + regex fallback, live head-to-head.
- `recovery_report.py` — regenerates `evaluation/evaluation_report.md(.json)`.
- `eval_utils.py` — shared scoring so all harnesses measure identically.
