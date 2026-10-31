# LayoutLM empty extraction investigation

Investigated 2026-10-16 using cached OCR and existing local checkpoints only.
No API calls, training, checkpoint edits, or production routing changes.

## Confirmed mechanism

The configured GST model is `layoutlm-synthetic-tax_invoice-trained`.
On the verification invoice it labels all 60 OCR words `O` (outside any
entity). Consequently BIO aggregation correctly produces no fields.
All 60 words reach the encoder. Strict pipeline inference does not discard
predictions by confidence. The checkpoint loads and its BIO names are read
from its own config, so neither missing weights, confidence filtering,
token truncation nor a label-index mismatch explains this particular result.

## Control runs

The same processor, checkpoint and production BIO decoder were used for
three existing Synthetic_Test invoices, using their stored generator tokens:

| Input | OCR words | Encoded words | Populated fields |
|---|---:|---:|---:|
| Verification invoice with cached Google OCR | 60 | 60 | 0 |
| GST-001001 | 224 | 212 | 10 |
| GST-001003 | 242 | 207 | 9 |
| GST-001005 | 242 | 216 | 10 |

These controls establish that this checkpoint can produce entities through
the production decoder. They are not an accuracy benchmark: only three
stored examples were selected, their token source differs from Google OCR,
and their training overlap has not been audited.

## Interpretation and separate limitations

The evidence points to poor generalization across layout/text/OCR input
distributions. It does not isolate layout alone or prove overfitting.
The smoke invoice uses a sparse single-column layout, while these stored
examples use a dense invoice template. A matched comparison using exact
and Google OCR tokens on the same images is needed to separate OCR effects
from layout sensitivity. The weights are already fine-tuned; calling them
simply untrained would be inaccurate.

Separate issues: all three stored controls exceed the encoder window, and
the configured checkpoint lacks IGST_AMOUNT, DUE_DATE and PO_NUMBER labels
although the API exposes them. It cannot directly predict those labels.
Neither issue explains all-O output on the 60-word smoke invoice.

## Next steps

1. Evaluate matched exact/Google OCR inputs and group results by unseen layout.
2. Add this invoice as a labeled regression/evaluation case, keeping it out of training.
3. Audit training label balance and template diversity before retraining.
4. Align checkpoint label coverage with the intended schema during future training.
5. Keep missing-field review and hosted fallback enabled. Do not describe a
   successful HTTP response as successful extraction quality.

Reproduce from the repository root: `python scripts/diagnose_layoutlm.py`.
Raw per-word evidence is saved to
`backend/data/verification/20261016T134533Z/layoutlm_diagnosis.json`.
