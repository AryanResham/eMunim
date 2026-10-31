"""Fresh schema-aligned synthetic documents, with disjoint layout-family splits."""
import argparse
import random
from datetime import date, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from common import HERE, LABEL_SETS, normalize_box, validate_row, write_json, write_rows

TITLES = {"GST_INVOICE":"TAX INVOICE", "PURCHASE_BILL":"PURCHASE BILL", "EXPENSE_RECEIPT":"EXPENSE RECEIPT", "UTILITY_BILL":"UTILITY BILL", "CREDIT_NOTE":"CREDIT NOTE", "DEBIT_NOTE":"DEBIT NOTE"}
ALIASES = {"invoice_no":["Invoice No", "Invoice #", "Invoice Number"],"vendor_name":["Supplier", "Seller", "Vendor Name"],"buyer_name":["Bill To", "Customer", "Buyer Name"],"total_amount":["Grand Total", "Invoice Total", "Total Amount"],"vendor_gstin":["Supplier GSTIN", "Seller GSTIN", "GSTIN"],"taxable_amount":["Taxable Value", "Taxable Amount", "Net Taxable"],"invoice_date":["Invoice Date", "Date of Issue", "Date"]}


def gstin(rng):
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    prefix = f"{rng.randint(1,37):02d}" + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5)) + f"{rng.randrange(10000):04d}" + rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + "1Z"
    total, factor = 0, 2
    for character in reversed(prefix):
        value = factor * alphabet.index(character)
        total += value // 36 + value % 36
        factor = 1 if factor == 2 else 2
    return prefix + alphabet[(36 - total % 36) % 36]


def values_for(doc_type, family, index, rng):
    stamp = date(2025,1,1) + timedelta(days=rng.randrange(365))
    fmt = rng.choice(["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"])
    taxable = rng.randint(100,50000)
    interstate = rng.choice([True,False])
    rate = rng.choice([0,5,12,18,28])
    tax = taxable * rate / 100
    values = {"invoice_no":f"INV-{family}-{index:05d}","invoice_date":stamp.strftime(fmt),
        "vendor_name":f"{rng.choice(['Aster','Cedar','Delta','Maple','Orion'])} {family} Supplies",
        "vendor_gstin":gstin(rng),"buyer_name":f"{rng.choice(['Lotus','River','Summit','Valley'])} {family} Traders",
        "buyer_gstin":gstin(rng),"taxable_amount":f"{taxable:,.2f}","cgst_amount":f"{0 if interstate else tax/2:,.2f}",
        "sgst_amount":f"{0 if interstate else tax/2:,.2f}","igst_amount":f"{tax if interstate else 0:,.2f}",
        "total_amount":f"{taxable+tax:,.2f}","due_date":(stamp+timedelta(days=30)).strftime(fmt),"po_number":f"PO-{family}-{index:05d}",
        "bill_no":f"BILL-{family}-{index:05d}","bill_date":stamp.strftime(fmt),"subtotal":f"{taxable:,.2f}","tax_amount":f"{tax:,.2f}",
        "payment_terms":rng.choice(["Net 30 days","Due on receipt","Net 15 days"]),"receipt_no":f"RCPT-{family}-{index:05d}",
        "receipt_date":stamp.strftime(fmt),"amount":f"{taxable+tax:,.2f}","payment_mode":rng.choice(["Cash","UPI","Card"]),
        "category":rng.choice(["Meals","Travel","Office Supplies"]),"consumer_no":f"{family}{index:08d}",
        "billing_period":stamp.strftime("%B %Y"),"units_consumed":str(rng.randint(10,800)),"amount_due":f"{taxable:,.2f}",
        "utility_provider":f"{family} {rng.choice(['Electricity','Water','Gas'])} Services","account_name":f"{family} Trading Company",
        "credit_note_no":f"CN-{family}-{index:05d}","credit_note_date":stamp.strftime(fmt),"original_invoice_no":f"INV-{family}-{index:05d}",
        "reason":rng.choice(["Goods returned","Price adjustment","Additional supplies"]),"credit_amount":f"{taxable+tax:,.2f}","tax_credit":f"{tax:,.2f}",
        "debit_note_no":f"DN-{family}-{index:05d}","debit_note_date":stamp.strftime(fmt),"debit_amount":f"{taxable+tax:,.2f}"}
    fields = {label[2:].lower():values[label[2:].lower()] for label in LABEL_SETS[doc_type] if label.startswith("B-")}
    for key in ("po_number","due_date","buyer_gstin"):
        if key in fields and rng.random() < .2:
            fields[key] = None
    return fields


def render(doc_type, family_number, index, split, destination):
    rng = random.Random(42 + family_number * 100003 + index * 101 + list(TITLES).index(doc_type) * 10000019)
    family = f"F{family_number:02d}"
    width, height = rng.choice([(1200,1600),(1400,1800)])
    image = Image.new("RGB", (width,height), rng.choice(["white", "#faf9f4", "#f7f8fb"]))
    draw = ImageDraw.Draw(image)
    fonts = [p for p in [Path("C:/Windows/Fonts/arial.ttf"),Path("C:/Windows/Fonts/times.ttf"),Path("C:/Windows/Fonts/cour.ttf")] if p.exists()]
    font_path = fonts[family_number % len(fonts)]
    font = ImageFont.truetype(str(font_path),rng.choice([22,24,26,28]))
    heading = ImageFont.truetype(str(font_path),34)
    words, boxes, labels = [], [], []

    def line(text,x,y,label=None,max_width=None):
        initial_x = x
        for i, word in enumerate(text.split()):
            if max_width and x + draw.textlength(word,font=font) > initial_x+max_width:
                y += font.size+7
                x = initial_x
            box = [int(v) for v in draw.textbbox((x,y),word,font=font)]
            if box[2] >= width or box[3] >= height:
                raise ValueError("Synthetic text overflow")
            draw.text((x,y),word,font=font,fill="#111111")
            words.append(word)
            boxes.append(normalize_box(box,width,height))
            labels.append("O" if label is None else ("B-" if i==0 else "I-")+label)
            x += draw.textlength(word+" ",font=font)

    # All OCR words, including the title, are represented in the training record.
    line(TITLES[doc_type],60 if family_number%3 else width//3,35)
    fields = values_for(doc_type,family,index,rng)
    keys = list(fields)
    random.Random(family_number).shuffle(keys)
    columns = 2 if family_number%4 in (1,2) else 1
    rows_per_column = (len(keys)+columns-1)//columns
    draw.line((45,105,width-45,105),fill="#777777",width=2)
    for position,key in enumerate(keys):
        if fields[key] is None:
            continue
        column, row = divmod(position,rows_per_column)
        x = 60 + column*(width//2)
        y = 150 + row*(86 if columns==1 else 122)
        caption = rng.choice(ALIASES.get(key,[key.replace("_"," ").title()]))
        if columns==1 and family_number%4==0:
            line(caption+":",x,y)
            line(fields[key],width//2,y,key.upper(),width//2-85)
        else:
            line(caption+":",x,y)
            line(fields[key],x,y+font.size+8,key.upper(),width//columns-100)
    line("Thank you for your business",60,height-70)
    if family_number%5==0:
        image = image.filter(ImageFilter.GaussianBlur(.35))
    identity = f"{doc_type.lower()}-{split}-{family}-{index:05d}"
    path = destination / "images" / (identity+".jpg")
    path.parent.mkdir(parents=True,exist_ok=True)
    image.save(path,quality=rng.choice([65,80,95]))
    image.close()
    record = dict(id=identity,image=path.relative_to(HERE).as_posix(),words=words,boxes=boxes,labels=labels,fields=fields,group=family,doc_type=doc_type,split=split,provenance="generator_exact")
    validate_row(record,LABEL_SETS[doc_type])
    return record


def prepare_synthetic(train_count=1000,development_count=150,test_count=150):
    for doc_type in TITLES:
        folder = HERE / "data/synthetic" / doc_type.lower()
        marker = folder / "provenance.json"
        if marker.exists():
            old = __import__('json').loads(marker.read_text())
            if old["counts"] != dict(train=train_count,development=development_count,test=test_count):
                raise ValueError("Existing synthetic dataset has different counts; use a new version, do not silently overwrite")
            continue
        for split,count,families in (("train",train_count,range(28)),("development",development_count,range(28,34)),("test",test_count,range(34,40))):
            rows = [render(doc_type,families[i%len(families)],i,split,folder) for i in range(count)]
            write_rows(folder/(split+".jsonl"),rows)
        write_json(marker,dict(version="synthetic-v2",seed=42,counts=dict(train=train_count,development=development_count,test=test_count),family_splits=dict(train=[0,27],development=[28,33],test=[34,39]),labels=LABEL_SETS[doc_type],limitations="Parametric layout families, not 40 independently authored templates; exact OCR only; no real MSME training"))
        print("Generated",doc_type,flush=True)


if __name__ == "__main__":
    prepare_synthetic()
