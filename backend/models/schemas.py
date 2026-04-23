from enum import Enum
from typing import Literal
from pydantic import BaseModel
from utils.confidence_config import OCR_DEFAULT_WORD_CONFIDENCE


class DocType(str, Enum):
    GST_INVOICE     = "GST_INVOICE"
    PURCHASE_BILL   = "PURCHASE_BILL"
    EXPENSE_RECEIPT = "EXPENSE_RECEIPT"
    UTILITY_BILL    = "UTILITY_BILL"
    CREDIT_NOTE     = "CREDIT_NOTE"
    DEBIT_NOTE      = "DEBIT_NOTE"


class OCRWord(BaseModel):
    text: str
    bounding_box: list[list[int]]  # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    confidence: float = OCR_DEFAULT_WORD_CONFIDENCE


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
    date: str
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
