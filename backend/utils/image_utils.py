# ============================================================
# ARYAN — image_utils.py
# ============================================================
#
# PURPOSE:
#   Convert uploaded documents (PDF or image) into image bytes
#   that can be sent to Google Cloud Vision or PaddleOCR.
#
# FUNCTIONS TO IMPLEMENT:
#
#   def pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
#       - Use pdf2image.convert_from_bytes() to convert each PDF page to a PIL image
#       - Convert each PIL image to JPEG bytes and return as list
#       - Windows: pdf2image needs poppler — install via:
#           conda install -c conda-forge poppler
#         OR set poppler_path= in convert_from_bytes()
#       - Multi-page PDFs return one bytes entry per page
#
#   def normalize_image(image_bytes: bytes) -> bytes:
#       - Open with PIL, convert to RGB
#       - Resize so longest side is max 2048px (Cloud Vision works best under 4MB)
#       - Save as JPEG and return bytes
#
# IMPORTS YOU WILL NEED:
#   from pdf2image import convert_from_bytes
#   from PIL import Image
#   import io
