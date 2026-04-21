"""Phase 1 scratch script — verify Google Cloud Vision API key and OCR output."""
import base64
import sys
import os
import httpx

# Add backend directory to path so config can be imported securely
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings
VISION_URL = (
    "https://vision.googleapis.com/v1/images:annotate"
    f"?key={settings.GOOGLE_CLOUD_VISION_API_KEY}"
)


def run_vision_ocr(image_path: str) -> None:
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "requests": [
            {
                "image": {"content": image_b64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }

    response = httpx.post(VISION_URL, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Dump the raw JSON to a file so we can analyze the structure!
    import json
    with open("./response.txt", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("SUCCESS: Raw JSON response written to response.txt")

    pages = data["responses"][0].get("fullTextAnnotation", {}).get("pages", [])
    if not pages:
        print("No text detected.")
        return

    # Write the carefully parsed plain text and bounding boxes directly to the file
    import os
    out_path = os.path.join(os.path.dirname(__file__), "response.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("Parsed OCR Results:\n" + "="*50 + "\n")
        
        for page in pages:
            for block in page["blocks"]:
                for para in block["paragraphs"]:
                    for word in para["words"]:
                        text = "".join(s["text"] for s in word["symbols"])
                        box = word["boundingBox"]["vertices"]
                        
                        # Create the nicely formatted line
                        line = f"{text:30s} {box}\n"
                        
                        # Print to console AND write to the file
                        print(line, end="")
                        f.write(line)
                        
    print("\nSUCCESS: The clean parsed output above was securely saved to response.txt!")


if __name__ == "__main__":
    run_vision_ocr("C:\\Users\\Aryan\\Downloads\\img.tif")
