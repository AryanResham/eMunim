#!/usr/bin/env python3
"""
Synthetic Indian-style business document generator.

Generates realistic-looking but FICTIONAL:
  - TAX INVOICE
  - DEBIT NOTE
  - SALES ORDER
  - CREDIT NOTE
  - PURCHASE BILL
  - EXPENSE RECEIPT
  - UTILITY BILL

Default: 5,000 one-page A4 PDFs + manifest.csv.

Install:
    pip install reportlab

Run:
    python generate_synthetic_invoices.py --count 5000 --out synthetic_docs --seed 42

Optional:
    python generate_synthetic_invoices.py --count 5000 --out synthetic_docs \
        --seed 42 --invoice-only

The source screenshots are used only as layout/style inspiration. This script
does not copy their real parties, GSTINs, bank details, invoice numbers, etc.
All generated business identities and transaction values are synthetic.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
import string
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Dict, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.pdfbase.pdfmetrics import stringWidth


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN = 9 * mm

# Layout diversity controls.
# A new "layout family" is selected every few documents, while per-document
# jitter makes every individual PDF different even when it uses the same family.
LAYOUT_FAMILIES = [
    "classic", "header_split", "buyer_right", "meta_split", "compact",
    "wide_items", "boxed_sections", "minimal", "asymmetric", "dense",
    "ledger", "receipt_like",
]
LAYOUT_CHANGE_EVERY = 7

def make_layout_rng(seed: int, serial: int):
    """Independent deterministic RNG so layout changes never affect document data."""
    return random.Random((seed + 1) * 1_000_003 + serial * 97_409)

def choose_layout(seed: int, serial: int):
    lrng = make_layout_rng(seed, serial)
    # Rotate the family pool by epoch so the structure changes substantially.
    epoch = (serial - 1) // LAYOUT_CHANGE_EVERY
    family = LAYOUT_FAMILIES[epoch % len(LAYOUT_FAMILIES)]
    # Every document gets independent visual jitter.
    return {
        "family": family,
        "left": lrng.uniform(5.5, 13.5) * mm,
        "right": lrng.uniform(5.5, 13.5) * mm,
        "top": lrng.uniform(4.5, 10.0) * mm,
        "bottom": lrng.uniform(4.5, 10.0) * mm,
        "pad": lrng.uniform(1.5, 5.0),
        "row_pad": lrng.uniform(1.0, 3.8),
        "title_size": lrng.uniform(11.5, 17.0),
        "line_width": lrng.uniform(0.25, 0.85),
        "show_original": lrng.random() < 0.72,
        "show_disclaimer": lrng.random() < 0.90,
        "show_page_border": lrng.random() < 0.20,
        "reverse_party": lrng.random() < 0.45,
        "extra_spacer": lrng.uniform(0.5, 5.0) * mm,
        "header_gap": lrng.uniform(1.0, 6.0) * mm,
        "section_gap": lrng.uniform(0.7, 3.5) * mm,
        "buyer_height": lrng.uniform(29.0, 46.0) * mm,
    }

GST_RATES = [5, 12, 18, 28]
DOC_WEIGHTS = {
    "tax_invoice": 0.44,
    "debit_note": 0.08,
    "sales_order": 0.10,
    "credit_note": 0.08,
    "purchase_bill": 0.10,
    "expense_receipt": 0.10,
    "utility_bill": 0.10,
}

INDIAN_STATES = [
    ("Uttar Pradesh", "09", ["Lucknow", "Gorakhpur", "Kanpur", "Varanasi", "Agra"]),
    ("Maharashtra", "27", ["Mumbai", "Pune", "Nagpur", "Nashik"]),
    ("Karnataka", "29", ["Bengaluru", "Mysuru", "Hubballi", "Mangaluru"]),
    ("Delhi", "07", ["New Delhi", "Delhi"]),
    ("Gujarat", "24", ["Ahmedabad", "Surat", "Vadodara", "Rajkot"]),
    ("Rajasthan", "08", ["Jaipur", "Jodhpur", "Kota", "Udaipur"]),
    ("West Bengal", "19", ["Kolkata", "Durgapur", "Siliguri"]),
    ("Tamil Nadu", "33", ["Chennai", "Coimbatore", "Madurai"]),
    ("Telangana", "36", ["Hyderabad", "Warangal"]),
    ("Andhra Pradesh", "37", ["Vijayawada", "Visakhapatnam", "Tirupati"]),
    ("Bihar", "10", ["Patna", "Gaya", "Muzaffarpur"]),
    ("Madhya Pradesh", "23", ["Indore", "Bhopal", "Jabalpur"]),
]

COMPANY_PREFIXES = [
    "NOVA", "APEX", "ORBIT", "PRIME", "METRO", "UNITED", "STAR",
    "TRIDENT", "EVEREST", "SUNRISE", "VISTA", "ZENITH", "ROYAL",
    "CENTRAL", "SHREE", "GLOBAL", "PIONEER", "CAPITAL", "SILVER",
]
COMPANY_SUFFIXES = [
    "AUTOMOBILES", "AUTO PARTS", "MOTORS", "TRADERS", "ENTERPRISES",
    "TECH SOLUTIONS", "INDUSTRIES", "DISTRIBUTORS", "SYSTEMS",
    "ELECTRONICS", "SUPPLIERS", "SERVICES", "PRODUCTS",
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Kabir", "Rohan", "Rahul",
    "Vikram", "Ankit", "Amit", "Suresh", "Manish", "Neeraj", "Karan",
    "Nikhil", "Raj", "Mohit", "Piyush", "Varun", "Deepak",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Yadav", "Agarwal", "Jain",
    "Mehta", "Patel", "Kumar", "Mishra", "Srivastava", "Malhotra",
    "Kapoor", "Bansal", "Saxena",
]

PRODUCTS = [
    # description, HSN/SAC, unit, low price, high price
    ("SMF BATTERY 35AH", "85071000", "Nos", 1800, 4200),
    ("SMF BATTERY 45AH", "85071000", "Nos", 2400, 5200),
    ("SMF BATTERY 55AH", "85071000", "Nos", 3000, 6500),
    ("CAR HEAD LAMP ASSEMBLY", "85122000", "Pcs", 900, 4500),
    ("LED HEAD LAMP", "85122000", "Pcs", 700, 3500),
    ("SIDE BOX RH", "87141090", "Pcs", 500, 1800),
    ("SIDE BOX LH", "87141090", "Pcs", 500, 1800),
    ("BRAKE SHOE SET", "87141090", "Set", 250, 1200),
    ("CLUTCH PLATE", "84831090", "Pcs", 800, 3200),
    ("AIR FILTER", "84213100", "Pcs", 180, 900),
    ("OIL FILTER", "84212300", "Pcs", 120, 650),
    ("BRAKE PAD SET", "87083000", "Set", 650, 2800),
    ("WIPER BLADE", "85124000", "Pcs", 150, 850),
    ("HORN ASSEMBLY", "85123000", "Pcs", 180, 1000),
    ("TONER CARTRIDGE BLACK", "84439951", "Nos", 2500, 9500),
    ("TONER CARTRIDGE CYAN", "84439951", "Nos", 2500, 9500),
    ("TONER CARTRIDGE YELLOW", "84439951", "Nos", 2500, 9500),
    ("NETWORK PRINTER", "84433220", "Nos", 8500, 28000),
    ("PASSBOOK PRINTER", "84433220", "Nos", 18000, 32000),
    ("SCANNER MAIN BOARD", "84733099", "Nos", 12000, 45000),
    ("USB KEYBOARD", "84716060", "Pcs", 500, 1800),
    ("LASER MOUSE", "84716060", "Pcs", 350, 1200),
    ("POWER ADAPTER", "85044090", "Pcs", 600, 2200),
    ("CABLE ASSEMBLY", "85444290", "Pcs", 150, 1200),
    ("DASHING BLACK", "65061090", "Pcs", 500, 1800),
    ("NUT & WASHER", "73182910", "Pcs", 1.5, 15),
    ("PVC CABLE SLEEVE", "87149990", "Pcs", 80, 500),
    ("FREIGHT", "996511", "Nos", 50, 800),
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Party:
    name: str
    address: str
    city: str
    state: str
    state_code: str
    pincode: str
    phone: str
    gstin: str


@dataclass
class LineItem:
    description: str
    hsn: str
    qty: float
    unit: str
    unit_price: Decimal
    discount_pct: Decimal
    gst_rate: Decimal

    @property
    def gross(self) -> Decimal:
        return money(Decimal(str(self.qty)) * self.unit_price)

    @property
    def discount(self) -> Decimal:
        return money(self.gross * self.discount_pct / Decimal("100"))

    @property
    def taxable(self) -> Decimal:
        return money(self.gross - self.discount)

    @property
    def cgst(self) -> Decimal:
        return money(self.taxable * self.gst_rate / Decimal("200"))

    @property
    def sgst(self) -> Decimal:
        return money(self.taxable * self.gst_rate / Decimal("200"))

    @property
    def igst(self) -> Decimal:
        return Decimal("0.00")

    @property
    def total(self) -> Decimal:
        return money(self.taxable + self.cgst + self.sgst)


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt_money(x: Decimal) -> str:
    return f"{x:,.2f}"


def fmt_qty(q: float) -> str:
    if abs(q - round(q)) < 1e-9:
        return f"{int(round(q))}.00"
    return f"{q:.2f}"


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def random_digits(rng, n):
    return "".join(rng.choice(string.digits) for _ in range(n))


def fake_gstin(rng, state_code: str) -> str:
    # Plausible GSTIN shape, intentionally synthetic.
    letters = "".join(rng.choice(string.ascii_uppercase) for _ in range(5))
    digits = random_digits(rng, 4)
    entity = rng.choice(string.ascii_uppercase)
    checksum = rng.choice(string.ascii_uppercase + string.digits)
    return f"{state_code}{letters}{digits}{entity}1Z{checksum}"


def fake_phone(rng) -> str:
    return "9" + random_digits(rng, 9)


def make_party(rng, kind: str) -> Party:
    state, code, cities = rng.choice(INDIAN_STATES)
    city = rng.choice(cities)
    if kind == "seller":
        name = f"{rng.choice(COMPANY_PREFIXES)} {rng.choice(COMPANY_SUFFIXES)}"
    else:
        if rng.random() < 0.42:
            # Add a numeric/entity marker to reduce accidental name collisions.
            name = (
                f"{rng.choice(COMPANY_PREFIXES)} "
                f"{rng.choice(COMPANY_SUFFIXES)} "
                f"{rng.randint(10,999)}"
            )
        else:
            name = (
                f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)} "
                f"{rng.choice(['AUTOMOBILES', 'TRADERS', 'ENTERPRISES', 'SERVICES'])}"
            )

    street = rng.choice([
        "MAIN MARKET", "INDUSTRIAL AREA", "TRANSPORT NAGAR",
        "M.G. ROAD", "G.T. ROAD", "RING ROAD", "STATION ROAD",
        "SOUTH EXTENSION", "COMMERCIAL COMPLEX",
    ])
    number = rng.randint(1, 999)
    pincode = str(rng.randint(100000, 999999))
    address = f"{number}, {street}, {city}"
    return Party(
        name=name,
        address=address,
        city=city,
        state=state,
        state_code=code,
        pincode=pincode,
        phone=fake_phone(rng),
        gstin=fake_gstin(rng, code),
    )


def make_seller(rng) -> Party:
    # Repeated seller identity makes the dataset resemble a real accounting
    # export while remaining fully synthetic.
    return Party(
        name="NOVA AUTOPARTS PRIVATE LIMITED",
        address="PLOT 17, INDUSTRIAL AREA, TRANSPORT NAGAR",
        city="Lucknow",
        state="Uttar Pradesh",
        state_code="09",
        pincode="226012",
        phone=fake_phone(rng),
        gstin=fake_gstin(rng, "09"),
    )


def random_date(rng) -> date:
    start = date(2025, 4, 1)
    end = date(2026, 3, 31)
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, days))


def make_items(rng, max_items=8) -> List[LineItem]:
    n = rng.randint(1, max_items)
    chosen = rng.sample(PRODUCTS, k=min(n, len(PRODUCTS)))
    items = []

    for desc, hsn, unit, low, high in chosen:
        if desc == "FREIGHT":
            qty = rng.randint(1, 4)
        elif unit in ("Nos", "Pcs", "Set"):
            qty = rng.choices(
                [rng.randint(1, 5), rng.randint(6, 30), rng.randint(31, 120)],
                weights=[45, 45, 10],
                k=1,
            )[0]
        else:
            qty = rng.randint(1, 25)

        # Strongly vary prices; occasionally use round/retail-like numbers.
        if rng.random() < 0.25:
            price = Decimal(str(rng.choice([
                round(rng.uniform(low, high), 0),
                round(rng.uniform(low, high), 1),
                round(rng.uniform(low, high), 2),
            ])))
        else:
            price = Decimal(str(round(rng.uniform(low, high), 2)))

        if rng.random() < 0.25:
            discount = Decimal(str(rng.choice([0, 5, 10, 12.5, 15.25, 25, 30, 39, 42.37, 47.45, 50])))
        else:
            discount = Decimal("0")

        # Most examples are 18%; include some legitimate variation.
        if desc == "FREIGHT":
            gst = Decimal("18")
        else:
            gst = Decimal(str(rng.choices(GST_RATES, weights=[4, 3, 75, 8])[0]))

        items.append(LineItem(
            description=desc,
            hsn=hsn,
            qty=qty,
            unit=unit,
            unit_price=price,
            discount_pct=discount,
            gst_rate=gst,
        ))
    return items


def totals(items: List[LineItem]) -> Dict[str, Decimal]:
    taxable = sum((i.taxable for i in items), Decimal("0"))
    cgst = sum((i.cgst for i in items), Decimal("0"))
    sgst = sum((i.sgst for i in items), Decimal("0"))
    total = money(taxable + cgst + sgst)
    return {
        "taxable": money(taxable),
        "cgst": money(cgst),
        "sgst": money(sgst),
        "tax": money(cgst + sgst),
        "total": total,
    }


def amount_in_words_indian(n: Decimal) -> str:
    # Good enough for invoice-style output; handles amounts up to crores.
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen",
            "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty",
            "Seventy", "Eighty", "Ninety"]

    def under_1000(x):
        parts = []
        if x >= 100:
            parts += [ones[x // 100], "Hundred"]
            x %= 100
        if x >= 20:
            parts.append(tens[x // 10])
            x %= 10
        if x:
            parts.append(ones[x])
        return " ".join(parts)

    value = int(n)
    if value == 0:
        return "Zero"

    groups = [
        (10_000_000, "Crore"),
        (100_000, "Lakh"),
        (1_000, "Thousand"),
        (1, ""),
    ]
    out = []
    remainder = value
    for divisor, label in groups:
        q, remainder = divmod(remainder, divisor)
        if q:
            out.append(under_1000(q))
            if label:
                out.append(label)
    return " ".join(out)


def choose_doc_type(rng, invoice_only=False):
    if invoice_only:
        return "tax_invoice"
    types = list(DOC_WEIGHTS.keys())
    weights = list(DOC_WEIGHTS.values())
    return rng.choices(types, weights=weights, k=1)[0]


def make_document(rng, serial: int, seller: Party | None = None, invoice_only=False):
    doc_type = choose_doc_type(rng, invoice_only)
    # Every document gets its own synthetic seller identity.
    seller = make_party(rng, "seller")
    buyer = make_party(rng, "buyer")
    dt = random_date(rng)
    items = make_items(rng)
    rng.shuffle(items)
    t = totals(items)

    if doc_type == "tax_invoice":
        prefix = "GST"
    elif doc_type == "debit_note":
        prefix = "DN"
    elif doc_type == "credit_note":
        prefix = "CN"
    elif doc_type == "purchase_bill":
        prefix = "PB"
    elif doc_type == "expense_receipt":
        prefix = "RC"
    elif doc_type == "utility_bill":
        prefix = "UB"
    else:
        prefix = "SO"

    # Unique document number: type + date-derived block + serial + random suffix.
    doc_no = f"{prefix}/{dt.strftime('%y%m%d')}/{serial:07d}-{rng.randint(100,999)}"

    payment_terms = rng.choice(["30 Days", "15 Days", "45 Days", "Immediate", "60 Days", "7 Days"])
    payment_mode = rng.choice(["CASH", "UPI", "NEFT", "RTGS", "CARD", "CHEQUE", "NET BANKING"])
    category = rng.choice([
        "Travel & Conveyance", "Meals & Entertainment", "Petrol & Fuel",
        "Office Expenses", "Software Subscription", "Stationery",
    ])
    provider = rng.choice([
        "UPPCL", "BSES Rajdhani", "TATA Power", "Adani Electricity",
        "Airtel Broadband", "Jio Fiber", "Jal Kal Dept.", "Mahanagar Gas",
    ])
    consumer_no = random_digits(rng, 10)
    account_name = rng.choice([
        "SHREE GANESH ELECTRONICS", "NOVA VENTURES", "APEX SUPPLIERS",
        "OM ENTERPRISES", "SRI BALAJI TRADERS",
    ])
    billing_start = random_date(rng)
    billing_end = billing_start + timedelta(days=rng.choice([28, 29, 30, 31]))
    units_consumed = rng.randint(40, 2500)
    due_date = dt + timedelta(days=rng.choice([7, 10, 15, 21]))

    return {
        "doc_type": doc_type,
        "doc_no": doc_no,
        "date": dt,
        "seller": seller,
        "buyer": buyer,
        "items": items,
        "totals": t,
        "transport": rng.choice([
            "BY AUTO", "BY BUS", "BY COURIER", "SELF",
            "TRANSPORT", "HAND DELIVERY",
        ]),
        "vehicle_no": "" if rng.random() < 0.6 else
            f"{rng.choice(['UP','DL','MH','KA','RJ','GJ'])}{rng.randint(10,99)}"
            f"{rng.choice(string.ascii_uppercase)}{rng.randint(1000,9999)}",
        "eway": "" if rng.random() < 0.65 else random_digits(rng, 12),
        "reference": f"PO/{dt.strftime('%y%m')}/{rng.randint(10000,99999)}",
        "reverse_charge": "N",
        "serial": serial,
        "payment_terms": payment_terms,
        "payment_mode": payment_mode,
        "category": category,
        "provider": provider,
        "consumer_no": consumer_no,
        "account_name": account_name,
        "billing_start": billing_start,
        "billing_end": billing_end,
        "units_consumed": units_consumed,
        "due_date": due_date,
    }


# ---------------------------------------------------------------------------
# PDF styling helpers
# ---------------------------------------------------------------------------

styles = getSampleStyleSheet()
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"

small = ParagraphStyle(
    "small", parent=styles["Normal"], fontName=FONT, fontSize=6.5,
    leading=7.4, spaceAfter=0
)
tiny = ParagraphStyle(
    "tiny", parent=small, fontSize=5.8, leading=6.6
)
normal = ParagraphStyle(
    "normal", parent=styles["Normal"], fontName=FONT, fontSize=7.2,
    leading=8.2, spaceAfter=0
)
bold = ParagraphStyle(
    "bold", parent=normal, fontName=FONT_BOLD
)
center = ParagraphStyle(
    "center", parent=normal, alignment=TA_CENTER
)
center_bold = ParagraphStyle(
    "center_bold", parent=center, fontName=FONT_BOLD
)
right = ParagraphStyle(
    "right", parent=normal, alignment=TA_RIGHT
)
right_bold = ParagraphStyle(
    "right_bold", parent=right, fontName=FONT_BOLD
)
title = ParagraphStyle(
    "title", parent=styles["Title"], fontName=FONT_BOLD, fontSize=14,
    leading=15, alignment=TA_CENTER, spaceAfter=1
)
subtitle = ParagraphStyle(
    "subtitle", parent=normal, alignment=TA_CENTER, fontSize=7.2, leading=8
)


def P(text, style=normal):
    return Paragraph(str(text).replace("&", "&amp;"), style)


def p_multiline(lines, style=small):
    safe = "<br/>".join(str(x).replace("&", "&amp;") for x in lines if x is not None)
    return Paragraph(safe, style)


def box_table(data, widths, row_heights=None, grid=False, valign="TOP",
               layout=None):
    # Tables are retained internally only for ReportLab positioning/alignment.
    # They are rendered WITHOUT visible borders, so the output has no table
    # boxes/grid around the content.
    t = Table(data, colWidths=widths, rowHeights=row_heights, hAlign="LEFT")
    pad = layout["pad"] if layout else 3
    row_pad = layout["row_pad"] if layout else 2
    line_width = layout["line_width"] if layout else 0.35
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), valign),
        ("LEFTPADDING", (0, 0), (-1, -1), pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (-1, -1), row_pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), row_pad),
    ]
    if grid:
        cmds.append(("GRID", (0, 0), (-1, -1), line_width, colors.black))
    t.setStyle(TableStyle(cmds))
    return t


def seller_header(doc, layout=None):
    seller = doc["seller"]
    layout = layout or choose_layout(42, doc["serial"])
    if doc["doc_type"] == "tax_invoice":
        heading = "TAX INVOICE"
    elif doc["doc_type"] == "debit_note":
        heading = "DEBIT NOTE"
    elif doc["doc_type"] == "credit_note":
        heading = "CREDIT NOTE"
    elif doc["doc_type"] == "purchase_bill":
        heading = "PURCHASE BILL"
    elif doc["doc_type"] == "expense_receipt":
        heading = "EXPENSE RECEIPT"
    elif doc["doc_type"] == "utility_bill":
        heading = "UTILITY BILL"
    else:
        heading = "SALES ORDER"

    # Header family changes the visual hierarchy, not just the data.
    family = layout["family"]
    if family in ("header_split", "asymmetric"):
        left = p_multiline([
            seller.name,
            "AUTOMOTIVE • ELECTRONICS • OFFICE EQUIPMENT",
            f"{seller.address}, {seller.city.upper()}",
        ], ParagraphStyle("hdr_left", parent=small, fontSize=8.2, leading=9.3))
        right = p_multiline([
            heading,
            f"GSTIN : {seller.gstin}",
            f"Tel. : {seller.phone}",
        ], ParagraphStyle("hdr_right", parent=small, fontSize=8.2,
                          leading=9.3, alignment=TA_RIGHT))
        t = Table([[left, right]], colWidths=[105*mm, 70*mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), layout["pad"]),
            ("RIGHTPADDING", (0, 0), (-1, -1), layout["pad"]),
            ("TOPPADDING", (0, 0), (-1, -1), layout["pad"]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), layout["pad"]),
            ("LINEBELOW", (0, 0), (-1, 0), layout["line_width"], colors.black),
        ]))
        return [t, Spacer(1, layout["header_gap"])]
    elif family in ("compact", "receipt_like"):
        compact_title = ParagraphStyle(
            "compact_title", parent=title, fontSize=layout["title_size"],
            leading=layout["title_size"] + 1
        )
        return [
            P(heading, compact_title),
            P(seller.name, bold),
            P(f"{seller.city.upper()}, {seller.state.upper()} • GSTIN {seller.gstin}", tiny),
            Spacer(1, layout["header_gap"]),
        ]
    else:
        varied_title = ParagraphStyle(
            "varied_title", parent=title, fontSize=layout["title_size"],
            leading=layout["title_size"] + 1
        )
        lines = [
            P(heading, center_bold),
            P(seller.name, varied_title),
            P("AUTOMOTIVE • ELECTRONICS • OFFICE EQUIPMENT • GENERAL TRADING", subtitle),
            P(f"{seller.address}, {seller.city.upper()}, {seller.state.upper()} - {seller.pincode}", subtitle),
            P(f"<b>GSTIN : {seller.gstin}</b>", subtitle),
            P(
            f"Tel. : {seller.phone} &nbsp;&nbsp; "
            f"Email : accounts@{seller.name.lower().replace(' ', '').replace('&', 'and')[:18]}.example",
            subtitle
        ),
            Spacer(1, layout["header_gap"]),
        ]
        return lines


def party_block(label: str, party: Party):
    return p_multiline([
        f"<b>{label}</b>",
        party.name,
        party.address,
        f"{party.city}, {party.state} - {party.pincode}",
        "",
        f"Party Mobile No : {party.phone}",
        f"Party Aadhaar No : SYNTHETIC-{party.phone[-4:]}",
        f"GSTIN / UIN : {party.gstin}",
    ], small)


def meta_block(doc, layout=None):
    d = doc["date"].strftime("%d-%m-%Y")
    if doc["doc_type"] == "tax_invoice":
        left = [
            f"Invoice No.       : {doc['doc_no']}",
            f"Dated             : {d}",
            f"Place of Supply   : {doc['buyer'].state} ({doc['buyer'].state_code})",
            f"Reverse Charge    : {doc['reverse_charge']}",
            f"Reference          : {doc['reference']}",
        ]
    elif doc["doc_type"] == "debit_note":
        left = [
            f"Dr. Note No.      : {doc['doc_no']}",
            f"Dr. Note Date     : {d}",
            f"Original Inv. No. : {doc['reference']}",
            f"Original Inv. Date: {d}",
            f"GR/RR No.         : -",
        ]
    elif doc["doc_type"] == "credit_note":
        left = [
            f"Credit Note No.   : {doc['doc_no']}",
            f"Credit Note Date  : {d}",
            f"Against Invoice   : {doc['reference']}",
            f"Reason            : Rate / quantity adjustment",
            f"Reference         : CN/{doc['serial']:06d}",
        ]
    elif doc["doc_type"] == "purchase_bill":
        left = [
            f"Bill No.          : {doc['doc_no']}",
            f"Bill Date         : {d}",
            f"Vendor Ref        : {doc['reference']}",
            f"Payment Terms     : {doc['payment_terms']}",
            f"Mode of Payment   : {doc['payment_mode']}",
        ]
    elif doc["doc_type"] == "expense_receipt":
        left = [
            f"Receipt No.       : {doc['doc_no']}",
            f"Receipt Date      : {d}",
            f"Category          : {doc['category']}",
            f"Payment Mode      : {doc['payment_mode']}",
            f"Reference         : {doc['reference']}",
        ]
    elif doc["doc_type"] == "utility_bill":
        billing_period = (
            f"{doc['billing_start'].strftime('%d-%m-%Y')} "
            f"to {doc['billing_end'].strftime('%d-%m-%Y')}"
        )
        left = [
            f"Consumer No.      : {doc['consumer_no']}",
            f"Bill Date         : {d}",
            f"Due Date          : {doc['due_date'].strftime('%d-%m-%Y')}",
            f"Billing Period    : {billing_period}",
            f"Account Name      : {doc['account_name']}",
        ]
    else:
        left = [
            f"Order No          : {doc['doc_no']}",
            f"Order Date        : {d}",
            f"Ref No            : {doc['reference']}",
            f"PO Date           : {d}",
            f"Payment Terms     : 30 Days",
        ]

    if doc["doc_type"] == "utility_bill":
        right = [
            f"Provider          : {doc['provider']}",
            f"Units Consumed    : {doc['units_consumed']}",
            f"Tariff / Meter No : {doc['consumer_no'][-6:]}",
            f"Bill Amount Due   : {fmt_money(doc['totals']['total'])}",
        ]
    else:
        right = [
            f"Transport         : {doc['transport']}",
            f"Vehicle No.       : {doc['vehicle_no'] or '-'}",
            f"E-Way Bill No.    : {doc['eway'] or '-'}",
            f"No. Of Packages   : {max(1, len(doc['items']) // 2)}",
            f"Supply State      : {doc['buyer'].state}",
        ]
    if layout and layout["family"] in ("meta_split", "ledger", "wide_items"):
        widths = [72*mm, 104*mm]
    elif layout and layout["family"] == "asymmetric":
        widths = [103*mm, 73*mm]
    else:
        widths = [88*mm, 88*mm]
    return box_table([
        [p_multiline(left, small), p_multiline(right, small)]
    ], widths, layout=layout)


def items_table(doc, layout=None):
    items = doc["items"]
    # 10 columns in the same general family as the supplied documents.
    headers = [
        "S.N.", "Description of Goods", "HSN/SAC", "Qty.", "Unit",
        "Price", "CGST\nRate", "CGST\nAmount", "SGST\nRate", "SGST\nAmount", "Amount"
    ]

    data = [[P(h, center_bold) for h in headers]]
    for idx, item in enumerate(items, 1):
        data.append([
            P(idx, center),
            P(item.description, small),
            P(item.hsn, center),
            P(fmt_qty(item.qty), right),
            P(item.unit, center),
            P(fmt_money(item.unit_price), right),
            P(f"{item.gst_rate:.2f} %", center),
            P(fmt_money(item.cgst), right),
            P(f"{item.gst_rate:.2f} %", center),
            P(fmt_money(item.sgst), right),
            P(fmt_money(item.total), right),
        ])

    # Fill a little vertical space so the document resembles the source format,
    # without bloating the token count (blank rows add no words but each item
    # row carries 11 numeric cells that inflate subword tokens past LayoutLM's
    # 512-token window, truncating the amount fields).
    min_rows = 2
    while len(data) < min_rows + 1:
        data.append([""] * len(headers))

    # Item-table geometry varies enough to move columns around.
    if layout and layout["family"] == "wide_items":
        widths = [7*mm, 55*mm, 16*mm, 12*mm, 10*mm, 18*mm, 13*mm, 18*mm, 13*mm, 18*mm, 18*mm]
    elif layout and layout["family"] == "compact":
        widths = [7*mm, 42*mm, 16*mm, 12*mm, 10*mm, 15*mm, 13*mm, 17*mm, 13*mm, 17*mm, 19*mm]
    elif layout and layout["family"] == "receipt_like":
        widths = [8*mm, 66*mm, 17*mm, 14*mm, 17*mm, 20*mm, 18*mm, 18*mm, 18*mm, 18*mm, 14*mm]
    else:
        widths = [7*mm, 46*mm, 16*mm, 12*mm, 10*mm, 18*mm, 13*mm, 18*mm, 13*mm, 18*mm, 17*mm]
    t = box_table(data, widths, grid=False, layout=layout)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        # No GRID/BOX: content remains free-standing text.
    ]))
    return t


def tax_summary(doc, layout=None):
    items = doc["items"]
    rates = {}
    for item in items:
        key = item.gst_rate
        if key not in rates:
            rates[key] = {"taxable": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0")}
        rates[key]["taxable"] += item.taxable
        rates[key]["cgst"] += item.cgst
        rates[key]["sgst"] += item.sgst

    rows = [[
        P("HSN/SAC", center_bold), P("Tax Rate", center_bold),
        P("Taxable Amt.", center_bold), P("CGST Amt.", center_bold),
        P("SGST Amt.", center_bold), P("Total Tax", center_bold)
    ]]
    for rate, vals in sorted(rates.items(), key=lambda x: float(x[0])):
        total_tax = vals["cgst"] + vals["sgst"]
        rows.append([
            P("Multiple" if len(rates) > 1 else items[0].hsn, center),
            P(f"{rate:.0f}%", center),
            P(fmt_money(money(vals["taxable"])), right),
            P(fmt_money(money(vals["cgst"])), right),
            P(fmt_money(money(vals["sgst"])), right),
            P(fmt_money(money(total_tax)), right),
        ])

    tax_widths = ([21, 22, 29, 26, 26, 24] if layout and layout["family"] == "ledger"
                  else [24, 19, 30, 25, 25, 25])
    t = box_table(rows, [x*mm for x in tax_widths], grid=False, layout=layout)
    return t


def totals_block(doc, layout=None):
    t = doc["totals"]
    total = t["total"]

    summary = Table([
        [P("Taxable Amount", bold), P(fmt_money(t["taxable"]), right)],
        [P("CGST", normal), P(fmt_money(t["cgst"]), right)],
        [P("SGST", normal), P(fmt_money(t["sgst"]), right)],
        [P("Total Tax", normal), P(fmt_money(t["tax"]), right)],
        [P("Grand Total", bold), P(fmt_money(total), right_bold)],
    ], colWidths=[38*mm, 34*mm], hAlign="RIGHT")
    summary.setStyle(TableStyle([
        # No visible grid around the totals.
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    return [
        Table([
            [P(f"Grand Total    {sum(i.qty for i in doc['items']):.2f} Units", bold),
             summary]
        ], colWidths=[92*mm, 72*mm], hAlign="LEFT",
           style=TableStyle([
               ("VALIGN", (0, 0), (-1, -1), "TOP"),
               ("BOX", (1, 0), (1, 0), 0.35, colors.black),
               ("LEFTPADDING", (0, 0), (-1, -1), 2),
               ("RIGHTPADDING", (0, 0), (-1, -1), 2),
               ("TOPPADDING", (0, 0), (-1, -1), 2),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
           ])),
        Spacer(1, 2),
    ]


def footer_block(doc, layout=None):
    seller = doc["seller"]
    bank_rng = random.Random(doc["serial"] * 7919 + 17)
    bank_name = rng_choice = bank_rng.choice([
        "SYNTHETIC BANK", "NATIONAL SAMPLE BANK", "DEMO COMMERCIAL BANK",
        "FICTIONAL MERCHANT BANK", "SAMPLE FINANCE BANK"
    ])
    account_no = "".join(bank_rng.choice(string.digits) for _ in range(12))
    ifsc = "SYNTH" + "".join(bank_rng.choice(string.ascii_uppercase + string.digits) for _ in range(7))
    bank = f"{seller.name} • {bank_name} • A/C NO. {account_no} • IFSC {ifsc}"
    return [
        P("<b>Bank Detail</b>", center_bold),
        P(bank, center),
        Spacer(1, 2),
        P(f"<b>For {seller.name}</b>", bold),
        Spacer(1, 2),
    ]


def build_pdf(doc, path: Path, layout=None):
    layout = layout or choose_layout(42, doc["serial"])
    family = layout["family"]

    pdf = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=layout["right"],
        leftMargin=layout["left"],
        topMargin=layout["top"],
        bottomMargin=layout["bottom"],
        title=f"{doc['doc_type']} {doc['doc_no']}",
        author="Synthetic Document Generator",
    )

    story = []

    # Different families reorder major blocks. This is the main source of
    # structural diversity; jitter then changes the exact geometry per file.
    story.extend(seller_header(doc, layout))

    party = box_table(
        [[party_block("Billed to :", doc["buyer"])]],
        [176*mm],
        row_heights=[layout["buyer_height"]],
        layout=layout,
    )

    if family in ("buyer_right", "asymmetric"):
        seller = doc["seller"]
        buyer = doc["buyer"]
        buyer_box = box_table(
            [[party_block("Billed to :", buyer),
              p_multiline([
                  "<b>Dispatch / Contact</b>",
                  seller.city,
                  seller.state,
                  f"Phone: {seller.phone}",
                  f"GSTIN: {seller.gstin}",
              ], small)]],
            [105*mm, 71*mm],
            row_heights=[layout["buyer_height"]],
            layout=layout,
        )
        story.append(buyer_box)
    elif family == "minimal":
        story.append(party)
    else:
        story.append(party)

    story.append(Spacer(1, layout["section_gap"]))

    meta = meta_block(doc, layout)
    if family in ("meta_split", "ledger"):
        story.append(meta)
        story.append(Spacer(1, layout["extra_spacer"]))
        story.append(items_table(doc, layout))
    elif family == "dense":
        story.append(items_table(doc, layout))
        story.append(Spacer(1, layout["section_gap"]))
        story.append(meta)
    elif family == "receipt_like":
        story.append(items_table(doc, layout))
        story.append(Spacer(1, layout["extra_spacer"]))
        story.append(meta)
    else:
        story.append(meta)
        story.append(Spacer(1, layout["section_gap"]))
        story.append(items_table(doc, layout))

    story.append(Spacer(1, layout["section_gap"]))

    if doc["doc_type"] not in ("sales_order", "expense_receipt", "utility_bill"):
        if family in ("boxed_sections", "ledger", "wide_items"):
            story.append(tax_summary(doc, layout))
            story.append(Spacer(1, layout["section_gap"]))
            story.extend(totals_block(doc, layout))
        else:
            story.append(tax_summary(doc, layout))
            story.extend(totals_block(doc, layout))
    else:
        story.extend(totals_block(doc, layout))

    # Some families move the footer before the final note, others keep it at
    # the very bottom. The content remains synthetic in every case.
    story.append(Spacer(1, layout["extra_spacer"] if family in ("compact", "receipt_like") else 2))
    story.extend(footer_block(doc, layout))

    if layout["show_disclaimer"]:
        story.append(Spacer(1, layout["section_gap"]))
        disc_style = ParagraphStyle(
            f"disc_{doc['serial']}",
            parent=tiny,
            alignment=TA_CENTER,
            fontName=FONT_BOLD,
            fontSize=random.Random(doc["serial"] * 31).uniform(5.0, 6.8),
        )
        story.append(P(
            "SYNTHETIC SAMPLE • NOT A VALID TAX DOCUMENT • GENERATED FOR DATA/ML TESTING",
            disc_style
        ))

    def draw_page(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(layout["line_width"])

        # Page borders are now rare; content itself is never enclosed in
        # table-style borders.
        if layout["show_page_border"] and family in ("minimal", "receipt_like"):
            canvas.rect(
                layout["left"] * 0.65,
                layout["bottom"] * 0.65,
                PAGE_W - layout["left"] * 1.3 - layout["right"] * 0.65,
                PAGE_H - layout["top"] * 1.2 - layout["bottom"] * 0.65,
            )
        elif layout["show_page_border"] and family in ("asymmetric", "header_split"):
            canvas.line(layout["left"], PAGE_H - layout["top"] * 1.6,
                        PAGE_W - layout["right"], PAGE_H - layout["top"] * 1.6)
            canvas.rect(
                layout["left"], layout["bottom"],
                PAGE_W - layout["left"] - layout["right"],
                PAGE_H - layout["top"] - layout["bottom"],
            )
        elif layout["show_page_border"]:
            canvas.rect(
                layout["left"], layout["bottom"],
                PAGE_W - layout["left"] - layout["right"],
                PAGE_H - layout["top"] - layout["bottom"],
            )

        if layout["show_original"]:
            canvas.setFont(FONT_OBLIQUE, random.uniform(5.5, 7.5))
            canvas.drawRightString(
                PAGE_W - layout["right"] - random.uniform(0, 5),
                PAGE_H - layout["top"] + random.uniform(0, 3),
                random.choice(["Original Copy", "Office Copy", "Customer Copy", "Duplicate Copy"])
            )
        canvas.restoreState()

    pdf.build(story, onFirstPage=draw_page)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=Path("synthetic_docs"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--invoice-only", action="store_true",
        help="Generate only TAX INVOICE documents."
    )
    ap.add_argument(
        "--layout-change-every", type=int, default=7,
        help="Switch to a substantially different layout family every N documents."
    )
    args = ap.parse_args()
    global LAYOUT_CHANGE_EVERY
    LAYOUT_CHANGE_EVERY = max(1, args.layout_change_every)

    if args.count < 1:
        raise SystemExit("--count must be >= 1")

    args.out.mkdir(parents=True, exist_ok=True)
    for sub in ("tax_invoice", "debit_note", "credit_note", "sales_order",
                "purchase_bill", "expense_receipt", "utility_bill"):
        (args.out / sub).mkdir(exist_ok=True)

    rng = random.Random(args.seed)

    manifest_path = args.out / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "serial", "document_type", "document_number", "date",
            "seller", "buyer", "buyer_state", "buyer_gstin",
            "item_count", "taxable_amount", "cgst", "sgst",
            "tax_amount", "grand_total", "file"
        ])
        writer.writeheader()

        for serial in range(1, args.count + 1):
            doc = make_document(rng, serial, None, args.invoice_only)
            folder = args.out / doc["doc_type"]
            filename = f"{doc['doc_no']}.pdf"
            path = folder / filename

            build_pdf(doc, path, choose_layout(args.seed, serial))

            writer.writerow({
                "serial": serial,
                "document_type": doc["doc_type"],
                "document_number": doc["doc_no"],
                "date": doc["date"].isoformat(),
                "seller": doc["seller"].name,
                "buyer": doc["buyer"].name,
                "buyer_state": doc["buyer"].state,
                "buyer_gstin": doc["buyer"].gstin,
                "item_count": len(doc["items"]),
                "taxable_amount": fmt_money(doc["totals"]["taxable"]),
                "cgst": fmt_money(doc["totals"]["cgst"]),
                "sgst": fmt_money(doc["totals"]["sgst"]),
                "tax_amount": fmt_money(doc["totals"]["tax"]),
                "grand_total": fmt_money(doc["totals"]["total"]),
                "file": str(path),
            })

            if serial % 100 == 0 or serial == args.count:
                print(f"Generated {serial}/{args.count}")

    print(f"\nDone.")
    print(f"PDFs:     {args.out.resolve()}")
    print(f"Manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
