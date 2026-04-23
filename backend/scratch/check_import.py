import sys
import os
sys.path.append(os.getcwd())
try:
    from utils.confidence_config import OCR_DEFAULT_WORD_CONFIDENCE
    print(f"Import success: {OCR_DEFAULT_WORD_CONFIDENCE}")
except Exception as e:
    print(f"Import failed: {e}")
