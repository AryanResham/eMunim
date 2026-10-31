# Metric definitions and evidence boundaries

All rates include declared cohort counts; undefined denominators are JSON null,
never fabricated zero/100%. No annotated real Indian MSME benchmark is currently
verified. Synthetic/public results are separate cohorts. Raw outputs are preserved.

| Family | Measured outputs | Definition / qualification |
|---|---|---|
| Public extraction | strict entity precision, recall, F1; token accuracy; complete-document accuracy | BIO IOB2 strict scoring; complete documents compare all entity spans. FUNSD and SROIE are different tasks. |
| Accounting extraction | per-field TP/FP/FN, precision/recall/F1; micro/macro F1; complete-document accuracy | A wrong populated value contributes one FP and one FN. Missing GT field contributes FN; prediction on GT absence contributes FP. |
| Absence / unsupported fields | absent-field specificity; extra-absent-field rate | The latter is extra predictions / all populated predictions. It is not proof that every wrong value was fabricated by a model. |
| OCR | corpus CER/WER, reference character/word counts, failures/empty outputs | Levenshtein edits / reference length after NFKC and whitespace collapse, case-sensitive. Generator ordering includes column-order disagreements. Provider word confidence is not accuracy. |
| Document classifier | confusion counts, accuracy, macro precision/recall/F1, L1/L2/L3 counts and conditional accuracy | Failed classification remains an unavailable output. Unused levels have undefined accuracy; no invented L2 score. Oracle type is supplied to extraction. |
| Reliability A/B/C | review rate, accepted coverage, detection precision/recall, FPR/specificity, field detection precision/recall, accepted/silent error rates, confusion counts | A has no detector; B uses shared validation; C adds meaningful local-model confidence only. Flags do not alter extraction F1. |
| Confidence | Brier score, ten-bin ECE, correctness AUROC, bin counts | Populated LayoutLM fields only. Hosted confidence is unavailable. AUROC is undefined if only one correctness class exists. |
| Uncertainty | Wilson complete-document accuracy interval; paired document bootstrap and cluster bootstrap | Seed 42, 1,000 replicates. Small synthetic family counts limit inference. These are not real-population guarantees. |
| Performance | model load/hash time; median/p95 warm forward/window time; median/p95 warm pipeline and client end-to-end time | Window forward excludes image decoding/tokenization; full pipeline includes preprocessing. Shared measured OCR/classification time is explicitly added, not represented as independently repeated calls. |
| Quota overhead | pacing and retry wait, attempts/retries, logical requests, tokens, fallback rate, cache hits, failures | Primary live pilot disables shared hosted caches. Artificial spacing is separated from client service time; server time/remote hardware are not inferred. |
| Resources | sampled local RSS baseline/peak/increase; CUDA peak allocated/reserved bytes | RSS sampled every 20 ms may miss brief peaks. CUDA allocator peaks are not total GPU memory or remote-server memory. |
| Routing curve | fixed-candidate quality vs routed-document rate | Counterfactual replay using saved P1/P2 outputs, clearly separate from fresh P3 requests, cost or latency. |

Per-document automatic extraction is incorrect if any applicable field is wrong,
missing or extra, or an operational failure occurs. Human corrections remain a
separate product outcome. Raw automatic outputs are never replaced by corrected
values when scoring. Dates/amounts/GSTINs use declared normalizations; text retains
word content and normalizes case/whitespace only.

Hosted token usage is the usage returned with accepted responses. Retried HTTP,
parsing or schema failures may not expose retained token usage; reported usage
must not be interpreted as exhaustive account consumption or billing. Physical
request attempts are counted separately. Saved automatic field predictions are
the scoring evidence; the adapter does not retain every rejected HTTP body.

Monetary charges, real-data accuracy, remote VLM memory, controlled human time
savings, duplicate-pair accuracy and accounting-head classification are explicitly
unavailable without their corresponding evidence. Account charges cannot be
inferred from an API key or a provider's free allowance. See each run's
unavailable_metrics, protocol.json, API ledger and saved raw predictions.
