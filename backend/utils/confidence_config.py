"""
Centralized configuration for all confidence-related constants and thresholds.
Used to avoid hardcoding values in the business logic.
"""

# --- OCR Service ---
# Words below this confidence score are flagged in the UI or downstream models
OCR_CONFIDENCE_THRESHOLD = 0.85
# Default confidence for words when the OCR engine doesn't provide one
OCR_DEFAULT_WORD_CONFIDENCE = 1.0


# --- Document Classifier (L1/L2/L3) ---
# If L1 (regex) confidence is >= this, we skip L2 (BERT)
CLASSIFIER_L1_THRESHOLD = 0.80
# If L2 (BERT) confidence is < this, we mark as L3 (Human review needed)
CLASSIFIER_L2_THRESHOLD = 0.60

# L1 Regex Base Confidence Scores
L1_CONF_CREDIT_NOTE = 0.95
L1_CONF_DEBIT_NOTE = 0.95
L1_CONF_GST_INVOICE_KEYWORD = 0.85
L1_CONF_INVOICE_KEYWORD = 0.92
L1_CONF_PURCHASE_BILL = 0.80
L1_CONF_UTILITY_BILL = 0.80
L1_CONF_EXPENSE_RECEIPT = 0.82

# L1 Heuristics
L1_GSTIN_BONUS = 0.10
L1_MAX_CONFIDENCE = 0.99
L1_GSTIN_ONLY_CONFIDENCE = 0.75


# --- Field Extractors ---
# Default confidence for regex-based extraction (fixed because regex is binary)
EXTRACTOR_REGEX_CONFIDENCE = 0.65

# If LayoutLM confidence for a field is below this, we might flag it or fallback
EXTRACTOR_LAYOUTLM_THRESHOLD = 0.50

# Confidence score assigned to fields extracted by the LayoutLLM (GPT-4) engine
LAYOUTLLM_LLM_CONFIDENCE = 0.90


# --- Math & Validation Tolerances ---
# Allowed difference between CGST and SGST (for rounding issues)
VALIDATION_TAX_MATCH_TOLERANCE = 0.01
# Allowed difference when matching calculated tax rates to valid GST slabs
VALIDATION_RATE_MATCH_TOLERANCE = 0.5


# --- Inference & Performance ---
# Max text length to pass to the L2 classifier to keep it fast on CPU
CLASSIFIER_L2_MAX_TEXT_LENGTH = 1500


def format_confidence(conf: float) -> float:
    """Standard formatting for confidence percentage (e.g., 0.8543 -> 85.4)."""
    return round(conf * 100, 1)


def format_ocr_confidence(conf: float) -> float:
    """Standard formatting for raw confidence scores (e.g., 0.854321 -> 0.8543)."""
    return round(conf, 4)


def format_prediction_confidence(conf: float) -> float:
    """Standard formatting for model prediction scores (e.g., 0.8543 -> 0.854)."""
    return round(conf, 3)
