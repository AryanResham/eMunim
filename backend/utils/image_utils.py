from PIL import Image, ImageOps
import io

# Vision API works best when the longest side is under 2048px and DPI is 300
TARGET_LONG_SIDE = 2048
TARGET_DPI = 300


def normalize_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))

    # RGB strips alpha channels and handles grayscale — Vision API expects RGB
    img = img.convert("RGB")

    # Boost contrast so faded ink / low-quality scans read more clearly
    img = ImageOps.autocontrast(img)

    # Scale down only if needed — never upscale, that adds blur not detail
    w, h = img.size
    if max(w, h) > TARGET_LONG_SIDE:
        scale = TARGET_LONG_SIDE / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", dpi=(TARGET_DPI, TARGET_DPI), quality=95)
    return out.getvalue()
