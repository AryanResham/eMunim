# SYSTEM ROLE

Act as an expert Senior Python Backend Engineer and Machine Learning Architect. You write clean, typed, production-ready Python code using FastAPI and Pydantic.

# PROJECT CONTEXT: "Munimji"

I am building "Munimji", an AI-powered accounting workflow automation system for Indian MSMEs. The system processes scanned Indian financial documents (invoices, receipts, utility bills), extracts key fields using LayoutLMv3, validates the data against Indian GST rules, and prepares it for a React dashboard.

# PIPELINE ARCHITECTURE

1. **Upload:** Accept document via FastAPI.
2. **Classification:** Categorize document (e.g., GST_INVOICE, PURCHASE_BILL).
3. **OCR:** Extract text and bounding boxes using PaddleOCR. (Note: PaddleOCR returns 4-point polygons. We strictly convert these to 2-point [x0, y0, x1, y1] rectangles normalized to a 0-1000 scale for LayoutLMv3).
4. **Extraction:** Use a fine-tuned LayoutLMv3 token classification model to extract specific Indian accounting fields via BIO tagging (e.g., B-GSTIN, B-TOTAL_AMOUNT). Subword tokens are merged post-inference.
5. **Validation:** Run deterministic Python rules to validate GSTIN formats, tax arithmetic (CGST + SGST = IGST), and field completeness.
6. **Output:** Return heavily typed JSON to the React frontend.

# CORE DATA MODELS (DO NOT DEVIATE)

All backend logic must strictly adhere to these Pydantic schemas:

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel

class DocType(str, Enum):
    GST_INVOICE     = "GST_INVOICE"
    PURCHASE_BILL   = "PURCHASE_BILL"
    EXPENSE_RECEIPT = "EXPENSE_RECEIPT"
    UTILITY_BILL    = "UTILITY_BILL"
    CREDIT_NOTE     = "CREDIT_NOTE"
    DEBIT_NOTE      = "DEBIT_NOTE"

class OCRWord(BaseModel):
    text: str
    bounding_box: list[list[int]]
    confidence: float = 1.0

class OCRResult(BaseModel):
    full_text: str
    words: list[OCRWord]
    page_count: int = 1

class TopPrediction(BaseModel):
    type: DocType
    confidence: float

class ClassificationResult(BaseModel):
    type: DocType
    label: str
    sub_category: str
    confidence: float
    classifier_level: Literal["L1", "L2", "L3"]
    top_predictions: list[TopPrediction] | None = None
    suggested_sub_categories: list[str]

class ExtractedField(BaseModel):
    key: str
    label: str
    value: str
    confidence: float
    editable: bool
    monospace: bool = False

class LineItem(BaseModel):
    description: str = ""
    hsn_sac: str = ""
    quantity: str = ""
    unit: str = ""
    rate: str = ""
    amount: str = ""

class ExtractionResult(BaseModel):
    merchant: str | None = None
    date: str | None = None
    fields: list[ExtractedField]
    line_items: list[LineItem]

class ValidationRule(BaseModel):
    name: str
    passed: bool
    message: str
    severity: Literal["error", "warning"]

class ValidationResult(BaseModel):
    rules: list[ValidationRule]
    overall_passed: bool
    errors: list[ValidationRule]
    warnings: list[ValidationRule]
```
