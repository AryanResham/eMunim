from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class DocType(str, Enum):
    GST_INVOICE = "GST_INVOICE"
    PURCHASE_BILL = "PURCHASE_BILL"
    EXPENSE_RECEIPT = "EXPENSE_RECEIPT"
    UTILITY_BILL = "UTILITY_BILL"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"

Pipeline = Literal["ocr_layoutlm", "hosted_vlm", "layoutlm_hosted_fallback"]
ReviewPolicy = Literal["extraction_only", "validation_review", "validation_confidence_review"]

class OCRWord(BaseModel):
    text: str
    bounding_box: list[list[int]] = Field(min_length=4, max_length=4)
    confidence: float = Field(1, ge=0, le=1)

    @field_validator("bounding_box")
    @classmethod
    def valid_vertices(cls, value):
        if any(len(point) != 2 for point in value):
            raise ValueError("Each bounding-box vertex must contain x and y.")
        return value

class OCRResult(BaseModel):
    full_text: str
    words: list[OCRWord]
    page_count: int = 1
    metadata: dict = Field(default_factory=dict)

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
    label: str = ""
    value: str | None = None
    confidence: float | None = Field(None, ge=0, le=100)
    editable: bool = True
    monospace: bool = False
    source: str = "layoutlm"

class LineItem(BaseModel):
    description: str = ""
    hsn_sac: str = ""
    quantity: str = ""
    unit: str = ""
    rate: str = ""
    amount: str = ""

class ValidationRule(BaseModel):
    name: str
    passed: bool | None
    status: str = "passed"
    message: str
    severity: Literal["error", "warning"] = "error"
    fields: list[str] = Field(default_factory=list)

class ValidationResult(BaseModel):
    rules: list[ValidationRule]
    overall_passed: bool
    errors: list[ValidationRule]
    warnings: list[ValidationRule]
    review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    flagged_fields: list[str] = Field(default_factory=list)
    policy: ReviewPolicy = "validation_review"
    rule_version: str = "consistency-v1"
    policy_version: str = "review-v1"
    threshold: float | None = None

class ExtractionResult(BaseModel):
    fields: list[ExtractedField]
    line_items: list[LineItem] = Field(default_factory=list)
    pipeline: Pipeline
    metadata: dict = Field(default_factory=dict)
