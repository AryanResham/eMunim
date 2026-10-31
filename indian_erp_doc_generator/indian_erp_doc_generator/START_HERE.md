# Generate the complete dataset

The images in `examples/` are previews. The Python script generates a configurable
dataset across **all six document classes**, with matching annotations.

After extracting the archive, open a terminal in `indian_erp_doc_generator`:

```bash
python -m pip install -r requirements.txt
python generate_indian_docs.py --out msme_6000 --per-type 1000 --workers 4 --format jpg
```

| Class | Images | Matching JSON files |
|---|---:|---:|
| GST invoice | 1,000 | 1,000 |
| Purchase bill | 1,000 | 1,000 |
| Expense receipt | 1,000 | 1,000 |
| Utility bill | 1,000 | 1,000 |
| Credit note | 1,000 | 1,000 |
| Debit note | 1,000 | 1,000 |
| **Total** | **6,000** | **6,000** |

For **60,000** documents, change `--per-type 1000` to `--per-type 10000` and use
a fresh output directory. `--per-type` applies to each class, not the total.
Use `--workers 1` if memory is limited. Every image gets annotations automatically.

To restrict the visual themes to Zoho and Odoo inspirations while retaining all
six classes:

```bash
python generate_indian_docs.py --out zoho_odoo_6000 --templates zoho_style odoo_style --per-type 1000 --workers 4 --format jpg
```

The full generator provides **14 original layout families**, including common
Tally/BUSY/Marg-like print conventions and Zoho/Odoo-inspired modern themes.
It includes eight Indian MSME product sectors, Indian monetary formats, tax
arithmetic, clean/scan/photo variants, and word/line boxes aligned to each image.
It is a synthetic-data renderer; it does not run or export from the named ERPs.

See `README.md` for exact fields, template names, annotation schema, tax/catalog
assumptions and model-training guidance.
