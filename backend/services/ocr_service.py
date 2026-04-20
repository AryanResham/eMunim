# ============================================================
# ARYAN — ocr_service.py
# ============================================================
#
# PURPOSE:
#   Send document images to Google Cloud Vision and return structured OCR results.
#
# FUNCTION TO IMPLEMENT:
#
#   async def run_vision_ocr(image_bytes: bytes) -> OCRResult:
#       - POST to Cloud Vision REST API:
#           https://vision.googleapis.com/v1/images:annotate?key={API_KEY}
#       - Feature type: TEXT_DETECTION
#       - Request body:
#           { "requests": [{ "image": { "content": base64(image_bytes) },
#                            "features": [{ "type": "TEXT_DETECTION" }] }] }
#       - Parse response:
#           textAnnotations[0].description  → full_text
#           textAnnotations[1..N]           → individual words with boundingPoly.vertices
#       - Each vertex is {"x": int, "y": int} — map to [[x,y],[x,y],[x,y],[x,y]]
#       - Return OCRResult(full_text=..., words=[OCRWord(...)], page_count=1)
#       - Use httpx.AsyncClient for the HTTP call
#
#   async def ocr_document(image_bytes: bytes) -> OCRResult:
#       - Call run_vision_ocr
#       - If GOOGLE_CLOUD_VISION_API_KEY is empty or request fails,
#         raise HTTPException(503, "OCR service unavailable — set GOOGLE_CLOUD_VISION_API_KEY")
#       - This function is the only one called by the router
#
# IMPORTS YOU WILL NEED:
#   import base64
#   import httpx
#   from config import settings
#   from models.schemas import OCRResult, OCRWord
