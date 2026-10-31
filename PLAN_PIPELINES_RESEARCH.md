# eMunim: pipeline comparison, extraction reliability, and assisted review plan

Updated: 2026-10-24
Status: integrated local application; measured pilot completed with provider failures.

Implementation update (2026-10-24): the three extraction pipelines, validation/
review, edit/confirm/save workflow, SQLite records/search/CSV, and a read-only
Research results page are implemented. CUDA training completed in the required
order: base -> FUNSD -> SROIE -> six separate synthetic document-type models.
Checkpoint identities, parent hashes and training logs are retained under
`layoutLM__model`. The measured suite runs public checkpoint tests, synthetic
checkpoint tests, and a bounded live OCR/hosted comparison; use the saved run
status rather than interpreting this plan as a claim of successful completion.

Evidence limits: there are 34 real-document annotation drafts and zero verified
real annotations. Real Indian MSME accuracy, human correction time and actual
billing are not established. DATABASE_URL is absent; the local application uses
SQLite and PostgreSQL has not been tested. An exact-image audit found nine
cross-split pairs in the pinned SROIE mirror: seven test images matching training
or development were excluded before test inference, leaving 340 test receipts.
Two historical train/development duplicate pairs remain a model-selection
limitation. The audit does not establish freedom from near-duplicates.

Read `research/METRICS.md` for definitions and each run's `report.md`, raw outputs,
protocol, manifests and failure logs for evidence. Generated-data results are a
pilot and must not support claims of real Indian MSME generalization. The
checklists below describe the full study, including work that remains pending.

Measured update: `paper-20261024-r2` finished all 1,290 checkpoint test documents
and 36 live test documents (six per type). Full-cohort field F1 was 0.778146
(P1), 0.796875 (P2), and 0.880131 (P3). P2 had 12 rate-limit failures and P3 had
12 degraded runs, all in the later credit/debit-note cases; availability and
type/order are confounded. These primary scores are not a clean model-quality
ranking. The conditional common-success subset has 24 documents across four
types, with F1 0.830097/0.980769/0.978417. P3 routed 100% of documents and showed
no logical hosted-call savings at its development-selected threshold. The full
study still needs verified real data, adequate hosted quota and the missing
measurements listed above. See `research/VERIFICATION_20261024.md`.

## 1. Agreed project and paper direction

Keep the original project: AI-based MSME accounting workflow automation. Complete its manual-upload workflow and evaluate both (1) local, hosted, and selective hybrid extraction pipelines and (2) the contribution of validation and selective human review to their reliability.

Working paper title:

**Comparing Local, Hosted, and Selective Hybrid Pipelines for Reliable Indian GST Invoice Processing**

Main research question:

> Which pipeline provides the best tradeoff between extraction accuracy, undetected errors, human-review workload, processing time, and external API usage for Indian GST invoices?

Supporting questions:

- Can selective hosted assistance reduce hosted-model calls while retaining extraction quality close to hosted-only inference?
- When does each pipeline fail, and does the hybrid's additional complexity provide a measurable benefit?
- Which extraction errors do rules detect, and which remain undetected?
- Does uncertainty-based review detect additional errors beyond rules alone?
- How does accepted-output reliability change as review workload changes?
- If a controlled user study is feasible, does assisted review reduce correction time relative to manual entry while preserving final record accuracy?

The contribution is a controlled comparison of complete extraction pipelines together with evidence about validation and review workload. Combining existing models and rules is not, by itself, a novelty claim. Do not assume the hybrid wins: hosted-only may prove the best practical choice. Free-tier access is an experimental allowance, not proof of zero deployment cost.

Both pipeline comparison and reliability are core, agreed parts of this paper. The hosted adapter and selective fallback are required for the complete three-pipeline study; local LayoutLM work can proceed without credentials while they are configured. Synthetic data supports training; diversity/noise experiments remain secondary.

## 2. Latest presentation: evidence to reconcile

Primary reference: `LY_artifacts/LY Project Presentation.pdf` (17 slides), supported by the mentor report, demo explanation, literature review, and earlier presentations.

| Evidence | Next action |
| --- | --- |
| Slide 14: domain mismatch, OCR noise, unseen layouts | Evaluate these failure types on verified real Indian invoices. |
| Slide 15: preliminary extraction/classification scores | Reproduce using checkpoint identities, dataset manifests, predictions, and exact metric definitions. |
| Slide 15: 95.38% average OCR word confidence | Report as confidence, not OCR accuracy. CER/WER requires verified transcription. |
| Slide 15: synthetic F1 of 65.76% and stronger SROIE scores | Audit different tasks/metrics; do not subtract unlike metrics to quantify a domain gap. |
| Slide 3: 40 annotated Indian invoices; slide 10: approximately 500 planned | Verify what actually exists. Planned counts are not collected data. |
| Slides 8/13/14/17: conflicting training/integration status | Reconcile against loadable checkpoints and actual inference paths. |
| Slide 17: user review before database commit | Implement effective edits, validation reruns, persistence, and audit history. |

Initial research scope: single-page English GST invoices, header fields and totals. Keep six existing document types available in the product, but extend paper claims only after separate labelled evaluation. Handwriting, multilingual processing, ERP sync, bank reconciliation, forecasting and full journal posting remain future scope.

Separate these tasks:

1. Document-type classification: invoice, receipt, utility bill, etc.; implemented by the current regex/DeBERTa cascade.
2. Field extraction: invoice number/date, vendor, GSTINs, amounts; the extraction task evaluated here.
3. Accounting-head assignment: expense/revenue categories and chart-of-accounts codes; not established by the current document classifier.

Use known document type in the initial research runner to isolate extraction/review. Evaluate classifier accuracy separately. Line-item extraction is also separate; do not assume heuristic table output is correct.

## 3. Main experiment: three pipelines plus reliability ablations

### Primary pipeline comparison

| ID | Pipeline | Extraction flow | Common final stage |
| --- | --- | --- | --- |
| P1: `ocr_layoutlm` | Local learned extraction | Normalized image -> Google Vision OCR -> one per-type LayoutLMv3 checkpoint | Same consistency rules -> review/confirmation |
| P2: `hosted_vlm` | Hosted extraction | Same normalized image + known type/schema -> one hosted vision-language model; no external OCR transcript | Same consistency rules -> review/confirmation |
| P3: `layoutlm_hosted_fallback` | Selective hybrid | Same OCR and LayoutLM as P1 -> development-frozen routing gate -> hosted assistance only for routed documents -> deterministic resolution or unresolved conflict | Same consistency rules -> review/confirmation |

P1 is local **extraction**, not an offline system: its Google Vision OCR is external. P2 and P3 must use the same hosted provider/model version. All pipelines receive the same image bytes, target schema, known document type and held-out documents; P1/P3 share OCR/cache and checkpoint. P2 must operate without OCR credentials or local model assets.

No regex repair or merged synthetic second head is included in the primary P1 baseline. A cheap OCR + spatial-rules baseline may be added separately. Different pipeline outputs may have different raw accuracy; compare them without assuming a winner.

P3 is an extraction intervention and may change values. Retain its pre-fallback LayoutLM output, hosted candidates, selected final fields, reasons, unresolved conflicts and usage. Measure both its accuracy change and external calls. Routing to a hosted model and routing to a human are different decisions and must have separate policies and counters.

### Supporting reliability ablations

Apply these policies to each pipeline's **frozen final automatic extraction output**, without rerunning models or changing values:

| ID | Configuration | Purpose |
| --- | --- | --- |
| A: `extraction_only` | No automated error detector; no-review acceptance is an offline simulation only | Raw extraction quality and baseline error exposure |
| B: `validation_review` | Common versioned rules flag implicated fields/documents | Error detection from consistency rules alone |
| C: `validation_confidence_review` | B flags plus a development-calibrated uncertainty policy | Incremental detection versus additional review |

**Flagging is not correction.** Within a pipeline, applying A/B/C does not change raw extraction F1. Between P1/P2/P3, F1 can change because the extractors differ and P3 can invoke hosted extraction. Human corrections are scored separately from automatic outputs.

Primary cross-pipeline reliability comparison uses the same validation-only B policy; do not assign a hosted confidence merely to force symmetry. Apply C to P1 and to fields in P3 that retain meaningful LayoutLM confidence. For hosted-generated or unresolved fields, use an explicit source/provenance/review policy rather than copied LayoutLM confidence. A full cross-pipeline C comparison requires a justified measurable uncertainty signal available for each extractor; otherwise report C as a supported-source ablation and disclose its scope.

Report pipeline-by-policy combinations separately, with validation-only B as the common comparison. Pipeline-specific applicability may cause different rules to fail, but the rule definitions/tolerances are shared. A is never a production bypass; record user confirmation before saving reviewed records.

Optional extensions: hosted image + OCR ablation, OCR + spatial-rules baseline, synthetic diversity/noise, and a controlled review-time study.

## 4. Phase 0: audit scores, datasets, and checkpoints — first priority

- [ ] Inventory real documents, annotations, OCR outputs, synthetic datasets, checkpoints, and evaluation artifacts.
- [ ] Deduplicate real invoices; identify type, vendor/template group, readability, and permitted research use. The previously listed 34 screenshots are a starting inventory, not a verified final sample count.
- [ ] Locate the claimed 40 annotations. If absent, record the gap and create annotations; the slide is not proof that they exist.
- [ ] For each slide-15 score, record sample size, split, task, metric definition, OCR source, preprocessing, checkpoint, and scoring code. Reproduce where assets exist; otherwise label not reproducible from available assets.
- [ ] Check classification label distributions and L1/L2 denominators, including whether L2 was tested on real L1-rejected cases. An isolated 100% result is not end-to-end accuracy.
- [ ] Hash loadable weight/config/tokenizer/processor files; record actual training lineage. Do not infer persisted FUNSD/SROIE transfer stages from narrative reports.
- [ ] Preserve historical results with their original definitions; do not overwrite them with differently scored new runs.

Proposed deliverables: `research/inventory.md`, `research/baselines/reproduction_manifest.json`, `research/checkpoints.json`.

Completion: actual usable counts are known and every quoted historical score has reproducible evidence or an explicit evidence gap.

## 5. Phase 1: verified real benchmark and annotation contract

- [ ] Freeze fields: invoice number/date, vendor name/GSTIN, buyer GSTIN, taxable amount, CGST, SGST, IGST, total.
- [ ] Define unconditional, conditional and optional applicability. A schema key is not necessarily a mandatory printed field. Distinguish absent, unreadable, invalid, and numeric zero.
- [ ] Store verified raw field strings, optional evidence boxes, source ID, vendor/template group, type and readability metadata. Model/API predictions are not ground truth without manual verification.
- [ ] Write an annotation guide, independently review a subset, and resolve disagreements before scoring.
- [ ] Freeze normalization for dates, amounts, GSTIN case and identifiers; preserve meaningful signs/punctuation and original strings alongside normalized values.
- [ ] Keep duplicates, augmented copies and shared vendor/template groups within a single split. Freeze development/test groups before rule/prompt/threshold tuning or real-data adaptation.
- [ ] If insufficient independent documents remain, collect more or present a pilot study with actual counts and limitations. Do not promise an arbitrary minimum guarantees generalization.
- [ ] Check whether existing real examples already informed training/rules. Disclose prior exposure and obtain fresh held-out examples where needed.
- [ ] Cache production OCR by normalized-image hash and OCR/preprocessing version. Create a verified transcription subset only if measuring OCR CER/WER.

Proposed deliverables: `research/annotation_guide.md`, annotation schema/examples, annotation validator, immutable dataset/split manifest.

Completion: verified independent development/test groups exist and final labels are excluded from method tuning. Keep identifiable document content out of commits by default.

## 6. Phase 2: dependable, auditable LayoutLM extraction

Files: `backend/services/extractor/layoutlm_extractor.py`, `field_mapper.py`, `pipeline.py`, `backend/models/schemas.py`, `backend/routers/extract.py`, `backend/config.py`.

- [ ] Add primary engine ID `ocr_layoutlm`. Keep extractor IDs separate from A/B/C review-policy IDs in contracts and manifests.
- [ ] Use one per-type checkpoint. Disable the legacy merged synthetic second head for core research and audit trained-label/production-schema differences.
- [ ] Separate pure model inference from regex fallback. Missing/unloadable weights yield explicit unavailability, never mislabeled regex success.
- [ ] Retain low-confidence candidates rather than discard them before review. Define/freeze token-to-field confidence aggregation; missing fields remain missing.
- [ ] Verify OCR word/box alignment, normalized coordinates, BIO aggregation, label IDs, and 512-token truncation. Record truncated/unseen content; resolve material preprocessing bugs before freezing runs.
- [ ] Emit exactly one canonical value per field with nullable status, available confidence, source/checkpoint, OCR/preprocessing version, timing, errors and provenance.
- [ ] Prevent duplicate keys from legacy merging and synthetic-prefixed fields overwriting primary values during validation.
- [ ] Ensure the new default never loads/downloads local Qwen weights; local VLM imports/dependencies must not block LayoutLM-only operation.
- [ ] Require usable OCR. Align frontend JPEG/PNG acceptance with backend; bounded upload size/type checks and useful errors are required. PDF/multipage handling is separate follow-up scope.

Completion: extraction works without a hosted key or local VLM; unavailable assets fail visibly; raw predictions and uncertainty/provenance survive end to end.

## 7. Phase 3: validation and uncertainty-assisted review

Files: `backend/services/validator/`, `backend/utils/confidence_config.py`, `backend/models/schemas.py`, `backend/routers/validate.py`; proposed new `backend/services/review/review_policy.py`.

- [ ] Version rules, applicability and tolerances: field completeness, GSTIN format/checksum, date parsing, amount parsing, and arithmetic where supporting fields exist.
- [ ] Audit inherited presentation assumptions before coding. In particular, do not adopt `CGST + SGST = IGST` as a universal check. Verify relevant domain assumptions independently; describe these as consistency checks, not comprehensive tax certification.
- [ ] Distinguish pass, fail, not applicable, and insufficient evidence. A skipped check does not establish correctness. Missing/invalid values cannot silently become zero.
- [ ] Return implicated fields/groups and readable reasons. A failed total equation may identify several suspect amounts without revealing which is wrong; score field and document attribution separately.
- [ ] B uses rules alone; C adds uncertainty flags derived from the same pipeline output where a defensible uncertainty signal exists. Use B as the common cross-pipeline reliability comparator and label any source-limited C ablation.
- [ ] Tune threshold/aggregation policy on development data using an explicit detection-versus-review objective; freeze a versioned policy artifact before final testing.
- [ ] Treat existing synthetic tau=0.50 as a candidate, not a real-data-calibrated operating point. Raw softmax confidence is not automatically a calibrated probability of correctness.
- [ ] Never choose the final threshold retrospectively from test labels. Report curves as sensitivity analysis with the preselected operating point identified.
- [ ] Empty output, inference failures and invalid OCR require review and remain visible in operational failure statistics and document denominators.
- [ ] Audit current always-pass duplicate stub. Implement real duplicate detection after persistence and evaluate separately using defined duplicate/nonduplicate cases.
- [ ] Do not change values inside A/B/C. P3's hosted extraction/resolution happens before these review ablations and preserves before/after predictions. Any additional regex repair is a separately named intervention.

Completion: B/C flag without mutating fields; optional absence does not cause false mandatory-field failures; every decision is reproducible.

## 8. Phase 4: effective review in the application

Files: `Frontend/src/types/upload.ts`, `src/api/backend.ts`, `components/upload/UploadWorkflow.tsx`, steps 1–4, `OcrDebugViewer.tsx`, and backend validation contracts.

- [ ] Offer P1/P2/P3 explicitly, selected before processing; keep extraction-engine choice separate from review configuration. P2 skips external OCR and uses manual type selection; P1/P3 retain OCR/classification/manual override. Remove local-VLM dependence from the normal workflow.
- [ ] Preserve document-type classification/manual override; do not present category chips as learned chart-of-accounts assignment.
- [ ] Show source image, values, provenance, rule flags, available uncertainty, hosted-fallback reasons and API activity; distinguish empty/loading/failure states and unavailable providers. Null hosted confidence is not zero confidence.
- [ ] Lift edits into workflow state, label human corrections, rerun validation, and retain original model values/confidence separately.
- [ ] Remove production fallback to mock validation; API failure remains a visible failure/unresolved review state.
- [ ] Centralize requests via `/api` plus Vite proxy or public `VITE_API_URL`; check upload status before reading IDs. Preserve fields, line items and metadata in state.
- [ ] Distinguish auto-eligible, user-confirmed, corrected and unresolved records. Show submission success only after a successful durable save.
- [ ] If running a timing study, record review actions/timing under an explicit protocol; define idle-time handling and measurement limitations.

Completion: edits affect validation and saved values, errors cannot become success, and original predictions/user corrections remain traceable.

## 9. Phase 5: complete the promised manual-upload product

Files: `backend/routers/upload.py`, `documents.py`, new storage/repository/schema/migration files, frontend records/dashboard/export views.

- [ ] Implement PostgreSQL persistence with migrations and local setup to match the presentation. SQLite may be an explicitly labelled development option; it does not demonstrate PostgreSQL integration.
- [ ] Persist upload metadata and locate files after restart instead of relying exclusively on `FILE_STORE`; root storage paths consistently.
- [ ] Save original/final/corrected fields, pipeline ID, fallback candidates and decisions, provider/model/checkpoint identities, prompt/schema/routing/review-policy versions, usage, validation, category, timestamps and audit history.
- [ ] Implement save/list/detail APIs and saved-record views with filters. Revalidate on the server at submission rather than trust client success flags.
- [ ] Implement basic counts/category/verified-amount summaries and CSV export from durable records.
- [ ] Do not infer profit, cash flow, receivables/payables or GL postings from document type alone; show only summaries supported by stored semantics.
- [ ] Add defined exact duplicate checks; keep duplicate-policy evaluation separate from extraction-error detection.
- [ ] Keep ERP sync, learned accounting-head assignment, forecasting and journal posting explicitly future scope until implemented/evaluated.

Completion: records survive reload/restart; dashboard/export reflect saved corrected values; save/database failures are visible. Product completion is separate from evidence for research claims.

## 10. Phase 6: reproducible evaluation and paper artifacts

Maintain new evaluation code under `research/`, outside `layoutLM__model/`. Reuse audited scoring code, excluding ground-truth-dependent resolver logic or mocked metrics as real evidence. Training code and trained artifacts remain in `layoutLM__model/`.

- [ ] Run P1/P2/P3 on identical held-out documents; freeze/cache raw outputs per pipeline and replay supported A/B/C review ablations without changing those outputs.
- [ ] Reuse P1's LayoutLM predictions as P3's first-stage input when computing offline decisions; independently measure actual P3 end-to-end latency. Separate cached hosted replay from live provider runs.
- [ ] Run a full-cohort hosted-only P2 reference, not just the subset P3 routes. Cache request artifacts to avoid unnecessary duplicate calls while keeping prompt/input differences explicit.
- [ ] Freeze both fallback routing and human-review policies on development data. A fixed 50% model threshold or missing optional field is not a defensible routing policy by itself.
- [ ] Record commit/working-tree patch identity, dataset/split hashes, checkpoint hash, provider/model identity, prompt and generation settings, OCR/cache version, schema/normalization/rule/routing/review-policy versions, thresholds, dependencies, hardware and timestamps.
- [ ] Define errors before scoring: missing applicable value, wrong value, extra value for an absent field. Declare treatment of unreadable/ambiguous annotations.
- [ ] Report raw per-field precision/recall/F1 and averaging definitions, complete-document accuracy, operational failure rates, field applicability/sample counts and error examples.
- [ ] Score field-level and document-level error detection; a document is reviewed if any relevant flag exists. Report group-level rule attribution honestly.
- [ ] Report silent errors among all documents, errors among accepted documents, review rate, acceptance coverage and unnecessary review with explicit denominators.
- [ ] Report C's newly detected errors and additional correct documents reviewed relative to B.
- [ ] Plot accepted-output error versus coverage/review workload for the pipeline-policy combinations with comparable signals. Identify frozen development-selected operating points; raw F1 does not change merely from flagging.
- [ ] Plot extraction quality versus hosted-call fraction for P3 routing thresholds, identifying the development-selected point. Compare paired document-level quality against P2; do not choose a preferred threshold from test results. If claiming near-equivalence, predefine the acceptable margin and report uncertainty; small samples may not support that claim.
- [ ] Report P3's positive and negative corrections, resolved/unresolved conflicts, and calls caused by absent/conditional fields. Explain when hybrid complexity fails to pay off.
- [ ] Use paired document-level comparisons and bootstrap intervals where appropriate; do not treat correlated fields or augmented copies as independent documents.
- [ ] Stratify by template novelty, OCR quality, applicability and error type where sample counts permit; show wrong-but-consistent and confidently wrong cases.
- [ ] Report median/p95 latency and local peak memory with sample counts; distinguish cold/warm model loads, cached OCR and fresh end-to-end runs.
- [ ] Report logical hosted calls, physical attempts/retries, tokens, fallback rate, failure rate and actual account cost per document. Include failed calls in denominators and distinguish free-tier allowance from model list-price estimates using dated rates.
- [ ] Cost accounting: P1 = OCR + local extraction; P2 = hosted image extraction; P3 = OCR + local extraction + actual hosted attempts on routed documents. Account for OCR logical usage even when shared caches avoid repeated experimental charges. Keep local training and human work separate.
- [ ] Keep synthetic versus real scores and exact-text versus production-OCR scores separate; do not claim provider server memory measurements.
- [ ] Generate paper tables/plots from saved predictions and decisions without new inference. Never mix manual corrections with automatic extraction success.

Document-level definitions, for N documents, E incorrect raw documents, R flagged documents, and U = N − R accepted documents:

| Metric | Definition |
| --- | --- |
| Review rate | R / N |
| Acceptance coverage | U / N |
| Detection precision | Incorrect documents flagged / R |
| Detection recall | Incorrect documents flagged / E |
| Silent-error rate over all documents | Incorrect documents accepted / N |
| Accepted-document error rate | Incorrect documents accepted / U |
| Unnecessary-review rate over correct documents | Correct documents flagged / correct documents |

Report zero-denominator metrics as undefined: accepting nothing does not establish 100% accepted accuracy. Include inference failures consistently and disclose denominators. Report present-field and absent-field behavior separately so trivial true negatives do not obscure extraction quality.

Completion: saved outputs plus a frozen run manifest regenerate core tables, curves and limitations without test-driven tuning.

## 11. Required hosted adapter and selective hybrid implementation

Implement after the dependable P1 path and shared validation contracts exist, before final cross-pipeline evaluation. Proposed files: `backend/services/extractor/hosted_vlm.py`, `providers/base.py`, `providers/groq.py`, `routing_policy.py`, and `candidate_resolver.py`; update pipeline/router/schema/config/frontend contracts. These paths are proposed, not existing implementations.

### Hosted extraction (P2)

Use one hosted image-capable model. Groq's free-tier vision offering is the initial candidate reflecting the user's preference; verify current access, image support, quota, output capabilities, model ID and applicable data terms before implementation. No permanent free/unlimited-access promise. Use the same selected provider/model in P2/P3; additional providers are optional.

- [ ] Pilot on development documents before freezing the model/prompt/schema and tested SDK/dependency versions.
- [ ] Accept image/type/schema independently of OCR/LayoutLM assets. No predictions, ground truth or external OCR transcript in P2's primary prompt.
- [ ] Use structured output where available and Pydantic validation; JSON mode alone does not ensure schema correctness or factual accuracy. Preserve null absent fields and reject malformed response types.
- [ ] Record provider/model, prompt/schema versions, generation settings, request IDs, usage, latency and typed failures. Do not fabricate a fixed confidence percentage.
- [ ] Bound total attempts including automatic SDK retries; distinguish authentication, rate/quota, transient, refusal, truncation and parsing failures. Do not retry invalid credentials repeatedly.
- [ ] Enforce run-level call caps and resumable evaluation. Cache by image/model/prompt/schema/input/settings hash and disclose cached versus live timing. Do not switch model/provider silently if the free quota is exhausted.
- [ ] Provider unavailability must yield explicit errors/review state; no mock output masquerades as a model result.

### Selective fallback and resolution (P3)

- [ ] Use precisely P1's OCR, checkpoint and retained candidates. Route on development-calibrated uncertainty, missing unconditional core fields, evidenced conditional fields, or actual consistency failures.
- [ ] Distinguish absent optional fields from failed extraction; optional absence alone must not invoke cloud inference.
- [ ] Initially make one logical hosted call per routed document, with bounded physical retries. Pass image, same field schema and target field names; omit previous candidate values and OCR text initially to reduce anchoring. Any OCR-context variant is a separate ablation.
- [ ] Define a deterministic resolver using source evidence, validation and conflict handling. Do not prefer a hosted value merely because it exists, or use uncalibrated confidence to compare engines.
- [ ] Emit one final value per key plus candidate history. Preserve high-confidence values unless the frozen conflict policy provides contrary evidence; unresolved conflicts are review-required.
- [ ] A hosted value missing from OCR can still be correct; OCR matching is supporting evidence, not an absolute veto. Arithmetic consistency alone does not prove correctness.
- [ ] Revalidate final merged output. Mark source per field; a hosted replacement cannot inherit the discarded LayoutLM score.
- [ ] On hosted failure, retain available LayoutLM output as degraded/review-required, log fallback failure and count the run as such. Do not silently substitute P1 success for P3 success.
- [ ] Version fallback routing and human-review policies separately and calibrate each on development data. Final B/C analyses operate after the fixed P3 extraction/resolution output.

Completion: P2 works without OCR/local model assets; confident eligible P3 documents make zero hosted calls; routed cases are bounded and traceable; errors/conflicts remain visible; both pipelines use no local VLM.

## 11a. Optional extensions

### Synthetic training ablation

After validating labels/generator and establishing the real benchmark, optionally compare fixed layouts, diverse layouts, and diverse layouts plus realistic noise. Match dataset sizes, checkpoint initialization and training budgets; use multiple seeds if feasible. For OCR-noise experiments, run OCR on degraded images rather than retain perfect text after visual degradation. Do not train/adapt on the final real test set.

### Controlled correction-time study

Compare manual entry and assisted review only with a predefined protocol. Counterbalance order or use matched disjoint invoice sets to avoid repeated-document memory effects; report participant experience, tasks, timing and final accuracy. Without this experiment, review rate and correction counts are proxies, not measured time savings.

## 12. Credentials and proposed configuration

| Requirement | Required use |
| --- | --- |
| `GOOGLE_CLOUD_VISION_API_KEY` | Fresh OCR for P1/P3; Vision API enabled with applicable billing/quota. Cached replay needs no new call. P2 image-only does not require it. |
| Local LayoutLM assets | Audited weights/config/processor/tokenizer for P1/P3; no local inference key. |
| Verified real annotations | All accuracy and reliability experiments, including hosted output. |
| `DATABASE_URL` | Product PostgreSQL credentials; not an AI API key. |
| `GROQ_API_KEY` | P2/P3 if Groq selected; required for the full comparison, not for P1-only development. Its existing declaration does not mean integration exists. |
| Local Qwen assets, Gemini/OpenAI keys | Not required. Other hosted provider keys only if that provider is chosen instead. |

Keep keys in backend `.env`/server secrets, never frontend `VITE_*`, commits, logs or paper artifacts. Do not paste keys into chat. No actual secret-file inspection is needed for planning.

Proposed settings; new variables require implementation:

```dotenv
GOOGLE_CLOUD_VISION_API_KEY=<your-cloud-vision-key>
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/emunim
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:5174"]
EXTRACTION_DEFAULT_PIPELINE=ocr_layoutlm
REVIEW_POLICY=validation_confidence_review
REVIEW_POLICY_PATH=research/policies/<frozen-development-policy>.json

# Required for P2/P3 if Groq is the selected provider:
GROQ_API_KEY=<your-groq-key>
HOSTED_VLM_PROVIDER=groq
HOSTED_VLM_MODEL=<verified-image-capable-model-id>
HOSTED_VLM_MAX_ATTEMPTS=2
HOSTED_VLM_MAX_CALLS_PER_DOCUMENT=2
HOSTED_VLM_TIMEOUT_SECONDS=60
FALLBACK_POLICY_PATH=research/policies/<frozen-development-routing-policy>.json
```

Fix the existing comma-separated `ALLOWED_ORIGINS` example to match its list-valued parser. Select fallback and review thresholds separately on development data and store policy artifacts. Timeout/attempt settings are provisional; count SDK retries inside the total cap. Confirm a run-level call budget before live experiments; free-tier quotas can still prevent completion.

Setup references to recheck at implementation:

- [Google Vision setup](https://docs.cloud.google.com/vision/docs/setup)
- [Groq vision](https://console.groq.com/docs/vision)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)

## 13. Meaningful validation checks

- Pure LayoutLM makes no hosted/local-VLM call; unavailable weights cannot masquerade as regex inference.
- Within each pipeline, A/B/C retain identical raw values/F1; review policies do not mutate fields. P3's upstream correction may change accuracy relative to P1 and must preserve the history.
- P2 requires neither OCR nor LayoutLM; P1 works without a hosted key. P2/P3 use the same hosted model/version.
- Confident P3 cases skip hosted calls; absent optional fields do not trigger calls; routed cases obey attempt caps.
- Hosted timeout/quota/parse errors produce explicit failure/review metadata, never fabricated success; conflicting candidates never create duplicate keys.
- Hosted replacements have correct provenance and do not inherit LayoutLM confidence. Pipeline/engine selection and review-policy selection remain distinct.
- Missing, invalid, zero and conditional absence differ; not-applicable checks remain explicit.
- Failed rules identify relevant fields/groups; a passed equation cannot certify all fields correct.
- C includes B flags; threshold/policy comes from frozen development data.
- Wrong-but-consistent and confidently wrong fixtures expose method limitations.
- Empty output and operational failures remain visible/review-required; mock validation success is absent.
- Human edits rerun validation, preserve originals, and survive save/restart.
- Scoring covers all-accepted, all-reviewed, no-error and undefined-denominator cases.
- Run relevant backend tests and frontend type/build checks after implementation. Ordinary tests incur no live API charges; live smoke tests are separate and explicitly configured.

## 14. Execution order and paper completion

Implementation update (2026-10-16): `research/annotate.py` provides local
image import, manual field review and verified-only manifest export with
vendor/template split checks. `research/ocr_inputs.py` prepares bounded
Google OCR and manually corrected OCR inputs; `research/run.py --ocr-variant`
and `research/compare_ocr.py` support matched OCR diagnosis. See research/README.md
for commands. Dataset verification, development calibration, final inference
and paper results remain pending; draft imports are not verified evidence.

1. **First:** audit actual annotations/assets and reproduce slide-15 scores.
2. Freeze schema, annotation guide and independent real development/test groups.
3. Complete one dependable extraction path with preserved raw outputs.
4. Implement rules and development-calibrated review policy.
5. Implement and development-pilot the hosted adapter/P2, then selective routing/resolution/P3. Freeze one provider/model and distinct fallback/review policies.
6. Complete all three frontend paths, effective editing, PostgreSQL storage, basic dashboard and CSV export. Product work/annotation may overlap without exposing held-out labels to tuning.
7. Freeze methods and run P1/P2/P3 on the untouched real benchmark, followed by supported A/B/C reliability ablations on saved outputs.
8. Add synthetic ablations, hosted OCR-context variants or timing study only when resources permit.

Paper deliverables: scope and related work; three pipeline architectures and versioned routing/resolution/review rules; actual dataset/split description; P1/P2/P3 extraction-quality, latency, local-memory, usage/cost and failure comparison; common B reliability comparison; supported A/B/C ablation table; accepted-error/coverage and quality/API-usage curves; paired uncertainty estimates; examples of improvements, regressions and undetected errors; reproducibility details and limitations.

Correct presentation claims before publication: confidence versus accuracy; document types versus accounting heads; planned versus collected datasets; completed versus pending components; expected effort savings versus measured savings. Do not claim first-ever integration, universal compliance, perfect OCR/classification, or model superiority without evidence. Verify bibliographic metadata rather than copy slide years: the invoice overview PDF has a 2024 DOI despite older template/footer references. FinBERT sentiment results do not establish accounting-head assignment performance.

Completion means a functioning manual-upload application, all three implemented extraction pipelines, and a reproducible study covering both pipeline comparison and reliability on verified real invoices. If credentials/quota prevent hosted experiments, report the missing arms as incomplete rather than claim the three-pipeline study is complete. If the sample remains small, report a pilot study. Updating this plan does not implement pipelines, make live API calls, run experiments, install dependencies or provision services.
