#!/usr/bin/env python3
"""Generate fictional Indian ERP document images and exact rendering annotations.

Python >= 3.10; pip install Pillow numpy
Example: python generate_indian_docs.py --out dataset --per-type 1000 --workers 4
See README.md for label semantics, synthetic tax assumptions and the JSON schema.
No API keys, internet, browser, OCR engine or proprietary ERP software required.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, __version__ as PIL_VERSION
except ImportError as exc:
    raise SystemExit("Install dependencies first: python -m pip install Pillow numpy") from exc

VERSION = "2.0.0"
DOC_TYPES = ("gst_invoice", "purchase_bill", "expense_receipt", "utility_bill", "credit_note", "debit_note")
CLASSIC_LAYOUTS = ("erp_boxed", "erp_letterhead", "erp_continuous")
MODERN_LAYOUTS = ("zoho_style", "odoo_style")
INVOICE_LAYOUTS = CLASSIC_LAYOUTS + ("trade_a5", "item_tax_landscape", "batch_mrp") + MODERN_LAYOUTS
LAYOUTS = {
    "gst_invoice": INVOICE_LAYOUTS, "purchase_bill": INVOICE_LAYOUTS,
    "credit_note": CLASSIC_LAYOUTS + ("note_compact",) + MODERN_LAYOUTS,
    "debit_note": CLASSIC_LAYOUTS + ("note_compact",) + MODERN_LAYOUTS,
    "expense_receipt": ("thermal", "expense_voucher", "compact_receipt") + MODERN_LAYOUTS,
    "utility_bill": ("utility_grid", "utility_plain") + MODERN_LAYOUTS,
}
ALL_LAYOUTS = tuple(dict.fromkeys(x for values in LAYOUTS.values() for x in values))
STATES = [
    ("27", "Maharashtra", "Pune", "411001"),
    ("24", "Gujarat", "Ahmedabad", "380001"),
    ("29", "Karnataka", "Bengaluru", "560001"),
    ("33", "Tamil Nadu", "Chennai", "600001"),
    ("36", "Telangana", "Hyderabad", "500001"),
    ("07", "Delhi", "New Delhi", "110001"),
    ("19", "West Bengal", "Kolkata", "700001"),
    ("08", "Rajasthan", "Jaipur", "302001"),
    ("09", "Uttar Pradesh", "Lucknow", "226001"),
    ("32", "Kerala", "Kochi", "682001"),
    ("23", "Madhya Pradesh", "Indore", "452001"),
    ("03", "Punjab", "Ludhiana", "141001"),
]
# Illustrative historical training catalog, NOT a current HSN/rate determination.
CATALOG = [
    {"description": "A4 copier paper 75 GSM - 500 sheets", "hsn_sac": "48025690", "unit": "REAM", "price_min": 210, "price_max": 340, "gst_rate": 12},
    {"description": "Ball point pen - blue ink box", "hsn_sac": "96081019", "unit": "BOX", "price_min": 80, "price_max": 180, "gst_rate": 18},
    {"description": "Lever arch file - office series", "hsn_sac": "48203000", "unit": "NOS", "price_min": 75, "price_max": 150, "gst_rate": 18},
    {"description": "Printer toner cartridge - black", "hsn_sac": "84439959", "unit": "NOS", "price_min": 1300, "price_max": 3200, "gst_rate": 18},
    {"description": "Copper insulated cable 1.5 sq mm", "hsn_sac": "85444999", "unit": "MTR", "price_min": 24, "price_max": 65, "gst_rate": 18},
    {"description": "Hex bolt and nut set M10", "hsn_sac": "73181500", "unit": "SET", "price_min": 12, "price_max": 38, "gst_rate": 18},
    {"description": "Deep groove ball bearing 6204", "hsn_sac": "84821090", "unit": "NOS", "price_min": 160, "price_max": 390, "gst_rate": 18},
    {"description": "Corrugated packing carton 5 ply", "hsn_sac": "48191010", "unit": "NOS", "price_min": 25, "price_max": 75, "gst_rate": 12},
    {"description": "Office notebook - ruled 200 pages", "hsn_sac": "48202000", "unit": "NOS", "price_min": 35, "price_max": 95, "gst_rate": 12},
    {"description": "Desktop computer - business series", "hsn_sac": "84715000", "unit": "NOS", "price_min": 24000, "price_max": 48000, "gst_rate": 18},
    {"description": "IT maintenance service - monthly", "hsn_sac": "998313", "unit": "JOB", "price_min": 1800, "price_max": 6200, "gst_rate": 18},
    {"description": "Cotton fabric - plain weave", "hsn_sac": "52081190", "unit": "MTR", "price_min": 65, "price_max": 160, "gst_rate": 5},
]
# Coherent MSME catalogs. Rates are illustrative historical training inputs.
# Each tuple is description, HSN/SAC, unit, min price, max price, GST percent.
SECTOR_ROWS = {
    "hardware": [
        ("Hex bolt and nut set M10", "73181500", "SET", 12, 38, 18),
        ("Deep groove ball bearing 6204", "84821090", "NOS", 160, 390, 18),
        ("MS pipe 25 mm - commercial grade", "73063090", "MTR", 110, 220, 18),
        ("Welding electrode 3.15 mm box", "83111000", "BOX", 420, 750, 18),
        ("Cutting wheel 4 inch", "68042290", "NOS", 18, 45, 18),
    ],
    "electrical": [
        ("Copper insulated cable 1.5 sq mm", "85444999", "MTR", 24, 65, 18),
        ("Modular switch 6A one-way", "85365090", "NOS", 35, 80, 18),
        ("MCB single pole 32A", "85362030", "NOS", 120, 290, 18),
        ("LED bulb 9W warm white", "85395000", "NOS", 70, 130, 12),
        ("Ceiling fan 1200 mm", "84145120", "NOS", 1100, 2300, 18),
    ],
    "stationery": [
        ("A4 copier paper 75 GSM - 500 sheets", "48025690", "REAM", 210, 340, 12),
        ("Ball point pen - blue ink box", "96081019", "BOX", 80, 180, 18),
        ("Lever arch file - office series", "48203000", "NOS", 75, 150, 18),
        ("Office notebook - ruled 200 pages", "48202000", "NOS", 35, 95, 12),
        ("Printer toner cartridge - black", "84439959", "NOS", 1300, 3200, 18),
    ],
    "textiles": [
        ("Cotton fabric - plain weave", "52081190", "MTR", 65, 160, 5),
        ("Mens cotton shirt - assorted sizes", "62052000", "PCS", 375, 875, 5),
        ("Cotton bedsheet single size", "63023100", "PCS", 250, 650, 5),
        ("Cotton towel standard 60 x 120 cm", "63026000", "PCS", 80, 190, 5),
        ("Polyester sewing thread cone", "54011000", "NOS", 45, 100, 12),
    ],
    "fmcg": [
        ("Packaged rice 5 kg bag", "10063090", "BAG", 230, 390, 5),
        ("Tea leaves 250 g packet", "09023020", "PKT", 80, 150, 5),
        ("Sunflower oil 1 litre pouch", "15121910", "PKT", 95, 150, 5),
        ("Bath soap 100 g - pack of four", "34011190", "PKT", 70, 140, 18),
        ("Laundry detergent 1 kg packet", "34022090", "PKT", 65, 180, 18),
    ],
    "pharmacy": [
        ("Paracetamol 500 mg - strip of 10", "30049099", "STRIP", 12, 28, 12),
        ("ORS powder sachet 21.8 g", "30049099", "PKT", 12, 22, 12),
        ("Sterile gauze dressing pack", "30059090", "PKT", 25, 65, 12),
        ("Adhesive bandage box", "30051090", "BOX", 40, 110, 12),
        ("Antiseptic liquid 100 ml bottle", "30049099", "BTL", 35, 70, 12),
    ],
    "auto_parts": [
        ("Engine oil filter - passenger car", "84212300", "NOS", 120, 390, 18),
        ("Brake pad set - front axle", "87083000", "SET", 650, 1800, 28),
        ("Spark plug - standard series", "85111000", "NOS", 95, 240, 28),
        ("Wiper blade pair 18 inch", "85124000", "PAIR", 190, 480, 28),
        ("Drive belt - automotive", "40103999", "NOS", 140, 420, 18),
    ],
    "services": [
        ("IT maintenance service - monthly", "998313", "JOB", 1800, 6200, 18),
        ("Computer repair and labour charges", "998713", "JOB", 450, 2100, 18),
        ("Design and artwork service", "998391", "JOB", 900, 4500, 18),
        ("Office equipment servicing", "998719", "JOB", 800, 3800, 18),
        ("Network installation labour", "998313", "JOB", 1200, 5200, 18),
    ],
}
SECTOR_CATALOGS = {name: [dict(zip(("description", "hsn_sac", "unit", "price_min", "price_max", "gst_rate"), row)) for row in rows] for name, rows in SECTOR_ROWS.items()}
MSME_SECTORS = tuple(SECTOR_CATALOGS)
PREFIXES = ("Shree", "Sri", "Om", "Jai", "New", "Royal", "Bharat", "Nav")
BRANDS = ("Kavya", "Nirmal", "Sagar", "Uday", "Aarav", "Pragati", "Vardhan", "Kiran", "Suman", "Navrang", "Deepak", "Aakash", "Sarthak", "Vikas", "Anmol", "Riddhi", "Siddhi", "Vihan", "Surya", "Tarang")
SUFFIXES = ("Traders", "Enterprises", "Industries", "Distributors", "Agencies", "Supplies", "Trading Co.", "Solutions")
CENT = Decimal("0.01")


def seeded(*parts) -> int:
    """Stable across Python processes and machines (unlike built-in hash)."""
    return int.from_bytes(hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).digest()[:8], "big")


def dec(value) -> Decimal:
    return Decimal(str(value))


def quant(value) -> Decimal:
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def amount(value) -> str:
    return f"{quant(value):.2f}"


def indian_money(value) -> str:
    value = quant(value)
    sign = "-" if value < 0 else ""
    whole, fraction = f"{abs(value):.2f}".split(".")
    tail = whole[-3:]
    lead = whole[:-3]
    groups = []
    while lead:
        groups.insert(0, lead[-2:])
        lead = lead[:-2]
    return sign + (",".join(groups) + "," if groups else "") + tail + "." + fraction


def integer_words(n: int) -> str:
    small = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen").split()
    tens = ("Zero Ten Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety").split()
    if n < 0:
        return "Minus " + integer_words(-n)
    if n < 20:
        return small[n]
    if n < 100:
        return tens[n // 10] + (" " + small[n % 10] if n % 10 else "")
    for divisor, label in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand"), (100, "Hundred")):
        if n >= divisor:
            return integer_words(n // divisor) + " " + label + (" " + integer_words(n % divisor) if n % divisor else "")
    raise AssertionError(n)


def rupee_words(value) -> str:
    total_paise = int(quant(value) * 100)
    rupees, paise = divmod(total_paise, 100)
    return "Indian Rupees " + integer_words(rupees) + (" and " + integer_words(paise) + " Paise" if paise else "") + " Only"


def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}-{(start + 1) % 100:02d}"


def make_party(run_seed: int, split: str, slot: int, sector: str, state=None) -> dict:
    r = random.Random(seeded(run_seed, split, slot, sector, "party"))
    code, state_name, city, pin = state or r.choice(STATES)
    base = f"{r.choice(PREFIXES)} {r.choice(BRANDS)}"
    suffix = {
        "electricity": "Power Services", "water": "Water Services", "gas": "Gas Services",
        "internet": "Broadband Services", "telephone": "Telecom Services",
        "meals": "Food Corner", "travel": "Travel Services", "fuel": "Fuel Centre",
        "hardware": "Hardware & Tools", "electrical": "Electricals", "stationery": "Stationers",
        "textiles": "Textile Traders", "fmcg": "Consumer Distributors", "pharmacy": "Medical Distributors",
        "auto_parts": "Auto Spares", "services": "Business Services",
    }.get(sector.split(":")[0], r.choice(SUFFIXES))
    # PAN entity character X makes this explicitly non-registration test data.
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    pan = "".join(r.choices(letters, k=3)) + "X" + r.choice(letters) + f"{r.randrange(10000):04d}" + r.choice(letters)
    party_id = "P" + hashlib.sha256(f"{run_seed}:{split}:{sector}:{slot}:{code}".encode()).hexdigest()[:16]
    return {
        "party_id": party_id, "name": f"{base} {suffix}",
        "address": f"{r.randint(1, 190)}, {r.choice(('Market Road', 'Industrial Estate', 'Station Road', 'Commercial Complex', 'Transport Nagar'))}",
        "city": city, "state": state_name, "state_code": code, "pincode": pin,
        "gstin": code + pan + "1Z0", "pan": pan,
        "phone": "00000 " + f"{r.randrange(100000):05d}",
        "email": f"accounts.{party_id[-6:].lower()}@example.invalid",
        "bank": "Demonstration Bank", "account_number": "0000" + f"{r.randrange(100000000):08d}",
        "ifsc": "TEST0" + f"{r.randrange(1000000):06d}", "synthetic": True,
    }


def calculate_items(raw_items: list[dict], tax_regime: str, rounded: bool = True) -> tuple[list, dict, list]:
    """Round line tax components independently; totals are sums of printed lines."""
    lines = []
    rate_summary = defaultdict(lambda: {k: Decimal(0) for k in ("taxable_value", "cgst", "sgst", "igst")})
    sums = {k: Decimal(0) for k in ("gross", "discount", "taxable_value", "cgst", "sgst", "igst")}
    for i, source in enumerate(raw_items):
        row = dict(source)
        gross = quant(dec(row["quantity"]) * dec(row["unit_price"]))
        discount = quant(gross * dec(row.get("discount_percent", 0)) / 100)
        base = gross - discount
        rate = dec(row["gst_rate"]) if tax_regime in ("intra_state", "inter_state") else Decimal(0)
        cgst = quant(base * rate / 200) if tax_regime == "intra_state" else Decimal(0)
        sgst = cgst
        igst = quant(base * rate / 100) if tax_regime == "inter_state" else Decimal(0)
        values = {"gross": gross, "discount": discount, "taxable_value": base, "cgst": cgst, "sgst": sgst, "igst": igst}
        row.update({k: amount(v) for k, v in values.items()})
        row.update({"line_number": i + 1, "quantity": str(row["quantity"]), "unit_price": amount(row["unit_price"]), "gst_rate": str(rate), "discount_percent": str(row.get("discount_percent", 0)), "total": amount(base + cgst + sgst + igst)})
        for k, v in values.items():
            sums[k] += v
        for k in ("taxable_value", "cgst", "sgst", "igst"):
            rate_summary[str(rate)][k] += values[k]
        lines.append(row)
    sums["tax_total"] = sums["cgst"] + sums["sgst"] + sums["igst"]
    sums["pre_round_total"] = sums["taxable_value"] + sums["tax_total"]
    grand = sums["pre_round_total"].quantize(Decimal("1"), rounding=ROUND_HALF_UP) if rounded else sums["pre_round_total"]
    sums["round_off"] = grand - sums["pre_round_total"]
    sums["grand_total"] = grand
    summaries = [{"gst_rate": rate, **{k: amount(v) for k, v in data.items()}} for rate, data in sorted(rate_summary.items(), key=lambda pair: dec(pair[0]))]
    return lines, {k: amount(v) for k, v in sums.items()}, summaries


def raw_line(description, quantity, unit_price, unit="NOS", hsn_sac="", gst_rate=0, discount_percent=0):
    return {"description": description, "quantity": str(quantity), "unit_price": amount(unit_price), "unit": unit, "hsn_sac": hsn_sac, "gst_rate": str(gst_rate), "discount_percent": str(discount_percent)}


def make_document(kind: str, index: int, split: str, config: dict) -> dict:
    r = random.Random(seeded(config["seed"], kind, index, "content"))
    start, end = date.fromisoformat(config["start_date"]), date.fromisoformat(config["end_date"])
    issued = start + timedelta(days=r.randrange((end - start).days + 1))
    allowed = [x for x in LAYOUTS[kind] if x in config["templates"]]
    template = allowed[index % len(allowed)]
    subtype = "general"
    if kind == "expense_receipt":
        subtype = ("meals", "travel", "fuel", "office_supplies")[index % 4]
    elif kind == "utility_bill":
        subtype = ("electricity", "water", "internet", "telephone", "gas")[index % 5]
    sector = subtype if subtype != "general" else "merchant"
    selected_catalog = config["catalog"]
    if subtype == "general" and not config.get("custom_catalog", False):
        sectors = config.get("sectors", list(MSME_SECTORS))
        sector = sectors[(index + index // len(allowed)) % len(sectors)]
        if template == "batch_mrp":
            batch_sectors = [s for s in sectors if s in ("pharmacy", "fmcg")]
            if batch_sectors:
                sector = batch_sectors[(index // len(allowed)) % len(batch_sectors)]
        selected_catalog = SECTOR_CATALOGS[sector]
    slot = r.randrange(config["suppliers_per_split"])
    seller = make_party(config["seed"], split, slot, sector)
    seller_state = next(s for s in STATES if s[0] == seller["state_code"])
    local = kind in ("expense_receipt", "utility_bill") or r.random() < 0.7
    buyer_state = seller_state if local else r.choice([s for s in STATES if s[0] != seller["state_code"]])
    buyer = make_party(config["seed"], split, r.randrange(config["suppliers_per_split"]), "buyer", buyer_state)
    regime = "intra_state" if local else "inter_state"
    title, visual_type = "TAX INVOICE", "tax_invoice"
    if kind == "purchase_bill":
        treatment = random.Random(seeded(config["seed"], split, slot, "purchase_status")).choices(("gst", "composition", "unregistered"), (0.65, 0.2, 0.15))[0]
        seller = make_party(config["seed"], split, slot, sector + ":purchase_" + treatment, seller_state)
        if treatment == "composition":
            title, visual_type, regime = "BILL OF SUPPLY", "bill_of_supply", "composition"
            if not local:
                buyer = make_party(config["seed"], split, r.randrange(config["suppliers_per_split"]), "buyer", seller_state)
                local = True
        elif treatment == "unregistered":
            title, visual_type, regime = r.choice(("CASH BILL", "RETAIL BILL")), "non_gst_bill", "unregistered"
            seller["gstin"] = None
    elif kind in ("credit_note", "debit_note"):
        title = kind.replace("_", " ").upper()
        visual_type = kind
    elif kind == "expense_receipt":
        title, visual_type = ("PAYMENT VOUCHER", "expense_voucher") if template == "expense_voucher" else (r.choice(("CASH RECEIPT", "PAYMENT RECEIPT", "CASH MEMO")), "receipt")
    elif kind == "utility_bill":
        title, visual_type = f"{subtype.upper()} BILL", "utility_bill"
    if kind == "gst_invoice" and r.random() < 0.35:
        title = "GST TAX INVOICE"
    prefix = {"gst_invoice": "INV", "purchase_bill": "BIL", "expense_receipt": "RCP", "utility_bill": "UTL", "credit_note": "CN", "debit_note": "DN"}[kind]
    if kind in ("gst_invoice", "purchase_bill"):
        prefix = r.choice(("INV", "GST", "BIL"))
    number = f"{prefix}/{financial_year(issued)}/{index + 1:05d}"
    raw = []
    extra = {}
    if kind in ("gst_invoice", "purchase_bill", "credit_note", "debit_note"):
        n = r.randint(1, config["max_items"])
        if kind in ("credit_note", "debit_note"):
            n = min(n, 4)
        for item in r.choices(selected_catalog, k=n):
            price = quant(Decimal(r.randint(int(dec(item["price_min"]) * 100), int(dec(item["price_max"]) * 100))) / 100)
            quantity = r.randint(1, 12 if dec(item["price_max"]) > 10000 else 45)
            if item["unit"] == "JOB":
                quantity = r.randint(1, 4)
            description = item["description"]
            if kind == "debit_note":
                description += " - adjustment"
                price = quant(price / r.randint(2, 5))
            raw.append(raw_line(description, quantity, price, item["unit"], item["hsn_sac"], item["gst_rate"], r.choice((0, 0, 0, 2, 5, 10))))
            if template == "batch_mrp":
                raw[-1].update({"batch_number": f"B{issued.year % 100:02d}{r.randrange(100000):05d}",
                    "expiry": (issued + timedelta(days=r.randint(180, 720))).isoformat() if sector in ("pharmacy", "fmcg") else None,
                    "mrp": amount((price * (1 + dec(item["gst_rate"]) / 100) * dec(r.choice(("1.08", "1.15", "1.25")))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))})
        extra.update({"purchase_order": f"PO/{financial_year(issued)}/{r.randint(1, 9999):04d}", "delivery_note": f"DC/{r.randint(1, 99999):05d}", "transport": r.choice(("By Road", "Local Delivery", "Self Collection")), "reverse_charge": False})
        extra.update({"payment_terms": r.choice(("Cash", "7 days", "15 days", "30 days")), "msme_sector": sector})
        extra["due_date"] = (issued + timedelta(days=int(extra["payment_terms"].split()[0]) if extra["payment_terms"] != "Cash" else 0)).isoformat()
        if kind in ("credit_note", "debit_note"):
            ref_date = issued - timedelta(days=r.randint(3, 70))
            extra["reference_invoice"] = {"number": f"INV/{financial_year(ref_date)}/{r.randint(1, 99999):05d}", "date": ref_date.isoformat()}
            extra["reason"] = r.choice(("Goods returned - damaged packing", "Post-sale price reduction", "Short quantity accepted by customer")) if kind == "credit_note" else r.choice(("Rate difference on original invoice", "Additional agreed service charges", "Short billing adjustment"))
    elif kind == "expense_receipt":
        if subtype == "meals":
            raw = [raw_line("Veg thali / working lunch", r.randint(1, 6), r.randint(120, 240), "NOS", "996331", 5), raw_line("Tea and refreshments", r.randint(1, 6), r.randint(20, 45), "NOS", "996331", 5)]
        elif subtype == "fuel":
            raw = [raw_line(r.choice(("Petrol - motor spirit", "High speed diesel")), f"{r.uniform(5, 30):.3f}", f"{r.uniform(85, 112):.2f}", "LTR", "2710")]
            regime = "not_separately_charged"
            extra["tax_note"] = "Pump price includes applicable local levies."
        elif subtype == "travel":
            raw = [raw_line("Local travel - office duty", r.randint(1, 4), r.randint(120, 600), "TRIP")]
            regime = "not_separately_charged"
        else:
            for item in r.sample(config["catalog"][:5], min(3, len(config["catalog"][:5]))):
                raw.append(raw_line(item["description"], r.randint(1, 3), item["price_min"], item["unit"], item["hsn_sac"], item["gst_rate"]))
        extra.update({"employee": r.choice(("Amit Kumar", "Priya Shah", "Kiran Rao", "Neha Verma", "Arun Nair", "Sana Khan")), "department": r.choice(("Administration", "Operations", "Sales", "Accounts")), "expense_category": subtype, "payment_mode": r.choice(("Cash", "UPI", "Debit Card", "Bank Transfer")), "payment_reference": "DEMO" + f"{r.randrange(10**8):08d}"})
    else:
        period_start, period_end = issued - timedelta(days=30), issued - timedelta(days=1)
        extra.update({"consumer_number": f"{r.randrange(10**9, 10**10):010d}", "period_start": period_start.isoformat(), "period_end": period_end.isoformat(), "due_date": (issued + timedelta(days=15)).isoformat(), "utility_type": subtype, "tariff_category": "Commercial / General", "arrears": "0.00"})
        if subtype in ("electricity", "water", "gas"):
            regime = "not_separately_charged"
            units = r.randint(100, 850) if subtype == "electricity" else r.randint(10, 75)
            previous = r.randint(1200, 28000)
            extra.update({"meter_number": f"MTR{r.randrange(10**7):07d}", "previous_reading": str(previous), "current_reading": str(previous + units), "consumption": str(units), "consumption_unit": {"electricity": "kWh", "water": "KL", "gas": "SCM"}[subtype]})
            unit_rate = {"electricity": "8.40", "water": "18.00", "gas": "43.50"}[subtype]
            raw = [raw_line("Consumption charges", units, unit_rate, extra["consumption_unit"]), raw_line("Fixed / service charges", 1, r.choice((60, 100, 125)), "MONTH"), raw_line("Meter service charges", 1, r.choice((10, 20, 30)), "MONTH")]
        else:
            extra["plan"] = "Business broadband 100 Mbps" if subtype == "internet" else "Business voice monthly plan"
            raw = [raw_line(extra["plan"], 1, r.choice((499, 699, 799, 999)), "MONTH", "9984", 18), raw_line("Equipment / usage charges", 1, r.choice((49, 99, 149)), "MONTH", "9984", 18)]
    items, totals, tax_summary = calculate_items(raw, regime, rounded=r.random() < 0.75)
    signed = -dec(totals["grand_total"]) if kind == "credit_note" else dec(totals["grand_total"])
    context = {"direction": "purchase" if kind in ("purchase_bill", "expense_receipt", "utility_bill") else "sale", "tenant_party_id": buyer["party_id"] if kind in ("purchase_bill", "expense_receipt", "utility_bill") else seller["party_id"], "issuer_role": "supplier", "receivable_adjustment_sign": -1 if kind == "credit_note" else 1 if kind == "debit_note" else None}
    if kind == "expense_receipt" and template == "expense_voucher":
        context["issuer_role"] = "buyer"
    return {"document_type": kind, "visual_document_type": visual_type, "template": template, "subtype": subtype, "title": title, "document_number": number, "date": issued.isoformat(), "date_format": r.choice(("%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y")), "currency": "INR", "currency_symbol": r.choice(("Rs.", "INR", "₹")), "supplier": seller, "buyer": buyer, "place_of_supply": {"state": buyer["state"], "state_code": buyer["state_code"]}, "tax_regime": regime, "items": items, "totals": totals, "tax_summary": tax_summary, "amount_in_words": rupee_words(totals["grand_total"]), "signed_accounting_amount": amount(signed), "business_context": context, "extra": extra, "synthetic": True}


def display_date(doc, key="date", value=None):
    return date.fromisoformat(value or doc[key]).strftime(doc["date_format"])


@lru_cache(maxsize=64)
def font_path(family: str, bold: bool, font_dir: str | None) -> str:
    names = {"sans": "DejaVuSans", "serif": "DejaVuSerif", "mono": "DejaVuSansMono"}
    name = names[family] + ("-Bold" if bold else "") + ".ttf"
    roots = ([Path(font_dir)] if font_dir else []) + [Path(__file__).resolve().parent / "fonts", Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/local/share/fonts"), Path.home() / ".fonts", Path("C:/Windows/Fonts"), Path("/Library/Fonts")]
    for root in roots:
        if (root / name).is_file():
            return str(root / name)
    # Arial/Courier/Times fallbacks make the single .py file useful on Windows/macOS.
    alternatives = {"sans": ("arialbd.ttf", "arial.ttf"), "mono": ("courbd.ttf", "cour.ttf"), "serif": ("timesbd.ttf", "times.ttf")}
    for root in roots:
        candidate = root / alternatives[family][0 if bold else 1]
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"Missing {name}. Use the supplied fonts/ folder or pass --font-dir PATH.")


@lru_cache(maxsize=512)
def load_font(path: str, size: int):
    # BASIC disables complex shaping; this English-only renderer exports word boxes.
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)


class LayoutError(ValueError):
    pass


class Canvas:
    """Logical layout units, actual pixel text bounds, annotation-aware primitives."""
    def __init__(self, width, height, dpi, width_mm, family="sans", font_dir=None, ink="#202020", accent="#242424", paper="#ffffff"):
        self.width, self.height = width, height
        self.scale = round(width_mm / 25.4 * dpi) / width
        self.image = Image.new("RGB", (round(width * self.scale), round(height * self.scale)), paper)
        self.draw = ImageDraw.Draw(self.image)
        self.family, self.font_dir, self.ink, self.accent = family, font_dir, ink, accent
        self.lines, self.words, self.regions = [], [], []

    def font(self, size, bold=False):
        return load_font(font_path(self.family, bold, self.font_dir), max(7, round(size * self.scale)))

    def measure(self, text, size=14, bold=False):
        return self.font(size, bold).getlength(str(text)) / self.scale

    def text(self, x, y, text, field="", role="value", size=14, bold=False, width=None, align="left", color=None):
        text = str(text)
        if not text:
            return y
        while width is not None and self.measure(text, size, bold) > width and size > 8.5:
            size -= 0.5
        if width is not None and self.measure(text, size, bold) > width + 0.5:
            raise LayoutError(f"Text does not fit field {field!r}: {text!r}; shorten custom content.")
        font = self.font(size, bold)
        xpos = x * self.scale
        tw = font.getlength(text)
        if width is not None:
            xpos += (width * self.scale - tw) * ({"left": 0, "center": 0.5, "right": 1}[align])
        ascent, _ = font.getmetrics()
        baseline = y * self.scale + ascent
        box = list(self.draw.textbbox((xpos, baseline), text, font=font, anchor="ls"))
        if box[0] < -0.1 or box[1] < -0.1 or box[2] > self.image.width + 0.1 or box[3] > self.image.height + 0.1:
            raise LayoutError(f"Text outside page: {field}: {text!r}, {box}")
        self.draw.text((xpos, baseline), text, fill=color or self.ink, font=font, anchor="ls")
        line_id = len(self.lines)
        self.lines.append({"id": line_id, "text": text, "field": field, "role": role, "source_bbox": box, "font_size_px": font.size})
        for match in re.finditer(r"\S+", text):
            wx = xpos + font.getlength(text[:match.start()])
            word_box = list(self.draw.textbbox((wx, baseline), match.group(), font=font, anchor="ls"))
            self.words.append({"id": len(self.words), "line_id": line_id, "text": match.group(), "field": field, "role": role, "source_bbox": word_box})
        return y + size * 1.4

    def wrap_lines(self, text, width, size=14, bold=False):
        result = []
        for paragraph in str(text).split("\n"):
            line = ""
            for word in paragraph.split():
                trial = (line + " " + word).strip()
                if line and self.measure(trial, size, bold) > width:
                    result.append(line)
                    line = word
                else:
                    line = trial
            result.append(line)
        return result

    def paragraph(self, x, y, text, width, field="", role="value", size=14, bold=False, leading=None):
        for line in self.wrap_lines(text, width, size, bold):
            self.text(x, y, line, field, role, size, bold, width)
            y += leading or size * 1.5
        return y

    def line(self, x1, y1, x2, y2, color=None, weight=0.8):
        self.draw.line(tuple(v * self.scale for v in (x1, y1, x2, y2)), fill=color or self.ink, width=max(1, round(weight * self.scale)))

    def rect(self, x, y, width, height, fill=None, outline=True, weight=0.8):
        self.draw.rectangle(tuple(v * self.scale for v in (x, y, x + width, y + height)), fill=fill, outline=self.ink if outline else None, width=max(1, round(weight * self.scale)))

    def region(self, x, y, width, height, label):
        self.regions.append({"label": label, "source_bbox": [v * self.scale for v in (x, y, x + width, y + height)]})

    def kv(self, x, y, label, value, width, field, size=13, gap=None):
        gap = gap or min(width * 0.45, self.measure(label, size, True) + 10)
        self.text(x, y, label, field, "key", size, True, gap - 5)
        self.text(x + gap, y, value, field, "value", size, False, width - gap)


def party_block(c, party, x, y, width, label, field, compact=False):
    c.text(x, y, label, field, "key", 12, True, width)
    y += 22
    y = c.paragraph(x, y, party["name"], width, field + ".name", size=18 if field == "supplier" and not compact else 15, bold=True)
    y = c.paragraph(x, y + 3, party["address"], width, field + ".address", size=12.5)
    c.text(x, y, f"{party['city']} - {party['pincode']}, {party['state']}", field + ".city_state_pin", size=12.5, width=width)
    y += 20
    if party.get("gstin"):
        c.kv(x, y, "GSTIN/UIN:", party["gstin"], width, field + ".gstin", size=12.5)
    else:
        c.text(x, y, "Unregistered supplier", field + ".registration", size=12)
    y += 20
    c.kv(x, y, "State code:", party["state_code"], width, field + ".state_code", size=12)
    return y + 20


def item_table(c, doc, y, x=50, width=900, min_body=230):
    weights = (32, 270, 76, 60, 48, 104, 62, 66, 182)
    widths = [w * width / 900 for w in weights]
    labels = ("Sl.", "Description of Goods / Services", "HSN/SAC", "Qty", "Unit", "Rate", "Disc %", "GST %", "Amount")
    fields = ("line_number", "description", "hsn_sac", "quantity", "unit", "unit_price", "discount_percent", "gst_rate", "taxable_value")
    header_height = 34
    row_heights = [max(38, 16 * len(c.wrap_lines(row["description"], widths[1] - 14, 12.5)) + 14) for row in doc["items"]]
    body_height = max(min_body, sum(row_heights) + 12)
    bottom = y + header_height + body_height
    c.rect(x, y, width, header_height, fill="#ededed")
    c.rect(x, y, width, header_height + body_height)
    xpos = x
    for label, cell_width in zip(labels, widths):
        c.text(xpos + 5, y + 8, label, "table.header", "key", 11.5, True, cell_width - 10, "center" if label != labels[1] else "left")
        c.line(xpos, y, xpos, bottom)
        xpos += cell_width
    cursor = y + header_height
    for i, (row, row_height) in enumerate(zip(doc["items"], row_heights)):
        xpos = x
        for field, cell_width in zip(fields, widths):
            val = row[field]
            if field in ("unit_price", "taxable_value"):
                val = indian_money(val)
            if field == "description":
                c.paragraph(xpos + 7, cursor + 9, val, cell_width - 14, f"items.{i}.{field}", size=12.5, leading=16)
            else:
                c.text(xpos + 5, cursor + 9, val, f"items.{i}.{field}", size=12, width=cell_width - 10, align="right" if field not in ("unit", "hsn_sac", "line_number") else "center")
            xpos += cell_width
        cursor += row_height
        if doc["template"] != "erp_continuous":
            c.line(x, cursor, x + width, cursor, color="#b0b0b0", weight=0.5)
    c.region(x, y, width, bottom - y, "line_items")
    return bottom


def total_pairs(doc):
    pairs = [("Gross amount", "gross"), ("Less: Discount", "discount"), ("Assessable value" if doc["tax_regime"] in ("intra_state", "inter_state") else "Sub-total", "taxable_value")]
    if doc["tax_regime"] == "intra_state":
        pairs += [("CGST", "cgst"), ("SGST", "sgst")]
    elif doc["tax_regime"] == "inter_state":
        pairs += [("IGST", "igst")]
    pairs.append(("Round off", "round_off"))
    return pairs


def invoice_summary(c, doc, y):
    h = max(200, 35 + 23 * (len(total_pairs(doc)) + 1))
    word_height = len(c.wrap_lines("Amount in words: " + doc["amount_in_words"], 510, 11.5)) * 17
    if doc["tax_regime"] in ("intra_state", "inter_state"):
        h = max(h, 39 + 22 + 21 * len(doc["tax_summary"]) + 12 + word_height + 12)
    c.rect(50, y, 900, h)
    c.line(590, y, 590, y + h)
    c.text(62, y + 12, "GST RATE SUMMARY" if doc["tax_regime"] in ("intra_state", "inter_state") else "BILL DETAILS", "tax_summary", "key", 12, True)
    sy = y + 39
    if doc["tax_regime"] in ("intra_state", "inter_state"):
        headers = ("GST %", "Taxable value", "CGST", "SGST", "IGST")
        xs, ws = (64, 124, 263, 369, 475), (50, 128, 95, 95, 100)
        for head, xx, ww in zip(headers, xs, ws):
            c.text(xx, sy, head, "tax_summary.header", "key", 10.5, True, ww, "right")
        sy += 22
        for i, row in enumerate(doc["tax_summary"]):
            for field, xx, ww in zip(("gst_rate", "taxable_value", "cgst", "sgst", "igst"), xs, ws):
                val = row[field] if field == "gst_rate" else indian_money(row[field])
                c.text(xx, sy, val, f"tax_summary.{i}.{field}", size=11, width=ww, align="right")
            sy += 21
    elif doc["tax_regime"] == "composition":
        sy = c.paragraph(64, sy, "Composition taxable person, not eligible to collect tax on supplies.", 510, "tax_note", size=12)
    else:
        sy = c.paragraph(64, sy, "Tax is not separately charged on this bill.", 510, "tax_note", size=12)
    c.paragraph(64, sy + 12, "Amount in words: " + doc["amount_in_words"], 510, "amount_in_words", size=11.5, leading=17)
    ty = y + 12
    for label, field in total_pairs(doc):
        c.text(606, ty, label, "totals." + field, "key", 13)
        c.text(775, ty, indian_money(doc["totals"][field]), "totals." + field, size=13, width=160, align="right")
        ty += 23
    c.line(590, ty + 1, 950, ty + 1)
    total_label = "Credit total" if doc["document_type"] == "credit_note" else "Debit total" if doc["document_type"] == "debit_note" else "Grand total"
    c.text(606, ty + 8, total_label, "totals.grand_total", "key", 15, True)
    c.text(757, ty + 8, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=16, bold=True, width=178, align="right")
    c.region(590, y, 360, h, "totals")
    return y + h


def footer(c, doc, y, width=900, x=50):
    if y + 153 > c.height - 25:
        raise LayoutError("Page content is too long; lower --max-items or shorten catalog descriptions.")
    c.line(x, y, x + width, y)
    c.text(x + 10, y + 10, "Bank details", "supplier.bank", "key", 12, True)
    c.text(x + 10, y + 32, doc["supplier"]["bank"], "supplier.bank", size=12, width=width * .54)
    c.text(x + 10, y + 52, "A/c: " + doc["supplier"]["account_number"] + "   IFSC: " + doc["supplier"]["ifsc"], "supplier.bank_details", size=11.5, width=width * .55)
    c.text(x + width * .64, y + 12, "For " + doc["supplier"]["name"], "signature.issuer", size=12, bold=True, width=width * .35, align="center")
    c.line(x + width * .69, y + 66, x + width * .95, y + 66)
    c.text(x + width * .64, y + 73, "Authorised Signatory", "signature.caption", size=11.5, width=width * .35, align="center")
    c.paragraph(x + 10, y + 86, "Declaration: The above particulars and values are as stated. E. & O.E.\nSubject to " + doc["supplier"]["city"] + " jurisdiction.", width * .61, "declaration", size=10.5, leading=16)
    c.text(x, y + 132, "SYNTHETIC TRAINING SAMPLE - NOT VALID FOR ACCOUNTING", "synthetic_marker", "other", 9, width=width, align="center", color="#666666")


def render_invoice(doc, config, rng):
    style = doc["template"]
    family = "mono" if style == "erp_continuous" else rng.choice(("sans", "serif"))
    accent = rng.choice(("#233d50", "#353535", "#365144"))
    c = Canvas(1000, 1414, config["dpi"], 210, family, config["font_dir"], accent=accent)
    if style == "erp_continuous":
        for yy in range(38, 1390, 30):
            for xx in (18, 982):
                c.draw.ellipse(tuple(v * c.scale for v in (xx - 4, yy - 4, xx + 4, yy + 4)), outline="#b3b3b3", fill="#ededed")
        c.line(35, 30, 35, 1380, color="#bcbcbc")
        c.line(965, 30, 965, 1380, color="#bcbcbc")
    c.text(50, 30, doc["title"], "title", size=24, bold=True, width=900, align="center")
    c.text(50, 66, rng.choice(("ORIGINAL FOR RECIPIENT", "DUPLICATE COPY", "Office Copy")), "copy_type", "other", 10, width=900, align="right")
    if style == "erp_letterhead":
        c.rect(50, 96, 6, 168, fill=accent, outline=False)
        party_block(c, doc["supplier"], 72, 99, 498, "SUPPLIER", "supplier")
        c.rect(610, 99, 340, 161, fill="#f3f5f5", outline=False)
        mx, my, mw = 624, 113, 310
        party_y, table_y = 284, 474
    else:
        c.rect(50, 94, 900, 172)
        c.line(595, 94, 595, 266)
        party_block(c, doc["supplier"], 63, 103, 515, "Supplier", "supplier")
        mx, my, mw = 608, 109, 329
        party_y, table_y = 266, 454
    for label, val, field in (("Document No.", doc["document_number"], "document_number"), ("Dated", display_date(doc), "date"), ("Order No.", doc["extra"]["purchase_order"], "extra.purchase_order"), ("Delivery Note", doc["extra"]["delivery_note"], "extra.delivery_note"), ("Despatch", doc["extra"]["transport"], "extra.transport"), ("Reverse charge", "No", "extra.reverse_charge")):
        c.kv(mx, my, label, val, mw, field, size=12)
        my += 23
    c.region(50, 94, 545, 172, "supplier")
    c.region(595, 94, 355, 172, "document_metadata")
    if style != "erp_letterhead":
        c.rect(50, party_y, 900, 150)
        c.line(510, party_y, 510, party_y + 150)
    party_block(c, doc["buyer"], 63, party_y + 10, 430, "Buyer (Bill to)", "buyer", True)
    if doc["document_type"] in ("credit_note", "debit_note"):
        ref = doc["extra"]["reference_invoice"]
        c.text(524, party_y + 11, "Against original invoice", "extra.reference_invoice", "key", 12, True)
        c.kv(524, party_y + 38, "Invoice No.", ref["number"], 411, "extra.reference_invoice.number", size=12)
        c.kv(524, party_y + 63, "Invoice Date", display_date(doc, value=ref["date"]), 411, "extra.reference_invoice.date", size=12)
        c.paragraph(524, party_y + 91, "Reason: " + doc["extra"]["reason"], 409, "extra.reason", size=12, leading=18)
    else:
        party_block(c, doc["buyer"], 524, party_y + 10, 409, "Consignee (Ship to)", "ship_to", True)
    c.region(50, party_y, 460, 150, "buyer")
    c.text(63, table_y - 27, "Place of supply: " + doc["place_of_supply"]["state"] + " (" + doc["place_of_supply"]["state_code"] + ")", "place_of_supply", size=12)
    c.text(640, table_y - 27, "All amounts in Indian Rupees", "currency", "other", 11.5, width=295, align="right")
    table_end = item_table(c, doc, table_y, min_body=rng.choice((210, 250, 280)))
    summary_end = invoice_summary(c, doc, table_end)
    footer(c, doc, max(summary_end + 15, 1150))
    return c


def receipt_table(c, doc, x, y, width):
    c.line(x, y, x + width, y, weight=1.3)
    c.text(x + 5, y + 8, "Particulars", "table.header", "key", 14, True, width * .57)
    c.text(x + width * .68, y + 8, "Amount", "table.header", "key", 14, True, width * .30, "right")
    y += 40
    for i, row in enumerate(doc["items"]):
        end = c.paragraph(x + 5, y, row["description"], width * .66, f"items.{i}.description", size=14, leading=20)
        c.text(x + width * .71, y, indian_money(row["taxable_value"]), f"items.{i}.taxable_value", size=14, width=width * .27, align="right")
        c.text(x + 5, end + 3, f"{row['quantity']} {row['unit']} x {indian_money(row['unit_price'])}", f"items.{i}.quantity_rate", size=12)
        y = end + 34
    c.line(x, y, x + width, y)
    return y + 14


def render_receipt(doc, config, rng):
    thermal = doc["template"] == "thermal"
    voucher = doc["template"] == "expense_voucher"
    width, height = (560, 1200) if thermal else (1000, 1140)
    c = Canvas(width, height, config["dpi"], 80 if thermal else 148, "mono" if thermal else rng.choice(("sans", "serif")), config["font_dir"], paper=rng.choice(("#ffffff", "#fffcf4")))
    x, w = (27, 506) if thermal else (50, 900)
    y = 35
    issuer_field = "buyer" if voucher else "supplier"
    issuer = doc[issuer_field]
    y = c.paragraph(x, y, issuer["name"].upper(), w, issuer_field + ".name", size=23 if thermal else 25, bold=True)
    y = c.paragraph(x, y + 7, issuer["address"] + ", " + issuer["city"] + " - " + issuer["pincode"], w, issuer_field + ".address", size=13)
    if doc["tax_regime"] == "intra_state":
        y = c.paragraph(x, y + 5, "GSTIN: " + issuer["gstin"], w, issuer_field + ".gstin", size=13)
    y += 17
    c.line(x, y, x + w, y)
    c.text(x, y + 15, doc["title"], "title", size=21, bold=True, width=w, align="center")
    y += 60
    payee_field = "supplier" if voucher else "buyer"
    for label, val, field in (("Voucher No." if voucher else "Receipt No.", doc["document_number"], "document_number"), ("Date", display_date(doc), "date"), ("Paid to" if voucher else "Paid by", doc[payee_field]["name"], payee_field + ".name")):
        c.kv(x, y, label, val, w, field, size=13.5)
        y += 29
    if voucher:
        for label, val, field in (("Employee", doc["extra"]["employee"], "extra.employee"), ("Department", doc["extra"]["department"], "extra.department"), ("Expense Head", doc["subtype"].replace("_", " ").title(), "extra.expense_category")):
            c.kv(x, y, label, val, w, field, size=14)
            y += 29
    y = receipt_table(c, doc, x, y + 15, w)
    pairs = [("Sub-total", "taxable_value")]
    if doc["tax_regime"] == "intra_state":
        for row in doc["tax_summary"]:
            c.text(x + 5, y, f"GST {row['gst_rate']}% on {indian_money(row['taxable_value'])}", "tax_summary", size=11.5, width=w)
            y += 22
        pairs += [("CGST", "cgst"), ("SGST", "sgst")]
    pairs += [("Round off", "round_off")]
    for label, field in pairs:
        c.text(x + 5, y, label, "totals." + field, "key", 14)
        c.text(x + w * .64, y, indian_money(doc["totals"][field]), "totals." + field, size=14, width=w * .34, align="right")
        y += 28
    c.line(x, y, x + w, y, weight=1.5)
    c.text(x + 5, y + 11, "TOTAL PAID", "totals.grand_total", "key", 18, True)
    c.text(x + w * .50, y + 11, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=19, bold=True, width=w * .48, align="right")
    c.region(x, y - 28 * len(pairs), w, 28 * len(pairs) + 42, "totals")
    y = c.paragraph(x + 5, y + 52, doc["amount_in_words"], w - 10, "amount_in_words", size=12, leading=18)
    y += 17
    c.kv(x, y, "Payment mode", doc["extra"]["payment_mode"], w, "extra.payment_mode", size=13)
    c.kv(x, y + 27, "Reference", doc["extra"]["payment_reference"], w, "extra.payment_reference", size=12)
    y += 66
    if doc["extra"].get("tax_note"):
        y = c.paragraph(x, y, doc["extra"]["tax_note"], w, "extra.tax_note", size=11.5, leading=17)
    if voucher:
        c.text(x, y + 12, "Prepared by                 Approved by                 Received by", "signature.caption", "other", 13, width=w)
        y += 54
    else:
        c.text(x, y + 12, "Thank you. Please retain this receipt.", "footer", "other", 12, width=w, align="center")
        y += 48
    c.paragraph(x, y, "SYNTHETIC TRAINING SAMPLE\nNOT VALID FOR ACCOUNTING", w, "synthetic_marker", "other", size=10, leading=16)
    used_height = min(height, y + 60)
    if thermal:
        c.image = c.image.crop((0, 0, c.image.width, round(used_height * c.scale)))
        c.height = used_height
    return c


def render_utility(doc, config, rng):
    c = Canvas(1000, 1414, config["dpi"], 210, rng.choice(("sans", "serif")), config["font_dir"])
    grid = doc["template"] == "utility_grid"
    color = rng.choice(("#193d5c", "#31483c", "#3f3f3f"))
    if grid:
        c.rect(50, 45, 900, 9, fill=color, outline=False)
    c.text(65, 77, doc["supplier"]["name"].upper(), "supplier.name", size=27, bold=True, width=870, color=color)
    c.text(65, 119, doc["supplier"]["address"] + ", " + doc["supplier"]["city"] + " - " + doc["supplier"]["pincode"], "supplier.address", size=13, width=870)
    c.text(65, 146, "Customer care: " + doc["supplier"]["phone"] + "   Email: " + doc["supplier"]["email"], "supplier.contact", size=12, width=870)
    c.text(65, 194, doc["title"], "title", size=25, bold=True, width=870)
    c.rect(50, 244, 900, 201, fill="#f5f6f7" if grid else None)
    party_block(c, doc["buyer"], 65, 258, 490, "Consumer / Service address", "buyer", True)
    extra = doc["extra"]
    for i, (label, val, field) in enumerate((("Bill No.", doc["document_number"], "document_number"), ("Bill Date", display_date(doc), "date"), ("Consumer No.", extra["consumer_number"], "extra.consumer_number"), ("Due Date", display_date(doc, value=extra["due_date"]), "extra.due_date"), ("Category", "Commercial", "extra.tariff_category"))):
        c.kv(580, 263 + 32 * i, label, val, 353, field, size=12.5)
    c.region(50, 244, 900, 201, "consumer_details")
    c.text(65, 471, "Billing period: " + display_date(doc, value=extra["period_start"]) + " to " + display_date(doc, value=extra["period_end"]), "extra.billing_period", size=14)
    c.rect(50, 518, 900, 86, fill="#e9eef1" if grid else "#f5f5f5")
    c.text(69, 539, "AMOUNT PAYABLE", "totals.grand_total", "key", 17, True)
    c.text(554, 534, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=32, bold=True, width=374, align="right")
    if "meter_number" in extra:
        c.text(65, 635, "METER / CONSUMPTION DETAILS", "meter", "key", 13, True)
        c.rect(50, 669, 900, 83)
        entries = (("Meter Number", "meter_number"), ("Previous", "previous_reading"), ("Current", "current_reading"), ("Consumption (" + extra["consumption_unit"] + ")", "consumption"))
        for i, (label, field) in enumerate(entries):
            c.text(65 + i * 224, 682, label, "extra." + field, "key", 12.5, True, 207)
            c.text(65 + i * 224, 714, extra[field], "extra." + field, size=15, width=207)
    else:
        c.text(65, 645, extra["plan"], "extra.plan", size=18, bold=True)
        c.kv(65, 683, "Supplier GSTIN", doc["supplier"]["gstin"], 680, "supplier.gstin", size=13)
        c.kv(65, 714, "Place of supply", doc["buyer"]["state"], 680, "place_of_supply", size=13)
    y = receipt_table(c, doc, 50, 784, 900)
    for label, field in [("Sub-total", "taxable_value")] + ([("CGST", "cgst"), ("SGST", "sgst")] if doc["tax_regime"] == "intra_state" else []) + [("Round off", "round_off")]:
        c.text(580, y, label, "totals." + field, "key", 14)
        c.text(760, y, indian_money(doc["totals"][field]), "totals." + field, size=14, width=175, align="right")
        y += 27
    c.kv(65, y + 12, "Previous balance:", "0.00", 400, "extra.arrears", size=13)
    y = c.paragraph(65, y + 45, doc["amount_in_words"], 865, "amount_in_words", size=13)
    c.paragraph(65, y + 23, "Please quote the consumer number with your payment.\nThis is a computer generated bill. Tariffs shown are illustrative.", 865, "footer", "other", size=12, leading=20)
    c.text(50, 1360, "SYNTHETIC TRAINING SAMPLE - NOT VALID FOR ACCOUNTING", "synthetic_marker", "other", 9, width=900, align="center", color="#666666")
    return c


def detailed_item_table(c, doc, x, y, width, columns, min_body=180):
    """Column-configurable trade table; all new fields retain exact word boxes."""
    total_weight = sum(column[2] for column in columns)
    widths = [width * column[2] / total_weight for column in columns]
    desc_index = next(i for i, col in enumerate(columns) if col[1] == "description")
    desc_width = widths[desc_index] - 12
    row_heights = [max(42, 15 * len(c.wrap_lines(row["description"], desc_width, 12)) + 14) for row in doc["items"]]
    bottom = y + 34 + max(min_body, sum(row_heights) + 10)
    c.rect(x, y, width, 34, fill="#ececec")
    c.rect(x, y, width, bottom - y)
    xx = x
    for (label, field, _), ww in zip(columns, widths):
        c.text(xx + 4, y + 9, label, "table.header", "key", 11, True, ww - 8, "left" if field == "description" else "center")
        c.line(xx, y, xx, bottom)
        xx += ww
    yy = y + 34
    for i, (row, hh) in enumerate(zip(doc["items"], row_heights)):
        xx = x
        for (_, field, _), ww in zip(columns, widths):
            value = row.get(field, "")
            if field == "expiry":
                value = date.fromisoformat(value).strftime("%m/%y") if value else "--"
            elif field in ("mrp", "unit_price", "taxable_value", "cgst", "sgst", "igst", "total") and value != "":
                value = indian_money(value)
            if field == "description":
                c.paragraph(xx + 6, yy + 8, value, ww - 12, f"items.{i}.{field}", size=12, leading=15)
            else:
                c.text(xx + 4, yy + 8, value, f"items.{i}.{field}", size=11.5, width=ww - 8,
                       align="center" if field in ("line_number", "hsn_sac", "unit", "batch_number", "expiry") else "right")
            xx += ww
        yy += hh
        c.line(x, yy, x + width, yy, color="#b0b0b0", weight=.5)
    c.region(x, y, width, bottom - y, "line_items")
    return bottom


def render_trade_invoice(doc, config, rng):
    batch = doc["template"] == "batch_mrp"
    c = Canvas(1000, 1414, config["dpi"], 210 if batch else 148,
               rng.choice(("sans", "serif")), config["font_dir"])
    c.text(50, 30, doc["title"], "title", size=23, bold=True, width=900, align="center")
    c.text(50, 75, doc["supplier"]["name"].upper(), "supplier.name", size=27, bold=True, width=900, align="center")
    c.text(50, 118, doc["supplier"]["address"] + ", " + doc["supplier"]["city"] + " - " + doc["supplier"]["pincode"], "supplier.address", size=14, width=900, align="center")
    c.text(50, 147, "GSTIN: " + (doc["supplier"]["gstin"] or "Unregistered") + "   State: " + doc["supplier"]["state_code"], "supplier.registration", size=14, width=900, align="center")
    c.text(50, 175, "Wholesale / Distribution" if batch else "Trading / Retail", "business_caption", "other", 12, width=900, align="center")
    c.line(50, 204, 950, 204, weight=1.5)
    party_block(c, doc["buyer"], 62, 220, 510, "Billed to", "buyer", True)
    for i, (label, value, field) in enumerate((("Bill No.", doc["document_number"], "document_number"),
            ("Date", display_date(doc), "date"), ("Terms", doc["extra"]["payment_terms"], "extra.payment_terms"),
            ("Order No.", doc["extra"]["purchase_order"], "extra.purchase_order"),
            ("Reverse charge", "No", "extra.reverse_charge"))):
        c.kv(610, 223 + i * 27, label, value, 326, field, size=13)
    c.text(62, 382, "Place of supply: " + doc["buyer"]["state"] + " (" + doc["buyer"]["state_code"] + ")", "place_of_supply", size=13, width=875)
    c.region(50, 70, 900, 135, "supplier")
    c.region(50, 215, 530, 150, "buyer")
    if batch:
        c.text(62, 408, "MRP includes tax. Rate and line amount exclude tax.", "table.price_basis", "other", 11.5)
        cols = (("Sl.", "line_number", 25), ("Product", "description", 190), ("HSN", "hsn_sac", 66),
                ("Batch", "batch_number", 85), ("Exp.", "expiry", 56), ("Qty", "quantity", 43),
                ("Unit", "unit", 47), ("MRP", "mrp", 75), ("Rate", "unit_price", 75),
                ("Disc %", "discount_percent", 47), ("GST %", "gst_rate", 46), ("Amount", "taxable_value", 145))
        end = detailed_item_table(c, doc, 50, 438, 900, cols, min_body=250)
    else:
        end = item_table(c, doc, 424, min_body=260)
    end = invoice_summary(c, doc, end)
    footer(c, doc, max(end + 15, 1150))
    return c


def render_landscape_invoice(doc, config, rng):
    c = Canvas(1414, 1000, config["dpi"], 297, rng.choice(("sans", "serif")), config["font_dir"])
    c.text(40, 24, doc["title"] + " - ITEM WISE TAX", "title", size=24, bold=True, width=1334, align="center")
    c.rect(40, 70, 1334, 181)
    c.line(482, 70, 482, 251)
    c.line(924, 70, 924, 251)
    party_block(c, doc["supplier"], 53, 84, 415, "Supplier", "supplier", True)
    party_block(c, doc["buyer"], 495, 84, 415, "Bill to / Ship to", "buyer", True)
    for i, (label, value, field) in enumerate((("Invoice No.", doc["document_number"], "document_number"),
            ("Date", display_date(doc), "date"), ("Order No.", doc["extra"]["purchase_order"], "extra.purchase_order"),
            ("Payment terms", doc["extra"]["payment_terms"], "extra.payment_terms"), ("Reverse charge", "No", "extra.reverse_charge"))):
        c.kv(938, 88 + 29 * i, label, value, 420, field, size=13)
    c.text(53, 266, "Place of supply: " + doc["buyer"]["state"] + " (" + doc["buyer"]["state_code"] + ")", "place_of_supply", size=13)
    cols = (("Sl.", "line_number", 28), ("Description", "description", 210), ("HSN/SAC", "hsn_sac", 75),
            ("Qty", "quantity", 50), ("Unit", "unit", 45), ("Rate", "unit_price", 85),
            ("Disc %", "discount_percent", 48), ("GST %", "gst_rate", 52), ("Taxable", "taxable_value", 105),
            ("CGST", "cgst", 96), ("SGST", "sgst", 96), ("IGST", "igst", 96), ("Net", "total", 110))
    end = detailed_item_table(c, doc, 40, 300, 1334, cols, min_body=245)
    sy = end + 18
    if sy + 188 > 910:
        raise LayoutError("Landscape table is too long; shorten item descriptions or lower --max-items.")
    c.text(53, sy, "Amount in words", "amount_in_words", "key", 13, True)
    word_end = c.paragraph(53, sy + 27, doc["amount_in_words"], 800, "amount_in_words", size=13, leading=20)
    c.text(53, word_end + 18, "Bank: " + doc["supplier"]["bank"], "supplier.bank", size=13)
    c.text(53, word_end + 42, "A/c: " + doc["supplier"]["account_number"] + "   IFSC: " + doc["supplier"]["ifsc"], "supplier.bank_details", size=12.5)
    if doc["tax_regime"] == "composition":
        c.paragraph(53, word_end + 73, "Composition taxable person, not eligible to collect tax on supplies.", 800, "tax_note", size=12)
    yy = sy
    for label, field in total_pairs(doc):
        c.text(950, yy, label, "totals." + field, "key", 13)
        c.text(1135, yy, indian_money(doc["totals"][field]), "totals." + field, size=13, width=220, align="right")
        yy += 23
    c.line(938, yy, 1374, yy)
    c.text(950, yy + 8, "Grand total", "totals.grand_total", "key", 16, True)
    c.text(1120, yy + 8, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=18, bold=True, width=235, align="right")
    c.region(938, sy, 436, yy + 40 - sy, "totals")
    c.line(40, 920, 1374, 920)
    c.text(53, 936, "E. & O.E.  |  Subject to " + doc["supplier"]["city"] + " jurisdiction", "declaration", "other", 11.5)
    c.text(940, 936, "For " + doc["supplier"]["name"], "signature.issuer", size=12, bold=True, width=420, align="right")
    c.text(40, 974, "SYNTHETIC TRAINING SAMPLE - NOT VALID FOR ACCOUNTING", "synthetic_marker", "other", 9, width=1334, align="center")
    return c


def render_compact_note(doc, config, rng):
    c = Canvas(1000, 1050, config["dpi"], 210, "sans", config["font_dir"])
    c.rect(50, 35, 900, 46, fill="#e9ecef")
    c.text(62, 44, doc["title"], "title", size=23, bold=True, width=875, align="center")
    party_block(c, doc["supplier"], 62, 102, 430, "Issued by", "supplier", True)
    party_block(c, doc["buyer"], 520, 102, 415, "Issued to", "buyer", True)
    c.line(50, 261, 950, 261)
    ref = doc["extra"]["reference_invoice"]
    c.kv(62, 277, "Note No.", doc["document_number"], 430, "document_number", size=13)
    c.kv(520, 277, "Original invoice", ref["number"], 415, "extra.reference_invoice.number", size=12.5)
    c.kv(62, 305, "Date", display_date(doc), 430, "date", size=13)
    c.kv(520, 305, "Invoice date", display_date(doc, value=ref["date"]), 415, "extra.reference_invoice.date", size=12.5)
    c.paragraph(62, 342, "Reason: " + doc["extra"]["reason"], 875, "extra.reason", size=13)
    end = item_table(c, doc, 390, min_body=150)
    end = invoice_summary(c, doc, end)
    footer(c, doc, end + 14)
    return c


def modern_item_table(c, doc, y, accent, zoho):
    columns = (("#", "line_number", 34), ("Item & Description", "description", 330),
        ("HSN/SAC", "hsn_sac", 88), ("Qty", "quantity", 65), ("Rate", "unit_price", 115),
        ("Disc %", "discount_percent", 60), ("GST %", "gst_rate", 68), ("Amount", "taxable_value", 140))
    c.rect(50, y, 900, 36, fill=accent if zoho else "#eeecef", outline=False)
    xx = 50
    for label, field, width in columns:
        c.text(xx + 6, y + 9, label, "table.header", "key", 12, True, width - 12,
               "left" if field == "description" else "right", color="white" if zoho else accent)
        xx += width
    yy = y + 36
    for i, row in enumerate(doc["items"]):
        row_height = max(46, 18 * len(c.wrap_lines(row["description"], 318, 13)) + 16)
        xx = 50
        for _, field, width in columns:
            value = row[field]
            output_field = f"items.{i}.{field}"
            if field in ("unit_price", "taxable_value"):
                value = indian_money(value)
            elif field == "quantity":
                value = value + " " + row["unit"]
                output_field = f"items.{i}.quantity_unit"
            if field == "description":
                c.paragraph(xx + 6, yy + 10, value, width - 12, output_field, size=13, leading=18)
            else:
                c.text(xx + 6, yy + 10, value, output_field, size=12.5, width=width - 12, align="right")
            xx += width
        yy += row_height
        c.line(50, yy, 950, yy, color="#ceced2", weight=.6)
    c.region(50, y, 900, yy - y, "line_items")
    return yy


def render_modern_document(doc, config, rng):
    """Original Zoho/Odoo-inspired print themes, adapted to all six classes.

    This is a local renderer, not a native export from either ERP. Utility pages
    keep provider-specific fields; a theme does not imply an ERP utility module.
    """
    zoho = doc["template"] == "zoho_style"
    accent = rng.choice(("#24455e", "#2f5152", "#33465a")) if zoho else rng.choice(("#714b67", "#52677d", "#596b62"))
    c = Canvas(1000, 1414, config["dpi"], 210, "sans", config["font_dir"], accent=accent)
    supplier, extra = doc["supplier"], doc["extra"]
    kind = doc["document_type"]
    total_label = {"expense_receipt": "TOTAL PAID", "credit_note": "CREDIT AMOUNT", "debit_note": "DEBIT AMOUNT"}.get(kind, "TOTAL AMOUNT")
    if zoho:
        c.text(60, 55, supplier["name"], "supplier.name", size=24, bold=True, width=515)
        c.paragraph(60, 99, supplier["address"] + "\n" + supplier["city"] + " - " + supplier["pincode"] + ", " + supplier["state"], 500, "supplier.address", size=13, leading=22)
        c.text(60, 155, "GSTIN: " + (supplier["gstin"] or "Unregistered"), "supplier.gstin", size=13, width=510)
        c.text(610, 57, doc["title"], "title", size=29, width=330, align="right")
        c.text(610, 107, doc["document_number"], "document_number", size=16, bold=True, width=330, align="right")
        c.rect(610, 151, 330, 82, fill="#f1f3f4", outline=False)
        c.text(625, 164, total_label, "totals.grand_total", "key", 11.5, width=300, align="right")
        c.text(625, 190, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=22, bold=True, width=300, align="right")
        party_block(c, doc["buyer"], 60, 267, 500, "Bill To" if kind != "expense_receipt" else "Received From", "buyer", True)
        info_x, info_y, info_w, table_y = 610, 278, 330, 462
    else:
        initials = "".join(word[0] for word in supplier["name"].split()[:2])
        c.rect(60, 51, 76, 76, fill=accent, outline=False)
        c.text(64, 69, initials, "supplier.monogram", "other", 29, True, 68, "center", color="white")
        c.text(400, 48, supplier["name"], "supplier.name", size=22, bold=True, width=540, align="right")
        c.text(400, 84, supplier["address"], "supplier.address", size=13, width=540, align="right")
        c.text(400, 108, supplier["city"] + " - " + supplier["pincode"] + ", " + supplier["state"], "supplier.city_state_pin", size=13, width=540, align="right")
        c.text(400, 132, "GSTIN: " + (supplier["gstin"] or "Unregistered"), "supplier.gstin", size=13, width=540, align="right")
        c.line(50, 179, 950, 179, color=accent, weight=1.5)
        party_block(c, doc["buyer"], 60, 203, 510, "Customer" if kind != "utility_bill" else "Consumer", "buyer", True)
        c.text(60, 382, doc["title"], "title", size=29, bold=True, width=870, color=accent)
        c.text(60, 426, doc["document_number"], "document_number", size=17, width=870)
        info_x, info_y, info_w, table_y = 60, 471, 870, 543
    if kind == "expense_receipt":
        fields = (("Payment Date", display_date(doc), "date"),
            ("Payment Mode", extra["payment_mode"], "extra.payment_mode"),
            ("Reference", extra["payment_reference"], "extra.payment_reference"),
            ("Expense", doc["subtype"].replace("_", " ").title(), "extra.expense_category"))
    elif kind == "utility_bill":
        fields = (("Bill Date", display_date(doc), "date"),
            ("Due Date", display_date(doc, value=extra["due_date"]), "extra.due_date"),
            ("Consumer No.", extra["consumer_number"], "extra.consumer_number"),
            ("Category", "Commercial", "extra.tariff_category"))
    else:
        fields = (("Invoice Date" if kind in ("gst_invoice", "purchase_bill") else "Note Date", display_date(doc), "date"),
            ("Due Date", display_date(doc, value=extra["due_date"]), "extra.due_date"),
            ("Payment Terms", extra["payment_terms"], "extra.payment_terms"),
            ("Place of Supply", doc["buyer"]["state"], "place_of_supply"))
    for i, (label, value, field) in enumerate(fields):
        if zoho:
            c.kv(info_x, info_y + i * 32, label, value, info_w, field, size=12.5, gap=135)
        else:
            xx = info_x + i * (info_w / 4)
            c.text(xx, info_y, label, field, "key", 12, True, info_w / 4 - 15, color=accent)
            c.text(xx, info_y + 25, value, field, size=13, width=info_w / 4 - 15)
    if kind in ("credit_note", "debit_note"):
        ref = extra["reference_invoice"]
        c.kv(60, table_y, "Original Invoice", ref["number"] + " / " + display_date(doc, value=ref["date"]), 870, "extra.reference_invoice", size=13)
        c.paragraph(60, table_y + 29, "Reason: " + extra["reason"], 870, "extra.reason", size=13)
        table_y += 72
    elif kind == "utility_bill":
        c.text(60, table_y, "Billing period: " + display_date(doc, value=extra["period_start"]) + " to " + display_date(doc, value=extra["period_end"]), "extra.billing_period", size=13)
        if "meter_number" in extra:
            text = "Meter " + extra["meter_number"] + "   Previous: " + extra["previous_reading"] + "   Current: " + extra["current_reading"] + "   Used: " + extra["consumption"] + " " + extra["consumption_unit"]
            c.text(60, table_y + 29, text, "extra.meter_readings", size=12, width=870)
        else:
            c.text(60, table_y + 29, extra["plan"], "extra.plan", size=13, width=870)
        table_y += 75
    elif kind == "expense_receipt" and extra.get("tax_note"):
        c.text(60, table_y, extra["tax_note"], "extra.tax_note", size=12, width=870)
        table_y += 35
    end = modern_item_table(c, doc, table_y, accent, zoho)
    summary_y = end + 22
    if summary_y + 196 > 1210:
        raise LayoutError("Modern template too long; lower --max-items or shorten descriptions.")
    left_y = c.paragraph(60, summary_y + 2, doc["amount_in_words"], 490, "amount_in_words", size=12.5, leading=19)
    if doc["tax_regime"] in ("intra_state", "inter_state"):
        c.text(60, left_y + 20, "Tax Summary", "tax_summary", "key", 12, True, color=accent)
        left_y += 47
        for i, row in enumerate(doc["tax_summary"]):
            value = "GST " + row["gst_rate"] + "% on " + indian_money(row["taxable_value"]) + ": " + indian_money(dec(row["cgst"]) + dec(row["sgst"]) + dec(row["igst"]))
            c.text(60, left_y, value, f"tax_summary.{i}.display", size=12, width=490)
            left_y += 22
    elif doc["tax_regime"] == "composition":
        c.paragraph(60, left_y + 21, "Composition taxable person, not eligible to collect tax on supplies.", 490, "tax_note", size=12)
    yy = summary_y
    for label, field in total_pairs(doc):
        c.text(610, yy, label, "totals." + field, "key", 13)
        c.text(783, yy, indian_money(doc["totals"][field]), "totals." + field, size=13, width=153, align="right")
        yy += 23
    c.rect(598, yy + 2, 352, 45, fill="#eef0f2", outline=False)
    c.text(610, yy + 12, "Total Paid" if kind == "expense_receipt" else "Total", "totals.grand_total", "key", 16, True)
    c.text(717, yy + 12, doc["currency_symbol"] + " " + indian_money(doc["totals"]["grand_total"]), "totals.grand_total", size=18, bold=True, width=219, align="right")
    c.region(598, summary_y, 352, yy + 47 - summary_y, "totals")
    footer(c, doc, max(yy + 62, 1220))
    return c


def render_document(doc, config):
    rng = random.Random(seeded(config["seed"], doc["document_number"], doc["document_type"], "style"))
    if doc["template"] in MODERN_LAYOUTS:
        return render_modern_document(doc, config, rng)
    if doc["document_type"] == "expense_receipt":
        return render_receipt(doc, config, rng)
    if doc["document_type"] == "utility_bill":
        return render_utility(doc, config, rng)
    if doc["template"] in ("trade_a5", "batch_mrp"):
        return render_trade_invoice(doc, config, rng)
    if doc["template"] == "item_tax_landscape":
        return render_landscape_invoice(doc, config, rng)
    if doc["template"] == "note_compact":
        return render_compact_note(doc, config, rng)
    return render_invoice(doc, config, rng)


def homography(source, target):
    a, b = [], []
    for (x, y), (u, v) in zip(source, target):
        a.extend(([x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]))
        b.extend((u, v))
    return np.append(np.linalg.solve(np.asarray(a, dtype=float), np.asarray(b, dtype=float)), 1.0).reshape(3, 3)


def project_points(points, matrix):
    points = np.asarray(points, dtype=float)
    result = np.c_[points, np.ones(len(points))] @ matrix.T
    return result[:, :2] / result[:, 2:3]


def augment_image(image, seed, mode):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    mode = rng.choices(("none", "scan", "photo"), (.30, .45, .25))[0] if mode == "mixed" else mode
    w, h = image.size
    matrix = np.eye(3)
    effects = {"mode": mode, "source_size": [w, h]}
    if mode == "none":
        return image.copy(), matrix, effects
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=float)
    if mode == "scan":
        angle = rng.uniform(-1.7, 1.7)
        theta = math.radians(angle)
        factor = min(w / (abs(w * math.cos(theta)) + abs(h * math.sin(theta))), h / (abs(w * math.sin(theta)) + abs(h * math.cos(theta)))) * .975
        rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]]) * factor
        target = (corners - [w/2, h/2]) @ rotation.T + [w/2, h/2]
        output_size = (w, h)
        background = (247, 246, 243)
        effects.update({"rotation_degrees_clockwise": angle, "scale": factor})
    else:
        margin_x, margin_y = .085 * w, .065 * h
        output_size = (round(w + 2 * margin_x), round(h + 2 * margin_y))
        target = corners + [margin_x, margin_y]
        for p in target:
            p += [rng.uniform(-.032, .032) * w, rng.uniform(-.025, .025) * h]
        background = rng.choice(((188, 181, 168), (176, 179, 180), (213, 205, 189)))
        effects["page_corners_px"] = target.tolist()
    matrix = homography(corners, target)
    inverse = np.linalg.inv(matrix)
    inverse /= inverse[2, 2]
    transformed = image.transform(output_size, Image.Transform.PERSPECTIVE, inverse.flatten()[:8], resample=Image.Resampling.BICUBIC, fillcolor=background)
    values = np.asarray(transformed).astype(np.float32)
    oh, ow = values.shape[:2]
    noise = rng.uniform(.6, 2.5) if mode == "scan" else rng.uniform(1.0, 3.5)
    values += nrng.normal(0, noise, (oh, ow, 1)).astype(np.float32)
    contrast = rng.uniform(.78, 1.02)
    values = (values - 128) * contrast + 128
    if mode == "photo":
        shadow = np.linspace(rng.uniform(.75, .93), 1.0, ow, dtype=np.float32)
        if rng.random() < .5:
            shadow = shadow[::-1]
        values *= shadow[None, :, None]
        effects["side_shadow"] = True
    if rng.random() < .35:
        row = rng.randrange(int(.25 * oh), int(.75 * oh))
        values[max(0, row-1):row+2] *= .95
        effects["faint_scan_line_y"] = row
    gray = rng.random() < .55 if mode == "scan" else rng.random() < .15
    if gray:
        values = np.repeat(values.mean(axis=2, keepdims=True), 3, axis=2)
    transformed = Image.fromarray(np.clip(values, 0, 255).astype(np.uint8))
    blur = rng.uniform(.15, .6) if mode == "scan" else rng.uniform(.2, .7)
    transformed = transformed.filter(ImageFilter.GaussianBlur(blur))
    quality = rng.randint(67, 92)
    with io.BytesIO() as buffer:
        transformed.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        with Image.open(buffer) as compressed:
            transformed = compressed.convert("RGB").copy()
    effects.update({"noise_sigma": noise, "contrast": contrast, "grayscale": gray, "blur_radius_px": blur, "jpeg_quality": quality})
    return transformed, matrix, effects


def transform_annotations(records, matrix, width, height):
    transformed = []
    for source in records:
        record = copy.deepcopy(source)
        x0, y0, x1, y1 = record["source_bbox"]
        points = project_points([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], matrix)
        # No intentional text cropping: every word remains visible geometrically.
        if points[:, 0].min() < -1 or points[:, 1].min() < -1 or points[:, 0].max() > width + 1 or points[:, 1].max() > height + 1:
            raise LayoutError(f"Annotation moved outside image: {record.get('text', record.get('label'))}")
        points[:, 0] = np.clip(points[:, 0], 0, width)
        points[:, 1] = np.clip(points[:, 1], 0, height)
        box = [max(0, math.floor(points[:, 0].min())), max(0, math.floor(points[:, 1].min())), min(width, math.ceil(points[:, 0].max())), min(height, math.ceil(points[:, 1].max()))]
        record["polygon"] = [[round(float(x), 3), round(float(y), 3)] for x, y in points]
        record["bbox"] = box
        record["bbox_1000"] = [round(box[0]*1000/width), round(box[1]*1000/height), round(box[2]*1000/width), round(box[3]*1000/height)]
        transformed.append(record)
    return transformed


def validate_document(doc):
    totals = doc["totals"]
    for key in ("gross", "discount", "taxable_value", "cgst", "sgst", "igst"):
        assert sum((dec(row[key]) for row in doc["items"]), Decimal(0)) == dec(totals[key]), key
    assert dec(totals["gross"]) - dec(totals["discount"]) == dec(totals["taxable_value"])
    assert dec(totals["taxable_value"]) + dec(totals["tax_total"]) + dec(totals["round_off"]) == dec(totals["grand_total"])
    assert 0 < len(doc["document_number"]) <= 16
    if doc["tax_regime"] == "intra_state":
        assert doc["supplier"]["state_code"] == doc["place_of_supply"]["state_code"]
        assert dec(totals["cgst"]) == dec(totals["sgst"]) and dec(totals["igst"]) == 0
    elif doc["tax_regime"] == "inter_state":
        assert doc["supplier"]["state_code"] != doc["place_of_supply"]["state_code"]
        assert dec(totals["cgst"]) == 0 and dec(totals["sgst"]) == 0
    else:
        assert dec(totals["tax_total"]) == 0
    if doc["document_type"] in ("credit_note", "debit_note"):
        assert doc["extra"]["reference_invoice"]["date"] < doc["date"]
    if "consumption" in doc["extra"]:
        ex = doc["extra"]
        assert dec(ex["current_reading"]) - dec(ex["previous_reading"]) == dec(ex["consumption"])


def make_split_counts(count, ratios):
    raw = [count * r for r in ratios]
    result = [math.floor(v) for v in raw]
    for i in sorted(range(3), key=lambda n: raw[n] - result[n], reverse=True)[:count - sum(result)]:
        result[i] += 1
    # Small preview datasets still get every requested split when possible.
    if count >= sum(r > 0 for r in ratios):
        for i, ratio in enumerate(ratios):
            if ratio > 0 and result[i] == 0:
                donor = max(range(3), key=lambda j: result[j])
                result[donor] -= 1
                result[i] += 1
    return result


def generate_task(task):
    kind, index, split, config = task
    doc = make_document(kind, index, split, config)
    validate_document(doc)
    canvas = render_document(doc, config)
    base_id = hashlib.sha256(f"{config['seed']}:{kind}:{index}".encode()).hexdigest()[:18]
    records = []
    root = Path(config["out"])
    for variant in range(config["variants"]):
        mode = "none" if config["variants"] > 1 and variant == 0 else config["augment"]
        image, matrix, effects = augment_image(canvas.image, seeded(config["seed"], kind, index, variant, "augmentation"), mode)
        sample_id = base_id + f"_v{variant:02d}"
        image_rel = Path("images") / split / kind / (sample_id + "." + config["format"])
        label_rel = Path("annotations") / split / kind / (sample_id + ".json")
        (root / image_rel).parent.mkdir(parents=True, exist_ok=True)
        (root / label_rel).parent.mkdir(parents=True, exist_ok=True)
        save_args = {"dpi": (config["dpi"], config["dpi"])}
        if config["format"] == "jpg":
            save_args["quality"] = 94
        else:
            save_args["compress_level"] = 5
        image.save(root / image_rel, **save_args)
        lines = transform_annotations(canvas.lines, matrix, *image.size)
        words = transform_annotations(canvas.words, matrix, *image.size)
        regions = transform_annotations(canvas.regions, matrix, *image.size)
        labels = {"schema_version": "1.0", "sample_id": sample_id, "base_document_id": base_id, "variant": variant, "split": split, "image": {"path": image_rel.as_posix(), "width": image.width, "height": image.height, "nominal_dpi": config["dpi"], "format": config["format"]}, "document": doc, "augmentation": {**effects, "source_to_image_homography": matrix.tolist()}, "ocr": {"bbox_format": "xyxy; pixels; origin top-left; x right; y down", "polygon_order": "source TL, TR, BR, BL mapped to final image", "reading_order": "renderer draw order; grouped by field; not global spatial order", "lines": lines, "words": words}, "regions": regions}
        (root / label_rel).write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append({"sample_id": sample_id, "base_document_id": base_id, "split": split, "document_type": kind, "visual_document_type": doc["visual_document_type"], "template": doc["template"], "subtype": doc["subtype"], "supplier_id": doc["supplier"]["party_id"], "buyer_id": doc["buyer"]["party_id"], "image": image_rel.as_posix(), "annotation": label_rel.as_posix(), "width": image.width, "height": image.height, "augmentation": effects["mode"]})
    return records


def save_contact_sheet(root, records, font_dir, filename="preview.jpg"):
    selected, seen = [], set()
    # First show all document classes, then add previously unseen layout families.
    # Large invoice-template families must not hide receipts, bills or notes.
    shown_templates = set()
    for kind in DOC_TYPES:
        candidates = [r for r in records if r["document_type"] == kind]
        if candidates:
            record = next((r for r in candidates if r["augmentation"] == "none"), candidates[0])
            selected.append(record)
            seen.add((record["document_type"], record["template"]))
            shown_templates.add(record["template"])
    for record in records:
        key = (record["document_type"], record["template"])
        if key not in seen and record["template"] not in shown_templates:
            seen.add(key)
            shown_templates.add(record["template"])
            selected.append(record)
        if len(selected) == 18:
            break
    cols, card_w, card_h = 3, 440, 650
    rows = math.ceil(len(selected) / cols)
    sheet = Image.new("RGB", (cols * card_w + 40, rows * card_h + 110), "#e7e9ec")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(font_path("sans", True, font_dir), 25)
    body_font = load_font(font_path("sans", False, font_dir), 16)
    draw.text((24, 20), "INDIAN ERP DOCUMENTS | synthetic training examples", fill="#182c43", font=title_font)
    draw.text((24, 59), "Fictional data  /  multiple layouts  /  aligned text and field annotations", fill="#46566a", font=body_font)
    for i, record in enumerate(selected):
        xx = 20 + (i % cols) * card_w
        yy = 98 + (i // cols) * card_h
        draw.rounded_rectangle((xx + 5, yy, xx + card_w - 10, yy + card_h - 14), 10, fill="white")
        with Image.open(root / record["image"]) as im:
            thumb = im.convert("RGB")
            thumb.thumbnail((card_w - 44, card_h - 104))
            sheet.paste(thumb, (xx + (card_w - thumb.width)//2, yy + 12 + (card_h - 104 - thumb.height)//2))
        label = record["document_type"].replace("_", " ").title()
        draw.text((xx + 20, yy + card_h - 75), label, fill="#182c43", font=load_font(font_path("sans", True, font_dir), 17))
        draw.text((xx + 20, yy + card_h - 49), record["template"] + " / " + record["augmentation"], fill="#586579", font=body_font)
    sheet.save(root / filename, quality=90)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("dataset"), help="New or empty output directory; existing data is never overwritten.")
    p.add_argument("--per-type", type=int, default=1000, help="Base documents per selected class (default 1000: 6000 across all six classes).")
    p.add_argument("--sectors", nargs="+", choices=MSME_SECTORS, default=list(MSME_SECTORS), help="MSME sectors for invoice and note content; --catalog overrides these product lists.")
    p.add_argument("--dry-run", action="store_true", help="Print document/image/annotation counts without generating files.")
    p.add_argument("--types", nargs="+", choices=DOC_TYPES, default=list(DOC_TYPES))
    p.add_argument("--templates", nargs="+", choices=ALL_LAYOUTS, default=list(ALL_LAYOUTS))
    p.add_argument("--variants", type=int, default=1, help="Images per document; with >1 the first variant is clean. All stay in the same split.")
    p.add_argument("--augment", choices=("mixed", "none", "scan", "photo"), default="mixed")
    p.add_argument("--format", choices=("png", "jpg"), default="png")
    p.add_argument("--dpi", type=int, default=150, help="Nominal render DPI, 72..300 (default 150).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=1, help="Parallel processes. Each worker can use ~100-300 MB at 150-300 DPI.")
    p.add_argument("--split", nargs=3, type=float, default=[.8, .1, .1], metavar=("TRAIN", "VAL", "TEST"))
    p.add_argument("--suppliers-per-split", type=int, default=40, help="Party pool size per sector in each split.")
    p.add_argument("--max-items", type=int, default=8, help="Maximum invoice item rows (1..8); receipts/utilities use dedicated rows.")
    p.add_argument("--start-date", default="2024-04-01", help="ISO date, inclusive. Historical defaults avoid implying current tax rates.")
    p.add_argument("--end-date", default="2025-03-31")
    p.add_argument("--catalog", type=Path, help="Optional JSON list replacing the illustrative product catalog.")
    p.add_argument("--font-dir", type=Path, help="Folder containing DejaVu Sans, Serif and SansMono regular/bold TTFs.")
    p.add_argument("--no-preview", action="store_true")
    args = p.parse_args(argv)
    if not 1 <= args.per_type <= 99999:
        p.error("--per-type must be 1..99999")
    if not 1 <= args.variants <= 20:
        p.error("--variants must be 1..20")
    if not 72 <= args.dpi <= 300:
        p.error("--dpi must be 72..300")
    if not 1 <= args.max_items <= 8:
        p.error("--max-items must be 1..8")
    if not 1 <= args.workers <= 64 or not 1 <= args.suppliers_per_split <= 100000:
        p.error("--workers must be 1..64 and --suppliers-per-split 1..100000")
    if any(not math.isfinite(x) or x < 0 for x in args.split) or abs(sum(args.split) - 1) > 1e-8:
        p.error("--split must contain non-negative finite fractions summing to 1")
    try:
        if date.fromisoformat(args.start_date) > date.fromisoformat(args.end_date):
            raise ValueError("start date exceeds end date")
    except ValueError as exc:
        p.error(str(exc))
    args.types = list(dict.fromkeys(args.types))
    args.templates = list(dict.fromkeys(args.templates))
    for kind in args.types:
        if not set(LAYOUTS[kind]).intersection(args.templates):
            p.error(f"No compatible template selected for {kind}: choose from {LAYOUTS[kind]}")
    if not args.dry_run and args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        p.error("Output directory must be new or empty; choose another --out path.")
    return args


def load_catalog(path):
    catalog = json.loads(Path(path).read_text(encoding="utf-8")) if path else copy.deepcopy(CATALOG)
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("Catalog must be a non-empty JSON list.")
    required = {"description", "hsn_sac", "unit", "price_min", "price_max", "gst_rate"}
    for item in catalog:
        if not isinstance(item, dict) or not required <= item.keys():
            raise ValueError(f"Every catalog row needs {sorted(required)}")
        if not isinstance(item["description"], str) or not 1 <= len(item["description"]) <= 56 or not item["description"].isascii() or not item["description"].isprintable():
            raise ValueError("Catalog descriptions must be printable English/ASCII, 1..56 characters.")
        if not isinstance(item["hsn_sac"], str) or not re.fullmatch(r"\d{4,8}", item["hsn_sac"]):
            raise ValueError("Catalog hsn_sac must be a 4..8 digit string.")
        if not isinstance(item["unit"], str) or not re.fullmatch(r"[A-Za-z]{1,5}", item["unit"]):
            raise ValueError("Catalog units must contain 1..5 letters.")
        values = [dec(item[k]) for k in ("price_min", "price_max", "gst_rate")]
        if not all(v.is_finite() for v in values):
            raise ValueError("Catalog numbers must be finite.")
        low, high, rate = values
        if not (0 < low <= high <= 1000000 and 0 <= rate <= 100):
            raise ValueError("Catalog prices must be 0 < min <= max <= 1000000; GST 0..100.")
    return catalog


def main(argv=None):
    args = parse_args(argv)
    config = vars(args).copy()
    config["out"] = str(args.out.resolve())
    config["font_dir"] = str(args.font_dir.resolve()) if args.font_dir else None
    config["catalog"] = load_catalog(args.catalog)
    config["custom_catalog"] = args.catalog is not None
    if args.dry_run:
        print(json.dumps({"per_type": args.per_type, "types": args.types, "base_documents": args.per_type * len(args.types), "images": args.per_type * len(args.types) * args.variants, "annotation_files": args.per_type * len(args.types) * args.variants, "sectors": args.sectors, "layouts": {kind: [t for t in LAYOUTS[kind] if t in args.templates] for kind in args.types}}, indent=2))
        return 0
    # Resolve fonts before creating any outputs, so dependency failures are clean.
    fonts = sorted({font_path(f, b, config["font_dir"]) for f in ("sans", "serif", "mono") for b in (False, True)})
    font_hashes = {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in fonts}
    out = Path(config["out"])
    out.mkdir(parents=True, exist_ok=True)
    counts = make_split_counts(args.per_type, args.split)
    tasks = []
    for kind in args.types:
        assignments = [s for s, n in zip(("train", "val", "test"), counts) for _ in range(n)]
        random.Random(seeded(args.seed, kind, "split_assignment")).shuffle(assignments)
        tasks.extend((kind, i, split, config) for i, split in enumerate(assignments))
    info = {"generator_version": VERSION, "status": "incomplete", "seed": args.seed, "config": config, "dependencies": {"python": sys.version.split()[0], "pillow": PIL_VERSION, "numpy": np.__version__}, "font_sha256": font_hashes, "base_document_split_counts_per_type": dict(zip(("train", "val", "test"), counts)), "synthetic_data": True, "tax_policy": "Illustrative historical training data; not current tax/compliance advice.", "split_policy": "Party IDs and all variants of each base document are disjoint across train/val/test. Layout families are shared across splits."}
    (out / "dataset_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    records = []
    print(f"Generating {len(tasks)} base documents across {len(args.types)} classes: {len(tasks) * args.variants} images and matching JSON annotations.", flush=True)
    executor = ProcessPoolExecutor(max_workers=args.workers) if args.workers > 1 else None
    try:
        generated = executor.map(generate_task, tasks, chunksize=1) if executor else map(generate_task, tasks)
        with (out / "manifest.jsonl").open("w", encoding="utf-8") as manifest:
            for n, batch in enumerate(generated, 1):
                for record in batch:
                    manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                    records.append(record)
                if n % 25 == 0 or n == len(tasks):
                    print(f"Generated {n}/{len(tasks)} documents ({len(records)} images)", flush=True)
    finally:
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)
    if not args.no_preview:
        save_contact_sheet(out, records, config["font_dir"])
    info.update({"status": "complete", "base_documents": len(tasks), "image_count": len(records), "class_counts": dict(Counter(r["document_type"] for r in records)), "split_counts": dict(Counter(r["split"] for r in records)), "template_counts": dict(Counter(r["template"] for r in records)), "augmentation_counts": dict(Counter(r["augmentation"] for r in records))})
    (out / "dataset_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Done. Images, JSON labels and manifest: {out}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
