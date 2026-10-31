"""Run with: python -m unittest -v test_generator.py"""
import copy
import contextlib
import io
import json
import random
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

import generate_indian_docs as g


def config():
    return {
        "seed": 42, "start_date": "2024-04-01", "end_date": "2025-03-31",
        "templates": list(g.ALL_LAYOUTS), "suppliers_per_split": 40,
        "max_items": 8, "catalog": copy.deepcopy(g.CATALOG), "dpi": 100,
        "font_dir": None, "variants": 1, "augment": "mixed", "format": "png",
    }


class AccountingTests(unittest.TestCase):
    def test_indian_grouping_and_rounding(self):
        self.assertEqual(g.indian_money("12345678.90"), "1,23,45,678.90")
        self.assertEqual(g.indian_money("-0.125"), "-0.13")
        self.assertEqual(g.indian_money(0), "0.00")
        self.assertEqual(g.rupee_words("105.25"), "Indian Rupees One Hundred Five and Twenty Five Paise Only")
        self.assertEqual(g.financial_year(g.date(2025, 3, 31)), "24-25")
        self.assertEqual(g.financial_year(g.date(2025, 4, 1)), "25-26")

    def test_known_intrastate_invoice(self):
        items, totals, summary = g.calculate_items([
            g.raw_line("Item A", 3, 199.95, gst_rate=18, discount_percent=5),
            g.raw_line("Item B", "2.5", "40.00", gst_rate=12),
        ], "intra_state", rounded=True)
        self.assertEqual(items[0]["gross"], "599.85")
        self.assertEqual(items[0]["discount"], "29.99")
        self.assertEqual(items[0]["taxable_value"], "569.86")
        self.assertEqual(items[0]["cgst"], "51.29")
        self.assertEqual(items[0]["sgst"], "51.29")
        self.assertEqual(totals["taxable_value"], "669.86")
        self.assertEqual(totals["tax_total"], "114.58")
        self.assertEqual(totals["pre_round_total"], "784.44")
        self.assertEqual(totals["round_off"], "-0.44")
        self.assertEqual(totals["grand_total"], "784.00")
        self.assertEqual(len(summary), 2)

    def test_interstate_and_non_gst(self):
        raw = [g.raw_line("Item", 2, 100, gst_rate=18)]
        items, total, _ = g.calculate_items(raw, "inter_state", False)
        self.assertEqual(total["igst"], "36.00")
        self.assertEqual(total["cgst"], "0.00")
        self.assertEqual(total["grand_total"], "236.00")
        for mode in ("composition", "unregistered", "not_separately_charged"):
            with self.subTest(mode=mode):
                rows, totals, _ = g.calculate_items(raw, mode, False)
                self.assertEqual(totals["tax_total"], "0.00")
                self.assertEqual(totals["grand_total"], "200.00")
                self.assertEqual(rows[0]["gst_rate"], "0")

    def test_randomized_document_invariants(self):
        conf = config()
        visual_types, tax_modes = set(), set()
        for kind in g.DOC_TYPES:
            for i in range(160):
                doc = g.make_document(kind, i, ("train", "val", "test")[i % 3], conf)
                g.validate_document(doc)
                self.assertEqual(doc, g.make_document(kind, i, ("train", "val", "test")[i % 3], conf))
                visual_types.add(doc["visual_document_type"])
                tax_modes.add(doc["tax_regime"])
                if doc["tax_regime"] == "composition":
                    self.assertEqual(doc["supplier"]["state_code"], doc["buyer"]["state_code"])
                if kind == "credit_note":
                    self.assertLess(g.dec(doc["signed_accounting_amount"]), 0)
                if kind == "debit_note":
                    self.assertGreater(g.dec(doc["signed_accounting_amount"]), 0)
                for item in doc["items"]:
                    self.assertEqual(g.dec(item["gross"]) - g.dec(item["discount"]), g.dec(item["taxable_value"]))
                    self.assertEqual(g.dec(item["taxable_value"]) + g.dec(item["cgst"]) + g.dec(item["sgst"]) + g.dec(item["igst"]), g.dec(item["total"]))
        self.assertTrue({"tax_invoice", "bill_of_supply", "non_gst_bill", "receipt", "expense_voucher", "utility_bill", "credit_note", "debit_note"} <= visual_types)
        self.assertTrue({"intra_state", "inter_state", "composition", "unregistered"} <= tax_modes)


class RenderingTests(unittest.TestCase):
    def test_all_templates_with_extreme_item_counts(self):
        conf = config()
        for kind in g.DOC_TYPES:
            for i in range(12):
                with self.subTest(kind=kind, index=i):
                    doc = g.make_document(kind, i, "train", conf)
                    if kind in ("gst_invoice", "purchase_bill"):
                        # Force the maximum row count and three tax rates.
                        raw = [g.raw_line(g.CATALOG[j]["description"], 45, 99999.99, g.CATALOG[j]["unit"], g.CATALOG[j]["hsn_sac"], (5, 12, 18)[j % 3]) for j in range(8)]
                        doc["items"], doc["totals"], doc["tax_summary"] = g.calculate_items(raw, doc["tax_regime"])
                        doc["amount_in_words"] = g.rupee_words(doc["totals"]["grand_total"])
                    canvas = g.render_document(doc, conf)
                    self.assertGreater(len(canvas.lines), 20)
                    # Fail on overlapping text lines, including bottom/footer overflow.
                    # Touching text bounds are allowed; actual positive ink boxes aren't.
                    for aidx, a in enumerate(canvas.lines):
                        ax0, ay0, ax1, ay1 = a["source_bbox"]
                        for b in canvas.lines[aidx + 1:]:
                            bx0, by0, bx1, by1 = b["source_bbox"]
                            overlap_w = min(ax1, bx1) - max(ax0, bx0)
                            overlap_h = min(ay1, by1) - max(ay0, by0)
                            self.assertFalse(overlap_w > 1 and overlap_h > 1, f"Overlapping text: {a['text']!r} and {b['text']!r}")
                    for word in canvas.words:
                        x0, y0, x1, y1 = word["source_bbox"]
                        self.assertTrue(0 <= x0 < x1 <= canvas.image.width + .1)
                        self.assertTrue(0 <= y0 < y1 <= canvas.image.height + .1)

    def test_known_homography(self):
        source = [[0, 0], [100, 0], [100, 200], [0, 200]]
        target = [[15, 20], [120, 11], [135, 225], [8, 210]]
        matrix = g.homography(source, target)
        np.testing.assert_allclose(g.project_points(source, matrix), target, atol=1e-8)
        recovered = g.project_points(target, np.linalg.inv(matrix))
        np.testing.assert_allclose(recovered, source, atol=1e-8)

    def test_annotations_follow_actual_image_warp(self):
        # A black rectangle is an independent pixel target for verifying the matrix.
        image = Image.new("RGB", (240, 340), "white")
        g.ImageDraw.Draw(image).rectangle((70, 100, 155, 225), fill="black")
        record = [{"text": "rectangle", "source_bbox": [70, 100, 156, 226]}]
        for mode in ("none", "scan", "photo"):
            out, matrix, _ = g.augment_image(image, 91824, mode)
            annotation = g.transform_annotations(record, matrix, *out.size)[0]
            ys, xs = np.where(np.asarray(out).mean(axis=2) < 60)
            self.assertGreater(len(xs), 3000)
            actual = np.array([xs.min(), ys.min(), xs.max() + 1, ys.max() + 1])
            np.testing.assert_allclose(annotation["bbox"], actual, atol=3)
            for x, y in annotation["polygon"]:
                self.assertTrue(0 <= x <= out.width and 0 <= y <= out.height)

    def test_rendered_words_cover_ink(self):
        c = g.Canvas(600, 120, 150, 120)
        c.text(20, 20, "GSTIN 27ABQXD1234E1Z0  ₹ 1,23,456.78", "sample", size=22)
        ink = np.asarray(c.image).mean(axis=2) < 150
        mask = np.zeros(ink.shape, dtype=bool)
        for word in c.words:
            x0, y0, x1, y1 = word["source_bbox"]
            mask[max(0, int(y0)-1):int(np.ceil(y1))+1, max(0, int(x0)-1):int(np.ceil(x1))+1] = True
        self.assertGreater(ink.sum(), 100)
        self.assertLessEqual((ink & ~mask).sum(), 3)


class DatasetTests(unittest.TestCase):
    def test_msme_sector_catalogs(self):
        conf = config()
        for sector in g.MSME_SECTORS:
            conf["sectors"] = [sector]
            allowed = {row["description"] for row in g.SECTOR_CATALOGS[sector]}
            for kind in ("gst_invoice", "purchase_bill", "credit_note", "debit_note"):
                for index in (0, 3, 5, 11):
                    with self.subTest(sector=sector, kind=kind, index=index):
                        doc = g.make_document(kind, index, "train", conf)
                        self.assertEqual(doc["extra"]["msme_sector"], sector)
                        for row in doc["items"]:
                            self.assertIn(row["description"].removesuffix(" - adjustment"), allowed)
                            if row["unit"] == "JOB":
                                self.assertLessEqual(g.dec(row["quantity"]), 4)
                        g.validate_document(doc)

    def test_batch_fields_and_layout_sizes(self):
        conf = config()
        for kind in ("gst_invoice", "purchase_bill"):
            for index in (5 + j * len(g.INVOICE_LAYOUTS) for j in range(4)):
                doc = g.make_document(kind, index, "train", conf)
                self.assertEqual(doc["template"], "batch_mrp")
                for row in doc["items"]:
                    self.assertTrue(row["batch_number"].startswith("B"))
                    self.assertGreater(row["expiry"], doc["date"])
                    self.assertGreater(g.dec(row["mrp"]), g.dec(row["unit_price"]))
                c = g.render_document(doc, conf)
                self.assertTrue(any(line["field"].endswith(".batch_number") for line in c.lines))
                self.assertTrue(any(line["field"].endswith(".mrp") for line in c.lines))
        a5 = g.render_document(g.make_document("gst_invoice", 3, "train", conf), conf)
        wide = g.render_document(g.make_document("gst_invoice", 4, "train", conf), conf)
        self.assertEqual(a5.image.width, round(148 / 25.4 * conf["dpi"]))
        self.assertGreater(wide.image.width, wide.image.height)

    def test_large_generation_plans_do_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "planned"
            for arguments, expected in (([], 6000), (["--per-type", "10000"], 60000)):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    g.main(["--dry-run", "--out", str(out)] + arguments)
                plan = json.loads(output.getvalue())
                self.assertEqual(plan["images"], expected)
                self.assertEqual(plan["annotation_files"], expected)
                self.assertEqual(len(plan["types"]), 6)
                self.assertFalse(out.exists())

    def test_zoho_and_odoo_cover_all_six_classes(self):
        conf = config()
        conf["templates"] = list(g.MODERN_LAYOUTS)
        for kind in g.DOC_TYPES:
            for index, template in enumerate(g.MODERN_LAYOUTS):
                with self.subTest(kind=kind, template=template):
                    doc = g.make_document(kind, index, "train", conf)
                    self.assertEqual(doc["template"], template)
                    canvas = g.render_document(doc, conf)
                    g.validate_document(doc)
                    self.assertTrue(any(line["field"] == "totals.grand_total" for line in canvas.lines))
                    if kind in ("credit_note", "debit_note"):
                        self.assertTrue(any(line["field"] == "extra.reference_invoice" for line in canvas.lines))
                    if kind == "utility_bill":
                        self.assertTrue(any(line["field"] == "extra.billing_period" for line in canvas.lines))

    def test_custom_catalog_overrides_sector_products(self):
        conf = config()
        conf.update({"custom_catalog": True, "catalog": [g.CATALOG[0]], "sectors": ["auto_parts"]})
        for index in (0, 3, 4, 5):
            doc = g.make_document("gst_invoice", index, "train", conf)
            self.assertTrue(all(row["description"] == g.CATALOG[0]["description"] for row in doc["items"]))

    def test_split_apportionment(self):
        self.assertEqual(g.make_split_counts(1000, [.8, .1, .1]), [800, 100, 100])
        self.assertEqual(g.make_split_counts(6, [.8, .1, .1]), [4, 1, 1])
        self.assertEqual(g.make_split_counts(1, [.8, .1, .1]), [1, 0, 0])
        for n in range(1, 50):
            counts = g.make_split_counts(n, [.8, .1, .1])
            self.assertEqual(sum(counts), n)
            self.assertTrue(all(c >= 0 for c in counts))

    def test_party_isolation(self):
        conf = config()
        parties = {}
        for split in ("train", "val", "test"):
            parties[split] = {g.make_document(kind, i, split, conf)[who]["party_id"] for kind in g.DOC_TYPES for i in range(30) for who in ("buyer", "supplier")}
        self.assertFalse(parties["train"] & parties["val"])
        self.assertFalse(parties["train"] & parties["test"])
        self.assertFalse(parties["val"] & parties["test"])

    def test_dataset_roundtrip_and_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            g.main(["--out", str(out), "--per-type", "3", "--types", "gst_invoice", "--dpi", "72", "--variants", "2", "--augment", "photo", "--no-preview"])
            records = [json.loads(x) for x in (out / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 6)
            by_base = {}
            for rec in records:
                by_base.setdefault(rec["base_document_id"], set()).add(rec["split"])
                label = json.loads((out / rec["annotation"]).read_text())
                with Image.open(out / rec["image"]) as img:
                    self.assertEqual(img.size, (rec["width"], rec["height"]))
                for word in label["ocr"]["words"]:
                    x0, y0, x1, y1 = word["bbox_1000"]
                    self.assertTrue(0 <= x0 <= x1 <= 1000)
                    self.assertTrue(0 <= y0 <= y1 <= 1000)
                g.validate_document(label["document"])
            self.assertTrue(all(len(splits) == 1 for splits in by_base.values()))
            self.assertEqual({r["augmentation"] for r in records}, {"none", "photo"})
            self.assertEqual(json.loads((out / "dataset_info.json").read_text())["status"], "complete")

    def test_deterministic_pixels_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = config()
            conf.update({"out": str(Path(tmp) / "one"), "variants": 2, "augment": "scan"})
            first = g.generate_task(("expense_receipt", 2, "train", conf))
            conf["out"] = str(Path(tmp) / "two")
            second = g.generate_task(("expense_receipt", 2, "train", conf))
            self.assertEqual(first, second)
            for rec in first:
                for key in ("image", "annotation"):
                    self.assertEqual((Path(tmp) / "one" / rec[key]).read_bytes(), (Path(tmp) / "two" / rec[key]).read_bytes())

    def test_custom_catalog_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(g.CATALOG[:1]))
            self.assertEqual(len(g.load_catalog(path)), 1)
            for invalid in ([], [{"description": "No price"}], [{**g.CATALOG[0], "price_min": -1}], [{**g.CATALOG[0], "gst_rate": "NaN"}]):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    g.load_catalog(path)


if __name__ == "__main__":
    unittest.main()
