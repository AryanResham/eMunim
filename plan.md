# eMunim — LayoutLM Extraction Recovery Plan

## The problem

The rest of the system is frozen and known-good:

```
Upload → OCR → Classification → LayoutLM extraction → Validation → Storage → Dashboard
```

Everything up to extraction works. The question this plan answers is **why LayoutLM extraction is failing and how we prove the fix** — without guessing.

The goal is not to pre-commit to "LayoutLM is dead." It is to produce evidence, one experiment at a time, and let that evidence decide between **fixing LayoutLM**, **replacing it with a local VLM**, or **running both in a hybrid**.

---

## Part 1 — The plan (as designed, phase by phase)

### Phase 0 — Freeze the rest of the project
Do NOT touch: OCR, classification, validation, React UI, FastAPI, database. Architecture stays exactly as designed.

### Phase 1 — Audit the LayoutLM pipeline
Determine whether the model is overfitting or whether the pipeline itself is broken before blaming either.

1. **Inspect the training data** — for 10–20 documents, verify the chain:
   ```
   image → OCR words → bounding boxes → ground-truth fields → BIO labels
   ```
   visually. E.g. `Invoice No: INV-1023` must map to `INV-1023 → B-INVOICE_NO`.
2. **Verify token↔label alignment** — check `OCR token → word ID → LayoutLM tokenizer → BIO label`. If this is wrong, no amount of training will fix it.
3. **Verify bounding boxes** — `[x0, y0, x1, y1]` normalized to LayoutLM's 0–1000 range (the PPT says this is part of the pipeline).
4. **Verify the label set** — the current plan lists `B-AMOUNT / B-DATE / B-VENDOR / B-INVOICE_NO / B-TAX / O`. Strongly consider distinguishing `VENDOR / GSTIN / INVOICE_NO / DATE / TAXABLE_AMOUNT / CGST / SGST / IGST / TOTAL` instead of one collapsed `TAX` class.

### Phase 2 — Establish a proper baseline
The displayed run (`119 train / 30 eval`, `epoch 0.45/5`, train loss `0.8234`, val loss `0.7891`) is not diagnostic. Train to completion. Record after **every epoch**: epoch, train loss, val loss, precision, recall, F1. Plot train vs val loss and train vs val F1.

Interpretation:
- Train F1 ↑↑ / Val F1 ↓ → **overfitting**
- Train F1 ↑ / Val F1 ↑ → **learning normally**
- Both poor → **data / label / OCR / training bug**, not classic overfitting

### Phase 3 — Build a proper synthetic dataset (1,000–10,000 invoices)
Each generated invoice ships with: image + OCR text + bounding boxes + perfect ground truth + BIO labels.

**Vary:** layout (vendor top-left / top-right / centered, GSTIN near header / footer, total right-aligned / bottom-center), content (vendors, GSTINs, invoice numbers, dates, amounts, tax rates, HSN codes, quantities, units), visual (fonts, sizes, spacing, table dims, invoice length, item count, logos, alignment).

**Noise (introduced later):** blur, rotation, compression, faded scans, shadows, slight skew.

Purpose: stop the model from memorizing one template.

### Phase 4 — Retrain LayoutLM
- **Experiment L1:** current dataset → LayoutLMv3
- **Experiment L2:** large diverse synthetic dataset → LayoutLMv3

If L2 dramatically improves, the problem was data, not the model.

### Phase 5 — Real-world benchmark (30–50 documents, separated from training)
| Document | Count |
|---|---|
| GST invoices | 15 |
| Purchase bills | 8 |
| Receipts | 8 |
| Utility bills | 5 |
| Credit/debit notes | 4 |
| **Total** | **40** |

Annotate: vendor, GSTIN, invoice number, date, taxable amount, CGST, SGST, IGST, total (+ line items if feasible: description, HSN/SAC, qty, rate, amount).

### Phase 6 — Test LayoutLM on real data
Get two numbers: **Synthetic Test F1** and **Real Test F1** (e.g. 91% vs 58%). The gap is evidence of **synthetic→real domain shift**.

Then classify errors: OCR error / wrong field / wrong token boundary / wrong layout association / missing field / table error / numerical error.

### Phase 7 — Give LayoutLM a fair chance: small real fine-tune
```
large synthetic → pretrained LayoutLMv3 → 30 real annotated docs → fine-tune → real test set
```
Test documents never touch training. If L2 (synthetic-only) = 58% and L3 (synthetic + small real) = 78%, **keep LayoutLM** — the issue was domain adaptation.

### Phase 8 — Only now introduce the local 2–2B VLM
Same real test set, unchanged. Run:
- V1 zero-shot
- V2 few-shot
- V3 + strict JSON schema
- V4 + validation/retry

Measure: precision, recall, F1, exact match, hallucination rate, inference time, memory usage. The project wants a *cheap local* model — measure that explicitly.

### Phase 9 — Compare (the final experimental table)
| Model | Training | Real F1 | Latency | Memory | Hallucination |
|---|---|---|---|---|---|
| LayoutLMv3 | Synthetic | X | X | X | X |
| LayoutLMv3 | Synthetic + real | X | X | X | X |
| Local VLM | Zero-shot | X | X | X | X |
| Local VLM | Few-shot | X | X | X | X |
| Local VLM | Prompt + validation | X | X | X | X |
| Hybrid | Both | X | X | X | X |

### Phase 10 — Build the hybrid if it wins
```
              Document
                 │
                 ▼
                OCR
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    LayoutLM            Local VLM
        │                 │
        └────────┬────────┘
                 ▼
          Field Resolver
                 │
                 ▼
           Rule Validation
                 │
        ┌────────┴────────┐
        ▼                 ▼
      Valid          Needs Review
        │                 │
        ▼                 ▼
   PostgreSQL          Human
```
Use each model where it is strongest: GSTIN → regex + validation; invoice no / vendor / date → LayoutLM or VLM(+date parser); tax → VLM + arithmetic; line items → spatial table parser; total → model + arithmetic.

### Phase 11 — Human corrections become training data
The UI already has review/correction. Save `document + OCR + prediction + correction` → future fine-tuning data → human-in-the-loop story.

### Phase 12 — Finish the non-ML product
Validation (already designed), PostgreSQL, dashboard, CSV/Excel export, the 4/5-step UI. The demo is a product, not just a benchmark.

### Timeline (×3 weeks)
- **Week 1:** dataset/label/alignment/bbox audit (D1–2), full baseline (D3), eval script + metrics (D4), synthetic dataset + retrain (D5–7)
- **Week 2:** 30–50 real docs + annotate (D8–9), eval on real (D10), failure analysis (D11), small real adaptation (D12), local VLM zero/few-shot (D13–14)
- **Week 3:** prompt engineering, JSON output, retry (D15–16), LayoutLM vs VLM (D17), hybrid (D18), FastAPI integration (D19), DB/dashboard/export (D20), testing + presentation (D21)

---

## Part 2 — Codebase audit findings (what the actual code already tells us)

> These come from reading `layoutLM model/*.py` and `backend/services/extractor/*` today. They are the *starting* answers to the Phase 1 audit — several are concrete bugs, not theory.

### 2.1 Token→label alignment has a real bug risk (Phase 1.2 is not optional)
Both `layoutLM_synthetic_data_training.py` and `layoutLM_synthetic_test.py` build word labels with `build_word_labels()` using **first-match-by-exact-string**:
```python
for i, w in enumerate(words):
    if not used[i] and w == text:   # wrong when the token text repeats
        labels[i] = label; used[i] = True; break
```
If the same token text appears more than once in a document (e.g. `DATE`, `TOTAL`, `AMOUNT`, an amount value that equals another field's text), **labels are assigned to the first occurrence, not the true occurrence**. There is no position/box matching at all. This is exactly the failure mode Phase 1.2 warns about, and it is present in the current pipeline.

### 2.2 The training label space is one giant merged model
All three training scripts use a single `LABEL_LIST` of **~80 BIO labels merging every field of all 6 doc types** into one model. SROIE data only ever labels `VENDOR_NAME / INVOICE_DATE / TOTAL_AMOUNT`, so most labels *never fire* during that fine-tune. The synthetic set labels far more. Implication: the eval loss (`0.7891`) is dominated by the `O` class and tells you almost nothing about extraction quality.

### 2.3 Production vs training token-space mismatch (biggest silent risk)
- **Training** uses exact ground-truth token boxes (`tokens/boxes` JSON from the synthetic generator).
- **Production** (`backend/services/extractor/layoutlm_extractor.py`) feeds **Google Cloud Vision OCR output** — which splits/merges tokens differently than the generator and carries noise.

Even a *perfect* synthetic model can therefore fail on real inference purely from tokenization mismatch, before any "layout generalization" issue. This is a domain-shift source that only shows up as "real F1 drops," and Phase 6 will misattribute it unless synthetic training uses OCR-style tokens.

### 2.4 The tracked metric is wrong for this task
`compute_metrics` in the synthetic training script reports **token accuracy only**. With `O` typically ~90–95% of tokens, a model that predicts all-`O` scores ~93% and looks "fine" while extracting nothing. The eval script already does the right thing (`seqeval` entity-level P/R/F1 in `layoutLM_synthetic_test.py`) — that metric must be the one tracked per-epoch, not token accuracy.

### 2.5 "Exact match" for numbers is fragile
`layoutLM_synthetic_test.py` compares fields with `normalize_text` but numbers like `₹11,800` vs `11800` vs `11,800.00` are compared as raw strings. Amount/date comparisons need normalization rules (strip ₹/commas, collapse trailing `.00`) or the benchmark under-reports recall on the real set. This will matter badly in Phase 6.

### 2.6 Bounding-box math is consistent — one thing that is actually fine
Training (`normalize_box_1000`) and production (`_normalize_bbox` in `layoutlm_extractor.py`) both normalize to 0–1000. So box normalization is **not** the suspected bug; the audit should tick that off quickly.

### 2.7 Provenance of the production "indian" model is unrecorded
`/api/extract` serves `layoutlm-indian-invoice-trained` + `layoutlm-synthetic-trained`, but the repo holds no training script for the "indian" checkpoint (only SROIE / FUNSD / synthetic scripts). Part of the audit is to pin down *what actually trained the model that's serving production* — it may be the SROIE fine-tune under a different name.

---

## Part 3 — Recommended refinements to the plan

1. **Synthetic data must be generated through the production OCR engine.** Render the invoice → run **Google Cloud Vision** (same call as production, `backend/services/ocr_service.py`) → use *its* words + boxes → project ground truth onto those tokens (by box proximity, not first-string-match). This kills the 2.3 token gap before it exists and makes "synthetic F1" actually predictive of real F1.
2. **Fix label alignment with boxes.** Replace first-match-by-string with nearest-box assignment (match GT boxes to OCR boxes by IoU/overlap). Keep a per-doc "alignment quality" counter in the dataset so you *know* when alignment fails instead of silently training on wrong labels.
3. **Track entity-level seqeval F1 per epoch**, plus a small O-vs-entity confusion report. Drop token accuracy as the metric.
4. **Decide the label-set question first (Phase 1.4), then freeze it for all experiments.** The merged ~80-label space is workable but hard; at minimum confirm it during Phase 1 and add a *per-doc-type model* as an optional Experiment L0 to measure whether the merged space itself is hurting (it likely is).
5. **Normalize amounts/dates before exact-match eval** (₹, commas, `.00`, `12/08/2026` vs `12-Aug-2026`), and report per-field F1 + confusion (the field-level table in Phase 9 stays, but rows should be per-field).
6. **Run the Phase 2 "complete baseline" as the audit's deliverable** — finish the interrupted 5-epoch run, but with item-3's metric attached so the loss curves are actually interpretable.

---

## Part 4 — Is this the right approach? (Assessment)

**Overall verdict: yes, this is fundamentally the correct methodology**, and it is better than the common alternatives (rip out LayoutLM and pray a VLM works, or re-run the same training ad infinitum). It is a proper diagnosis-first ML workflow:

- It isolates **pipeline bugs** from **data problems** from **model limitations** (Phases 1–2) — which is precisely where your numbers sit right now.
- It tests the **cheapest hypothesis first** (avoidable: alignment bug + tiny data + bad metric) before spending on the expensive one (VLM infra).
- It gives LayoutLM a **fair, documented** chance via domain adaptation (Phase 7) before switching, which makes the eventual decision defensible to a reviewer/mentor.
- It introduces the VLM **last**, on a **fixed, unchanged real test set** (Phase 8), so the comparison is apples-to-apples — this is the part most student projects get wrong.
- It plans for the **hybrid + human-in-the-loop flywheel** (Phases 10–11), which is both the most likely winner and the strongest engineering story for the demo.

**Where the approach is weakest (and what I'd change):**

1. **It slightly over-weights "more data" and under-weights "train like you infer."** The single most probable explanation for the `0.79` val loss + poor demo is *not* insufficient data but the token/label alignment bug (2.1) and train-vs-inference token mismatch (2.3). Fix those before/bundled with the synthetic push, or you'll generate 10,000 near-perfect synthetic invoices and still fail on the first real scan — and Phase 6 will misdiagnose it as "domain shift."
2. **The 3-week timeline assumes the GPU/compute and the 40 real documents already exist.** Budget Week-2 start as the hard dependency for the real benchmark; the synthetic/VLM legs can run in parallel once the audit passes.
3. **The "1,000–10,000 synthetic invoices" is the right order of magnitude but wrong goal.** The diversity axes (layout/content/visual/noise) matter more than raw count. A deliberately diverse 1,500–3,000 with production-OCR tokens will beat 8,000 from one template family.
4. **The hybrid (Phase 10) should be green-lit earlier, not as a tie-breaker.** You already merge the `indian` + `synthetic` LayoutLM outputs in `extract.py`; the VLM is a third head in that same merge + a file resolver. The marginal engineering cost is low, and "use the right tool per field + deterministic validation" is the most demo-able story you have.

**One-line answer to "is this correct?":** Yes — it's the method I'd run, with three amendments: (a) fix token↔label alignment and train on production-OCR tokens before scaling synthetic data, (b) measure entity-level F1 per epoch, not token accuracy, (c) treat the hybrid as the expected outcome, not a fallback.

---

## Decision tree (unchanged — it is correct)

```
            LayoutLM failing
                 │
                 ▼
          Check training pipeline
                 │
        ┌─────────┴─────────┐
        │                   │
     Pipeline bad        Pipeline OK
        │                   │
        ▼                   ▼
       FIX             More synthetic data
                             │
                             ▼
                    Synthetic performance?
                        │              │
                      GOOD            BAD
                        │              │
                        ▼              ▼
                    Test real        Fix training
                        │
                        ▼
                  Real performance?
                    │          │
                  GOOD        BAD
                    │          │
                    ▼          ▼
               KEEP MODEL    Small real
                            fine-tuning
                                │
                                ▼
                          Improvement?
                          │          │
                         YES         NO
                          │           │
                          ▼           ▼
                     KEEP LayoutLM    VLM
                                      │
                                      ▼
                            Better on real data?
                              │           │
                             YES          NO
                              │            │
                              ▼            ▼
                           VLM /         LayoutLM
                           Hybrid         + fix
```

## Closing justification templates (pick when you have the data)

- **LayoutLM fixed:** *"We retained LayoutLMv3 because domain adaptation with synthetic and limited real data restored satisfactory extraction performance."*
- **LayoutLM replaced:** *"Despite correcting the training pipeline and increasing synthetic-data diversity, LayoutLMv3 showed substantial degradation on real-world documents. A locally deployed VLM demonstrated superior generalization on the same real-document benchmark, motivating its adoption."*
- **Hybrid wins (preferred):** *"Neither model was universally superior. LayoutLMv3 was effective for structured token-level extraction, while the local VLM handled layout and semantic variation better. Therefore, we combined both with deterministic accounting validation."*

The next milestone is not a decision — it is **proof of why LayoutLM is failing**. Everything after that decision becomes obvious.