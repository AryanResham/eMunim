from __future__ import annotations

# Candidate labels in natural language — zero-shot model maps these to DocType values.
# Using cross-encoder/nli-deberta-v3-small (~200MB) as the default because it is fast
# on CPU. Swap to facebook/bart-large-mnli for better accuracy if GPU is available.
_MODEL_NAME = "cross-encoder/nli-deberta-v3-small"

_CANDIDATE_LABELS = [
    "GST tax invoice from supplier",
    "purchase order or vendor bill",
    "expense or petty cash receipt",
    "electricity water or utility bill",
    "credit note for return or discount",
    "debit note for charge back or penalty",
]

_LABEL_TO_DOCTYPE: dict[str, str] = {
    "GST tax invoice from supplier":          "GST_INVOICE",
    "purchase order or vendor bill":           "PURCHASE_BILL",
    "expense or petty cash receipt":           "EXPENSE_RECEIPT",
    "electricity water or utility bill":       "UTILITY_BILL",
    "credit note for return or discount":      "CREDIT_NOTE",
    "debit note for charge back or penalty":   "DEBIT_NOTE",
}

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline(
            "zero-shot-classification",
            model=_MODEL_NAME,
            device=-1,  # CPU; change to 0 for GPU
        )
    return _pipeline


def classify_l2(text: str) -> tuple[str, float, list[dict]]:
    """
    Returns (top_doc_type, confidence_0_to_1, all_predictions_sorted).
    all_predictions is a list of {"type": DocType, "confidence": float}.
    Text is truncated to 1500 chars to keep inference fast.
    """
    clf = _get_pipeline()
    result = clf(text[:1500], _CANDIDATE_LABELS, multi_label=False)

    predictions = [
        {"type": _LABEL_TO_DOCTYPE[label], "confidence": round(score, 3)}
        for label, score in zip(result["labels"], result["scores"])
    ]

    top_type = _LABEL_TO_DOCTYPE[result["labels"][0]]
    top_conf = result["scores"][0]

    return top_type, top_conf, predictions
