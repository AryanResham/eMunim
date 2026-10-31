"""Load local inference models once before accepting requests."""
import logging

status = {"classifier": "not loaded", "extractors": {}}


def preload_models():
    from services.extractor import layoutlm_extractor as local
    from services.extractor.field_mapper import DOC_TYPE_TO_MODEL
    for doc_type in DOC_TYPE_TO_MODEL:
        try:
            loaded = local._get_model_for_doc_type(doc_type)
            status["extractors"][doc_type] = "ready" if loaded else "missing or unloadable"
        except Exception:
            logging.exception("Unable to preload %s", doc_type)
            status["extractors"][doc_type] = "failed to load"
    try:
        from services.classifier.l2_finbert import _get_pipeline
        _get_pipeline()
        status["classifier"] = "ready"
    except Exception:
        logging.exception("Classifier unavailable; rule classification and manual selection remain available")
        status["classifier"] = "unavailable"
    return status
