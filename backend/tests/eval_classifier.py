"""
eval_classifier.py — Evaluate L1 regex + L2 zero-shot classifier.

Test set: 60 hand-crafted OCR text snippets (10 per class), each covering
realistic variance in Indian business document language.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.classifier.l1_regex import classify_l1
from services.classifier.classifier_pipeline import classify_document
from utils.confidence_config import CLASSIFIER_L1_THRESHOLD

# fmt: off
TEST_SET = [
    # ---- GST_INVOICE (10) ----
    ("GST_INVOICE", "TAX INVOICE\nVendor: ANTAK CREATIONS\nGSTIN: 09ADMPT7817M1ZK\nInvoice No: GST-570\nDate: 22-04-2026\nTotal: ₹32,899.00\nCGST: ₹2,509.23  SGST: ₹2,509.23"),
    ("GST_INVOICE", "GST INVOICE\nBill To: Vibhu Automobile\nBuyer GSTIN: 09CPFPD0390L1ZS\nTaxable Value: 27880.32\nIGST @18%: 5018.46\nGrand Total: 32898.78"),
    ("GST_INVOICE", "ORIGINAL TAX INVOICE\nM/s Sharma Traders\n27AABCU9603R1ZM\nInvoice: INV/2025-26/001\nHSN: 8471  GST Rate: 18%\nTotal Amount: 15,340.00"),
    ("GST_INVOICE", "Invoice\nSupplier GSTIN: 24AADCB2230M1Z3\nDate: 15/03/2026\nItem: Office Supplies\nSub Total: 8500\nCGST 9%: 765  SGST 9%: 765\nNet Payable: 10,030"),
    ("GST_INVOICE", "B2B TAX INVOICE\nIRN: a3bc8...\nAck No: 112340001\n19AAACH7409R1ZZ\nInvoice Date: 01-04-2026\nTotal Tax: 3600  Total: 23600"),
    ("GST_INVOICE", "INVOICE\nFrom: Raj Electricals 29GGGGG1314R9Z6\nTo: Green Mart Pvt Ltd\nInv No: RE/26-27/1045\nBasic: 50000  IGST 12%: 6000\nTotal: 56000"),
    ("GST_INVOICE", "TAX INVOICE cum DELIVERY CHALLAN\n33AAHCM8432L1ZB\nDate: 07-04-2026\nProduct: Industrial Valves\nQty: 50  Rate: 420  Amt: 21000\nCGST: 1890  SGST: 1890  Total: 24780"),
    ("GST_INVOICE", "GST Tax Invoice\nRegistered under GST: 07AAACR5055K1Z4\nInvoice #: NV-00291\nTotal before tax: 12,400\nGST @5%: 620\nFinal Amount: 13,020"),
    ("GST_INVOICE", "Invoice\nGSTIN of Supplier: 32AABCM8732G1ZK\nPlace of Supply: Kerala\nValue of Supply: 9875.00\nCGST @9%: 888.75  SGST @9%: 888.75\nRound off: 0.50  Total: 11653.00"),
    ("GST_INVOICE", "REVISED TAX INVOICE\n06AAGCM4128P1ZX\nOriginal Invoice No: TI/001\nAmount Revised: 45600\nIGST 18%: 8208\nPayable: 53808"),

    # ---- PURCHASE_BILL (10) ----
    ("PURCHASE_BILL", "PURCHASE ORDER\nPO No: PO-2026-0412\nDate: 10-04-2026\nItem: Raw Cotton  Qty: 500kg  Rate: 85/kg\nAmount: 42,500\nDelivery: Within 15 days"),
    ("PURCHASE_BILL", "VENDOR BILL\nBill No: VB/26-27/089\nSupplier: Kumar Textiles\nFabric Roll x 20 @ 1200 = 24,000\nFreight: 500  Total: 24,500\nDue: 30 days"),
    ("PURCHASE_BILL", "PURCHASE BILL\nFrom: National Hardware Depot\nDate: 05-04-2026\nMS Pipe 2 inch x 100m: 15,000\nBolts & Nuts: 800\nTotal: 15,800  Tax Extra"),
    ("PURCHASE_BILL", "Purchase Order\nRef: MRP-556\nTo: Sunrise Chemicals Pvt Ltd\nSolvent 200L @ 180/L: 36,000\nDrum deposit: 2,000\nTotal Bill: 38,000"),
    ("PURCHASE_BILL", "PURCHASE BILL\nM/s Apex Polymers\nDate: 12-04-2026\nPP Granules 1MT: 87,500\nPacking: 500\nPayable: 88,000  Payment: NEFT"),
    ("PURCHASE_BILL", "Purchase Order No. ORD-2026-1124\nItems: Printer Cartridges x12 @ 650 = 7,800\nA4 Paper 10 ream @ 280 = 2,800\nTotal: 10,600  GST as applicable"),
    ("PURCHASE_BILL", "VENDOR BILL\nSupplier: Modern Pumps\nDate: 18-04-2026\nSubmersible Pump 5HP x 2: 28,000\nInstallation: 3,000\nBill Total: 31,000"),
    ("PURCHASE_BILL", "Purchase Bill\nBuyer: Sunrise Foods Ltd\nDate: 21-04-2026\nSoyabean Oil 50L cans x10 @ 1350: 13,500\nFreight included\nPayable: 13,500"),
    ("PURCHASE_BILL", "PURCHASE ORDER\nFrom: Phoenix Stationery\nPaper Reams: 5,600\nInk Cartridges: 3,200\nFiles & Folders: 1,200\nTotal: 10,000\nDelivery: Immediate"),
    ("PURCHASE_BILL", "VENDOR BILL\nNo: VB-0089\nSupplier: Classic Tools\nSpanner Set: 1,800  Drill Bits: 2,400  Total: 4,200\nPayment by cheque"),

    # ---- EXPENSE_RECEIPT (10) ----
    ("EXPENSE_RECEIPT", "RECEIPT\nDate: 22-04-2026\nReceived from: Rahul Sharma\nToward: Travel expenses Mumbai–Pune\nAmount: ₹850\nCash Paid\nSignature: _______"),
    ("EXPENSE_RECEIPT", "PETTY CASH RECEIPT\nVoucher No: PCR-044\nDate: 20-04-2026\nPurpose: Office stationery\nAmount: ₹320\nPaid by: Cash\nApproved by: Manager"),
    ("EXPENSE_RECEIPT", "EXPENSE RECEIPT\nDate: 19-04-2026\nEmployee: Priya Mehta\nClaim: Client dinner at Hotel Sagar\nBill Amount: ₹3,200\nReimbursable: Yes"),
    ("EXPENSE_RECEIPT", "Receipt\nFuel Petrol 12L @ 95.5 = ₹1,146\nDate: 18-04-2026\nVehicle: MH12-AB-1234\nPump: HP Petrol Station, Pune"),
    ("EXPENSE_RECEIPT", "RECEIPT\nSoftware Subscription: Adobe Creative Cloud\nAmount: ₹5,999/year\nDate: 15-04-2026\nMode: Credit Card\nTxn ID: TXN88923411"),
    ("EXPENSE_RECEIPT", "Expense Receipt\nCourier charges – Bluedart\nDate: 14-04-2026\nWeight: 2.5kg  Destination: Delhi\nAmt: ₹420  GST included"),
    ("EXPENSE_RECEIPT", "PETTY CASH VOUCHER\nNo: PCV-19\nDate: 13-04-2026\nAmt: ₹180  Particulars: Printing & photocopying\nCash disbursed to: Office boy"),
    ("EXPENSE_RECEIPT", "Receipt\nDate: 10-04-2026\nTaxi fare – Ola\nRoute: Airport to Office\nTotal Fare: ₹742\nPaid via: Ola Money"),
    ("EXPENSE_RECEIPT", "RECEIPT\nDate: 08-04-2026\nConference registration fee\nEvent: IndiaAI Summit 2026\nAmount: ₹2,500  Mode: UPI"),
    ("EXPENSE_RECEIPT", "Meal Receipt\nRestaurant: Cafe Coffee Day\nDate: 06-04-2026\nItems: 3x Coffee ₹120, 2x Sandwich ₹220\nTotal: ₹580  GST: ₹52\nPaid: UPI"),

    # ---- UTILITY_BILL (10) ----
    ("UTILITY_BILL", "ELECTRICITY BILL\nConsumer No: 140012345678\nBilling Period: Mar 2026\nMESEB\nUnits Consumed: 420\nAmount Due: ₹3,318\nDue Date: 05-05-2026"),
    ("UTILITY_BILL", "WATER BILL\nMunicipal Corporation of Pune\nAccount: WS-004-2234\nBilling Period: Feb–Mar 2026\nCharges: ₹480\nSewage: ₹96\nTotal: ₹576  Due: 30-04-2026"),
    ("UTILITY_BILL", "GAS BILL\nMahanagar Gas Limited\nCustomer No: MGL-78321\nMonth: March 2026\nConsumption: 15.3 SCM\nBill Amount: ₹820\nPay before: 20-04-2026"),
    ("UTILITY_BILL", "INTERNET BILL\nJio Fiber\nAccount: JF-MH-009812\nPlan: 300 Mbps  Period: Apr 2026\nPlan Charge: ₹999\nGST 18%: ₹179.82\nTotal: ₹1,178.82"),
    ("UTILITY_BILL", "BROADBAND BILL\nACT Fibernet\nCust ID: ACT-BLR-441\nSubscription: Apr 2026\nAmount: ₹849\nIncl. GST\nAuto-debit on 05-Apr-2026"),
    ("UTILITY_BILL", "TELEPHONE BILL\nBSNL Landline\nPhone No: 022-23456789\nBill Month: March 2026\nRental: ₹125  Calls: ₹43\nGST: ₹30  Total: ₹198\nDue: 25-04-2026"),
    ("UTILITY_BILL", "ELECTRICITY BILL\nTorrent Power Ltd\nConnection No: 1100099887\nBilling Cycle: 15 Mar – 14 Apr 2026\nFixed Charges: ₹120  Energy: ₹2,840\nTotal Payable: ₹2,960"),
    ("UTILITY_BILL", "WATER BILL\nBMC Mumbai\nConsumer: 1234AB\nPeriod: Q1 2026\nKL Consumed: 42\nCharges: ₹630  Late fee: ₹63\nPayable: ₹693"),
    ("UTILITY_BILL", "GAS BILL\nIndraprastha Gas Ltd\nBP No: IGL-00293812\nFor Month: Mar 2026\nUnits: 18.7 SCM  Rate: 53.59/SCM\nAmount: ₹1,002.13"),
    ("UTILITY_BILL", "ELECTRICITY BILL\nAdani Electricity\nConsumer No: AE-MUM-1928374\nBill Date: 01-04-2026\nUnits: 310  Amount: ₹2,108\nDue Date: 16-04-2026"),

    # ---- CREDIT_NOTE (10) ----
    ("CREDIT_NOTE", "CREDIT NOTE\nCredit Note No: CN-2026-089\nDate: 20-04-2026\nAgainst Invoice: GST-570\nReason: Goods returned – damaged\nCredit Amount: ₹5,000\nGST: ₹900"),
    ("CREDIT_NOTE", "CREDIT NOTE\nCN No: CN/26-27/012\nIssued to: Vibhu Automobile\nOriginal Invoice: INV-201\nDiscount Allowed: ₹1,200\nAdjusted GST: ₹216"),
    ("CREDIT_NOTE", "Credit Note\nDate: 18-04-2026\nBuyer: Green Mart\nReason: Price revision\nCredited: ₹3,500  CGST: ₹315  SGST: ₹315"),
    ("CREDIT_NOTE", "CREDIT NOTE\nNo: CRN-44\nVendor: Sharma Traders\nInvoice Date: 01-03-2026\nReturn Qty: 10 units  @ ₹120\nCredit: ₹1,200  GST @12%: ₹144"),
    ("CREDIT_NOTE", "CREDIT NOTE\nDate: 15-04-2026\nReason: Quality rejection\nCN Amount: ₹7,200\nIGST 18%: ₹1,296\nNet Credit: ₹8,496"),
    ("CREDIT_NOTE", "Credit Note No: CRNIT-2026-004\nIssued by: National Auto Parts\nDate: 12-04-2026\nOriginal Invoice: ORD-0123\nCredit for short supply: ₹2,800"),
    ("CREDIT_NOTE", "CREDIT NOTE\nFor: Sales Return\nCN-Number: CN0045\nDate: 10-04-2026\nProduct: LED Bulbs x50\nUnit Price: ₹180  Total: ₹9,000  GST: ₹1,620"),
    ("CREDIT_NOTE", "Credit Note\nDate: 08-04-2026\nCustomer: Apex Retailers\nReason: Discount allowed on bulk order\nCredit Amount: ₹4,500  Adj. CGST: ₹405  Adj. SGST: ₹405"),
    ("CREDIT_NOTE", "CREDIT NOTE\nCNO: 2026-CN-0081\nDate: 05-04-2026\nOriginal Inv: 2026-INV-0450\nReason: Wrong goods dispatched\nRefund: ₹11,250  GST Credit: ₹2,025"),
    ("CREDIT_NOTE", "Credit Note\nDate: 02-04-2026\nFrom: Metro Electronics\nTo: City Computers\nReason: Price Adjustment\nAmount: ₹600  GST: ₹108"),

    # ---- DEBIT_NOTE (10) ----
    ("DEBIT_NOTE", "DEBIT NOTE\nDN No: DN-2026-022\nDate: 22-04-2026\nTo: Kumar Textiles\nReason: Penalty for late delivery\nDebit Amount: ₹2,500"),
    ("DEBIT_NOTE", "DEBIT NOTE\nNo: DN/26-27/007\nDate: 20-04-2026\nSupplier: Apex Polymers\nReason: Short supply – 50kg\nRate: ₹87.5/kg  Debit: ₹4,375  GST: ₹788"),
    ("DEBIT_NOTE", "Debit Note\nDate: 18-04-2026\nFrom: Sunrise Foods\nTo: Vendor\nCharge Back: Damaged goods in transit\nAmount: ₹6,000  IGST 12%: ₹720"),
    ("DEBIT_NOTE", "DEBIT NOTE\nDN: DN-001\nReason: Purchase Return – defective material\nDate: 16-04-2026\nQty: 20  Rate: ₹250  Total: ₹5,000  GST: ₹900"),
    ("DEBIT_NOTE", "DEBIT NOTE\nNo: DNT-2026-044\nDate: 14-04-2026\nReason: Excess quantity billed\nDebit to Supplier: ₹3,200\nCGST @9%: ₹288  SGST @9%: ₹288"),
    ("DEBIT_NOTE", "Debit Note\nDate: 12-04-2026\nIssued by: Modern Pumps\nReason: Installation charges not billed\nAdditional Charge: ₹1,500  GST 18%: ₹270\nTotal Debit: ₹1,770"),
    ("DEBIT_NOTE", "DEBIT NOTE\nDN-0088\nDate: 10-04-2026\nFor: Freight differential\nSupplier: Fast Logistics\nDebit Amount: ₹800  GST: ₹144  Total: ₹944"),
    ("DEBIT_NOTE", "Debit Note\nDate: 08-04-2026\nVendor: Phoenix Stationery\nReason: Quality penalty clause\nPenalty: 5% of ₹10,000 = ₹500"),
    ("DEBIT_NOTE", "DEBIT NOTE\nNo: DEB-2026-019\nDate: 06-04-2026\nSupplier: Classic Tools\nReason: Warranty claim deduction\nDebit: ₹1,200  GST credit: ₹216"),
    ("DEBIT_NOTE", "Debit Note\nDate: 04-04-2026\nFrom: Buyer Corp\nReason: Charge back – wrong specification\nAmount: ₹9,000  IGST 18%: ₹1,620\nTotal Debit: ₹10,620"),
]
# fmt: on


def run_l1_only(text):
    doc_type, conf = classify_l1(text)
    if doc_type and conf >= CLASSIFIER_L1_THRESHOLD:
        return doc_type
    return None  # fell through to L2


def run_full_pipeline(text):
    result = classify_document(text)
    return result["type"], result["classifier_level"], result["confidence"]


def main():
    print("=" * 60)
    print("CLASSIFIER EVALUATION — 60 samples (10 per class)")
    print("=" * 60)

    classes = ["GST_INVOICE", "PURCHASE_BILL", "EXPENSE_RECEIPT", "UTILITY_BILL", "CREDIT_NOTE", "DEBIT_NOTE"]

    # L1-only stats
    l1_correct = {c: 0 for c in classes}
    l1_total = {c: 0 for c in classes}
    l1_fell_through = {c: 0 for c in classes}

    # Full pipeline stats
    full_correct = {c: 0 for c in classes}
    full_total = {c: 0 for c in classes}
    level_counts = {"L1": 0, "L2": 0, "L3": 0}

    from collections import defaultdict
    confusion = defaultdict(int)  # (true, pred) -> count

    print("\n--- Per-sample results ---")
    for true_label, text in TEST_SET:
        l1_total[true_label] += 1
        full_total[true_label] += 1

        l1_pred = run_l1_only(text)
        if l1_pred is None:
            l1_fell_through[true_label] += 1
        elif l1_pred == true_label:
            l1_correct[true_label] += 1

        pred_type, level, conf = run_full_pipeline(text)
        level_counts[level] += 1
        confusion[(true_label, pred_type)] += 1

        correct = pred_type == true_label
        if correct:
            full_correct[true_label] += 1
        status = "OK" if correct else f"WRONG->{pred_type}"
        print(f"  [{true_label[:12]:12s}] L={level} conf={conf} -> {status}")

    total = len(TEST_SET)

    print("\n" + "=" * 60)
    print("L1 REGEX — ACCURACY PER CLASS (docs that L1 handled)")
    print("=" * 60)
    l1_handled_correct = 0
    l1_handled_total = 0
    for c in classes:
        handled = l1_total[c] - l1_fell_through[c]
        acc = l1_correct[c] / handled if handled else 0
        print(f"  {c:20s}: {l1_correct[c]}/{handled} handled, acc={acc:.2%}  (fell-through={l1_fell_through[c]})")
        l1_handled_correct += l1_correct[c]
        l1_handled_total += handled

    l1_coverage = l1_handled_total / total
    l1_prec = l1_handled_correct / l1_handled_total if l1_handled_total else 0
    print(f"\n  L1 coverage (docs handled): {l1_coverage:.2%}")
    print(f"  L1 precision (when it fires): {l1_prec:.2%}")

    print("\n" + "=" * 60)
    print("FULL PIPELINE — ACCURACY PER CLASS")
    print("=" * 60)
    total_correct = 0
    for c in classes:
        acc = full_correct[c] / full_total[c] if full_total[c] else 0
        print(f"  {c:20s}: {full_correct[c]}/{full_total[c]} correct, acc={acc:.2%}")
        total_correct += full_correct[c]

    overall = total_correct / total
    print(f"\n  Overall accuracy: {total_correct}/{total} = {overall:.2%}")
    print(f"  Level breakdown: L1={level_counts['L1']}  L2={level_counts['L2']}  L3={level_counts['L3']}")

    print("\n" + "=" * 60)
    print("CONFUSION MATRIX (true -> predicted)")
    print("=" * 60)
    for c in classes:
        row = [confusion.get((c, p), 0) for p in classes]
        print(f"  {c[:12]:12s} | " + "  ".join(f"{v:2d}" for v in row))
    print("               | " + "  ".join(c[:4] for c in classes))

    # Macro P/R/F1
    from collections import defaultdict
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    for (true, pred), count in confusion.items():
        if true == pred:
            tp[true] += count
        else:
            fp[pred] += count
            fn[true] += count

    print("\n" + "=" * 60)
    print("MACRO P / R / F1")
    print("=" * 60)
    precisions, recalls, f1s = [], [], []
    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0
        f = 2 * p * r / (p + r) if (p + r) else 0
        precisions.append(p); recalls.append(r); f1s.append(f)
        print(f"  {c:20s}: P={p:.2%}  R={r:.2%}  F1={f:.2%}")

    mp = sum(precisions)/len(precisions)
    mr = sum(recalls)/len(recalls)
    mf = sum(f1s)/len(f1s)
    print(f"\n  Macro avg:  P={mp:.2%}  R={mr:.2%}  F1={mf:.2%}")
    print(f"  Overall accuracy: {overall:.2%}")


if __name__ == "__main__":
    main()
