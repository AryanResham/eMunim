# Indian MSME ERP document image generator — version 2

**This is a scalable generator for all six classes, not a 36-document dataset.**
The default run creates **6,000 images plus 6,000 matching JSON annotation files**:
1,000 GST invoices, 1,000 purchase bills, 1,000 expense receipts, 1,000 utility
bills, 1,000 credit notes and 1,000 debit notes. Set `--per-type 10000` for 60,000
images and annotations. Counts are configurable up to 99,999 documents per class
per run; different seeds generate additional data.

Version 2 adds A5 trading bills, landscape item-wise GST invoices, batch/MRP/expiry
billing, compact adjustment notes, and **Zoho Books/Invoice-inspired and
Odoo-inspired themes**. There are **14 layout families**. The Zoho and Odoo themes
can be selected for every one of the six classes. These are original synthetic
renderings informed by common print conventions, not authenticated ERP exports.

A local Python script that generates fictional Indian business document images
for document classification, OCR and field extraction. It covers the six classes
in your reference image. No ERP installation, paid APIs or internet access is
needed at generation time.

The layouts are original approximations of common Indian accounting printouts,
including boxed trading invoices, letterheads, continuous-paper formats,
receipts, vouchers and utility bills. They are not exact exports or copies of
Tally, BUSY, Marg, Zoho or Odoo, or any specific ERP version.

## Quick start

Use Python 3.10 or newer. Extract the complete archive, open a terminal in its
`indian_erp_doc_generator` directory, then run:

```bash
python -m pip install -r requirements.txt
python generate_indian_docs.py --out dataset --per-type 1000 --workers 4
```

That creates **6,000 images**: 1,000 per class, with corresponding JSON labels.
The default split is 80% training, 10% validation and 10% test. If memory is
limited, use `--workers 1`. Every output directory must be new or empty.

A small smoke test, if desired:

```bash
python generate_indian_docs.py --out small_dataset --per-type 6 --format jpg
```

The supplied `examples/` folder contains **120 preview images and their
annotations**, all 14 layout families, all five utility categories, plus a
manifest and contact sheet. These examples demonstrate the pipeline; they are
not a large enough dataset to train or evaluate a production model.

## Document coverage

| Class / `document_type` | Generated content | Layouts |
|---|---|---|
| `gst_invoice` | Supplier and buyer, GSTIN, place of supply, HSN/SAC, quantities, units, rates, discounts, CGST/SGST or IGST, tax summary, round-off, amount in words, bank/signatory area | Boxed, letterhead, continuous paper, A5 trade, landscape item tax, batch/MRP, Zoho-style, Odoo-style |
| `purchase_bill` | Incoming supplier tax invoice, composition bill of supply, or unregistered cash/retail bill | Same eight invoice layouts |
| `expense_receipt` | Meals, local travel, fuel and office supplies; payment mode, reference; employee/department on internal vouchers | Thermal, expense voucher, compact receipt, Zoho-style, Odoo-style |
| `utility_bill` | Electricity, water, internet, telephone and gas; consumer account, billing period, due date; readings/consumption for metered services | Utility grid, utility plain, Zoho-style, Odoo-style |
| `credit_note` | Supplier-issued credit adjustment, original invoice number/date, reason and tax reversal amounts | Boxed, letterhead, continuous paper, compact note, Zoho-style, Odoo-style |
| `debit_note` | Supplier-issued debit adjustment, original invoice number/date, reason and additional tax amounts | Same six note layouts |

Indian details include lakh/crore grouping (`1,23,456.78`), rupee notation,
Indian amount-in-words, April–March financial years, Indian cities/state codes
and PIN codes, and day-first printed dates. Fonts, copy labels, line items,
prices, discounts, dates, state combinations and paper appearance vary.

Invoice/note line items are drawn from coherent MSME sectors: `hardware`,
`electrical`, `stationery`, `textiles`, `fmcg`, `pharmacy`, `auto_parts` and
`services`. A hardware business bills hardware items instead of randomly mixing
medicines, computers and fabric. Supplier names match the sector. Batch/MRP
layouts favour pharmacy/FMCG when those sectors are enabled; other sectors can
also use batch layouts. Perishable goods receive expiry dates after the bill date.
MRP includes illustrative tax; the rate and assessable amount exclude tax.

Utility documents keep their provider billing fields. Applying a modern ERP-like
visual theme does not imply that Zoho or Odoo provides a native utility-billing
module. The generator does not log in to any ERP or label images as verified
native exports. The company branding is fictional.

## Important label distinction

**A purchase bill is a business-context label, not a unique visual format.** A
GST invoice received from a vendor is simultaneously a purchase bill for its
buyer. A utility bill may also be a tax invoice; an expense may have a tax receipt.
Do not expect an image-only classifier to infer information absent from the page.

Each annotation therefore contains both:

- `document.document_type`: one of your six requested business classes.
- `document.visual_document_type`: `tax_invoice`, `bill_of_supply`,
  `non_gst_bill`, `receipt`, `expense_voucher`, `utility_bill`, `credit_note`
  or `debit_note`.
- `document.business_context`: sale/purchase direction, tenant party ID,
  issuer role, and credit/debit adjustment sign when applicable.

For an image-only system, consider training the visible type first and resolving
purchase/sale from the buyer/seller and your organisation context. The generated
internal expense voucher is issued by the buyer; external receipts are issued
by the merchant. Debit and credit notes in this generator are supplier-issued.

## Useful commands

```bash
# Default: all six types, 1,000 each, with annotations
python generate_indian_docs.py --out msme_6000 --workers 4 --format jpg

# Larger dataset: all six types, 10,000 each = 60,000 images and JSON labels
python generate_indian_docs.py --out msme_60000 --per-type 10000 --workers 4 --format jpg

# Confirm a planned count without generating files
python generate_indian_docs.py --dry-run --per-type 10000

# All six types, only Zoho- and Odoo-inspired themes
python generate_indian_docs.py --out zoho_odoo --templates zoho_style odoo_style --per-type 1000 --workers 4

# Focus invoice and note content on particular MSME sectors
python generate_indian_docs.py --out electrical_hardware --sectors electrical hardware --per-type 1000

# 200 clean GST invoices, high resolution
python generate_indian_docs.py --out clean_invoices --types gst_invoice --per-type 200 --dpi 300 --augment none

# 600 base documents, each with a clean and a photographed version: 1,200 images
python generate_indian_docs.py --out paired --per-type 100 --variants 2 --augment photo --format jpg

# Expense and utility documents only
python generate_indian_docs.py --out expenses --types expense_receipt utility_bill --per-type 500

# Hold out a whole template family in a separate experiment
python generate_indian_docs.py --out boxed_train --types gst_invoice credit_note debit_note --templates erp_boxed erp_continuous --split 1 0 0 --seed 42
python generate_indian_docs.py --out letterhead_test --types gst_invoice credit_note debit_note --templates erp_letterhead --split 0 0 1 --seed 99

# Supply your own product descriptions, HSN/SAC, prices and verified rates
python generate_indian_docs.py --out custom --catalog catalog.example.json --start-date 2025-04-01 --end-date 2026-03-31

# Run the included checks
python -m unittest -v test_generator.py

# All command-line options
python generate_indian_docs.py --help
```

`--per-type` counts base documents **per selected class**, not the total output.
`--variants` multiplies the image count. With more than one variant, variant 0
is clean; later variants use `--augment`. Choosing `--augment none` with several
variants intentionally creates identical views and is usually unnecessary.

## Outputs and annotation schema

| Path relative to `--out` | Contents |
|---|---|
| `images/<split>/<class>/<id>.png` (or `.jpg`) | Rendered image; compatible with class-folder loaders |
| `annotations/<split>/<class>/<id>.json` | Document fields, amounts, OCR annotations, geometry and effects |
| `manifest.jsonl` | One image per line with class, visible type, split, supplier/buyer IDs and relative paths |
| `dataset_info.json` | Seed, config, exact catalog, dependency versions, font hashes and completion status |
| `preview.jpg` | Contact sheet with up to 18 type/layout examples |

All money values in JSON are decimal **strings** with two places. The displayed
credit-note total is positive; `signed_accounting_amount` is negative for credit
notes. It is an adjustment convention, not a complete double-entry journal.

Every JSON annotation includes:

```json
{
  "schema_version": "1.0",
  "sample_id": "<base-id>_v00",
  "base_document_id": "<base-id>",
  "split": "train",
  "image": {"path": "images/train/gst_invoice/<id>.png", "width": 1240, "height": 1753},
  "document": {
    "document_type": "gst_invoice",
    "visual_document_type": "tax_invoice",
    "supplier": {}, "buyer": {}, "items": [], "totals": {},
    "business_context": {}
  },
  "augmentation": {"source_to_image_homography": [[1,0,0],[0,1,0],[0,0,1]]},
  "ocr": {"lines": [], "words": []},
  "regions": []
}
```

Each OCR word and rendered text line carries `text`, semantic `field`, `role`,
pixel `bbox` in `[x_min, y_min, x_max, y_max]` form, a four-point `polygon`,
and `bbox_1000` normalised into `[0, 1000]` for models such as LayoutLM. A word
also has `line_id`. `source_bbox` describes the clean page before augmentation.

The origin is the upper-left; x increases right and y increases down. Coordinates
refer to the **saved image**, including photo margins. Polygons are the clean
box corners transformed through the same matrix used to warp the pixels. Pixel
boxes are their axis-aligned envelopes. The antialias/blur halo can extend a few
pixels beyond the geometric text box; the polygon is not an ink segmentation mask.

Semantic `field` paths identify values such as `supplier.gstin`,
`items.2.unit_price` and `totals.grand_total`. `role` distinguishes a printed key
from its value. Some print lines combine several source fields for realism, such
as `items.0.quantity_rate` and `extra.billing_period`; these are composite display
labels, not literal paths in `document`. Repeated field appearances are preserved.
Reading order is renderer draw order, grouped by field, not global top-to-bottom
sorting. No trained OCR model is used to generate the ground truth.

Minimal loader:

```python
import json
from pathlib import Path
from PIL import Image

root = Path("dataset")
for line in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    labels = json.loads((root / record["annotation"]).read_text(encoding="utf-8"))
    with Image.open(root / record["image"]) as im:
        image = im.convert("RGB")
    words = [w["text"] for w in labels["ocr"]["words"]]
    boxes = [w["bbox_1000"] for w in labels["ocr"]["words"]]
    # Feed image, words and boxes into your model-specific training pipeline.
```

## Diversity, splits and reproducibility

- `mixed` augmentation samples clean pages (30%), scan-like pages (45%) and
  photo-like pages (25%). Scan effects include modest skew, contrast variation,
  grayscale, noise, blur and compression. Photo effects add perspective,
  background margins and side shadows. No deliberate text cropping is applied.
- All variants of a base document stay in one split. Party IDs are generated
  from split-specific namespaces, so complete supplier/buyer identities do not
  cross splits. Generic business-name words can repeat, as in real documents.
- Layout families are shared across the normal splits. That is **not** a
  template-generalisation benchmark. Use the explicit template-holdout commands
  above and a separately held-out, permissioned real-document set.
- Small datasets reserve at least one example per nonzero split when possible.
  Each class can therefore depart from exact 80/10/10 percentages when very small.
- Same seed, arguments, fonts and dependency versions yield the same document
  content, annotations and images regardless of worker count. Different Pillow
  or font versions can change pixels; metadata records the versions and hashes.
- The default output never overwrites an existing nonempty directory. Failed runs
  retain `status: incomplete`; choose a new output directory after correcting the
  issue. Resume mode is not implemented.

## Customisation and practical limits

Edit `SECTOR_ROWS` for built-in MSME product profiles, or pass a JSON list like
`catalog.example.json` to override sector products. Each custom item needs
`description`, `hsn_sac`, `unit`, `price_min`, `price_max` and `gst_rate`.
Descriptions are printable English/ASCII, at most 56 characters; HSN/SAC is a
4–8 digit string; units are 1–5 letters. Catalog customisation affects invoices,
notes and office-supply expenses. Other expense items and utility tariffs live
in `make_document()` and can be edited there.

The generator currently supports **English text with Indian business formatting**.
Hindi and other Indic scripts require a shaping-capable font/layout engine and
reworked word alignment; they are not silently approximated. It generates
single-page documents with up to eight invoice rows. Custom long content that
does not fit raises a layout error; lower `--max-items` or shorten it.

Bundled DejaVu fonts make the complete package portable. The standalone script
also looks for installed DejaVu fonts, then Arial/Times/Courier. For stable pixels,
use the bundled `fonts/` folder. Font attribution is in `fonts/LICENSE-DejaVu.txt`.
The script checks fonts before writing output. No trained model is included.

The data is deliberately fictional. PAN/GSTIN-shaped identifiers use a deliberate
test entity character (`X` in PAN position 4); they are not issued registrations.
Phone numbers start with `00000`, emails use `example.invalid`, and bank/IFSC
details are test values. Each page has the same unobtrusive synthetic-data footer.
There are no real logos, signatures, working payment QR codes or e-invoice IRNs.

Tax arithmetic is internally consistent using `Decimal`, line-level component
rounding, CGST/SGST versus IGST separation and explicit round-off. **Rates,
HSN assignments, utility tariffs and levy treatment are illustrative training
inputs, not current tax advice or a compliant invoicing system.** The default
date window is FY 2024–25. Change the date range and product/rate catalog together
when matching a different real dataset. The utility examples are simplified;
they do not implement provider-specific slabs, subsidies, VAT, duties, arrears
or complete statutory rules. Composition bills are kept intrastate.

Synthetic-only accuracy will not establish performance on real ERP exports,
phone photographs or scans. Mix these with permissioned real examples and use
real held-out data to measure generalisation. Avoid giving models class-folder
paths, manifest metadata or JSON business-context labels as image features.

## Source references

Consulted 25 and 31 October 2026 for field and layout conventions:

- CBIC, tax invoice / credit and debit note particulars:
  https://cbic-gst.gov.in/gst-invoice-rules.html
- Tally's official HSN/SAC invoice printing guidance:
  https://help.tallysolutions.com/article/Tally.ERP9/Tax_India/gst/hsn_not_printing.htm
- Tally invoice configuration, including landscape item-wise GST:
  https://help.tallysolutions.com/article/Tally.ERP9/Maintaining_Company_Data/F12_Config/Sales_Invoice_print_conf.htm
- BUSY GST formats, including A5 and slip printing:
  https://busy.in/faqs/what-different-gst-formats-available-busy-add-company-logo-details-invoice-template-answerid-28978/
- Marg GUI, DMP, half-page and thermal format collections:
  https://care.margcompusoft.com/margerp/gui-format/1994/1/How-to-download-default-bill
- Zoho Books India PDF templates:
  https://www.zoho.com/in/books/help/settings/templates.html
- Odoo customer invoices and credit/debit notes:
  https://www.odoo.com/documentation/18.0/applications/finance/accounting/customer_invoices.html
  https://www.odoo.com/documentation/18.0/applications/finance/accounting/customer_invoices/credit_notes.html
- Pillow image transforms and drawing APIs:
  https://pillow.readthedocs.io/en/stable/reference/Image.html
  https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html

These references inform field names and rendering; the script does not claim
current legal compliance or reproduce a proprietary ERP template exactly.
