# eMunim extraction models

Six LayoutLMv3 token classifiers specialize in GST invoices, purchase bills,
expense receipts, utility bills, credit notes and debit notes. Each receives a
document image plus OCR words and normalized boxes, then predicts BIO field tags.
Document-type classification is a separate rule/optional zero-shot DeBERTa step;
the extraction benchmarks below supply the correct document type.

The shared transfer sequence is LayoutLMv3 base, FUNSD and SROIE, followed by
document-specific synthetic training. The recent corpus has 800 train, 100
validation and 100 test documents per type. Document and party identities are
separated by split, but layout families are shared. Real invoices were not used
to train these synthetic variants.

Two recent release families are retained locally:

- `ocr-augmented-20261119`: a mixture of clean and generated OCR-like inputs.
- `identifier-pilot-20261119`: three-epoch identifier/date fine-tuning from that
  release, with the heads retained. GST passed a development gate before the
  remaining models were trained.

Identifier/date reconstruction uses recognized characters, format and neighboring
boxes; it does not invent missing characters. The second augmentation version
also teaches split identifiers. Its OCR calibration used 105 cached GST training
extracts; other perturbation rates are engineering presets, not measured error
distributions for every document type. Validation F1 on generated inputs must not
be presented as real-OCR accuracy.

| Type | Previous release + fix, cached Vision | Identifier release + fix, cached Vision | Identifier release, separate RapidOCR cohort |
|---|---:|---:|---:|
| GST invoice | 84.26% | 85.19% | 88.89% |
| Purchase bill | 84.62% | 83.08% | 82.09% |
| Expense receipt | 94.00% | 92.00% | 80.00% |
| Utility bill | 90.67% | 84.00% | 75.32% |
| Credit note | 87.88% | 84.85% | 86.76% |
| Debit note | 86.76% | 88.24% | 78.79% |
| Overall | 87.50% (378/432) | 85.88% (371/432) | 82.57% (360/436) |

Each cohort contains ten synthetic images per type. Percentages are normalized
populated-field value accuracy, not entity F1. The cached-Vision cohort had already
been examined. The other cohort is disjoint from training/validation and that
cohort, but was partially evaluated before an interrupted run. Because its OCR
engine and images differ, it is not an isolated OCR-engine comparison. RapidOCR
is a historical experiment only; the deployed backend uses Google Vision.

On the second cohort, generator-exact words/boxes gave 436/436 correct values.
With RapidOCR, only 13/60 documents had every checked populated field correct.
Identifiers improved substantially, but names, currency transcription, party-role
assignment and missing values remain concerns. These results do not establish
unseen-layout or real-invoice reliability. Review is required before accounting use.

The latest checkpoints have not been automatically activated. Select a release on
development evidence and validate it on independently labelled real invoices.
Use the exporter and SHA-256 manifest in [DEPLOYMENT.md](DEPLOYMENT.md) to provision
the chosen release separately from GitHub. Source folders, weights, datasets,
raw invoice values and detailed local experiment artifacts are intentionally not
published in this code repository.
