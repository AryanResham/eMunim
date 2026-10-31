# Version 2 validation

Validated on 31 October 2026 with Python 3.12.14, Pillow 12.3.0 and NumPy 2.3.5.

All **18 tests passed** in 7.396 seconds. Coverage includes known-answer GST
calculations; 960 randomized accounting cases; 72 layout render cases including
maximum invoice item counts; pixel-versus-annotation warp alignment; split and
party isolation; deterministic labels/images; custom catalogs; sector-coherent
MSME products; batch/MRP/expiry fields; A5 and landscape sizes; and Zoho/Odoo
themes across every document class.

Dry-run plans verify that the default is 6,000 images plus 6,000 annotations,
and `--per-type 10000` schedules 60,000 of each. These large runs were planned,
not executed as part of this validation.

The generated preview set contains **120 images**, 20 per class, all **14 layouts**,
all **eight MSME product sectors** and all **five utility categories**. Every
image/annotation pairing was checked for arithmetic consistency, word boxes
inside the final saved image, non-overlapping text and disjoint party IDs across
splits. Full-size Zoho/Odoo-inspired invoices and a six-layout comparison sheet
were visually inspected.

There are **22,920 word boxes**. Splits contain 96 train, 12 validation and
12 test images; appearance modes contain 53 scans, 41 clean pages and 26 photos.

These checks validate the generator and preview data. No model was trained and
no real-world model accuracy or exact native ERP-export match is claimed.
