"""
Step 2 starter: MRZ-first OCR extraction.

Install:
    pip install opencv-python pytesseract passporteye numpy

Also install the tesseract-ocr binary itself (PassportEye and pytesseract both
call out to it):
    Ubuntu/Debian:  sudo apt install tesseract-ocr
    macOS:          brew install tesseract
    Windows:         https://github.com/UB-Mannheim/tesseract/wiki

Get a test image: use your own ID for local testing, or grab a sample from the
MIDV-2020 dataset (search "MIDV-2020 dataset" — synthetic, non-real documents,
safe to use for testing).

Run:
    python ocr_extract.py path/to/document.jpg
"""

import sys
import cv2
import numpy as np
from passporteye import read_mrz


def extract_mrz(image_path):
    """
    The fast path. PassportEye already does OpenCV-based MRZ region
    localization + Tesseract OCR + ICAO 9303 checksum validation internally —
    this is one function call instead of building the pipeline yourself.
    """
    mrz = read_mrz(image_path)
    if mrz is None:
        return None

    data = mrz.to_dict()
    return {
        "name": f"{data.get('names', '')} {data.get('surname', '')}".strip(),
        "document_number": data.get("number"),
        "nationality": data.get("nationality"),
        "date_of_birth": data.get("date_of_birth"),
        "expiry_date": data.get("expiration_date"),
        "sex": data.get("sex"),
        "mrz_valid": data.get("valid_score", 0) > 80,  # checksum-based confidence
    }


def locate_mrz_manually(image_path):
    """
    The fallback path. Classic OpenCV technique for finding the MRZ block
    yourself — useful when PassportEye can't find a clean MRZ on a noisy or
    skewed photo, so you can crop just that region and retry OCR on it.

    How it works: MRZ text is dense, horizontal, and monospaced, which makes
    it show up as a strong horizontal-gradient blob near the bottom of the
    document once you run a blackhat + Sobel + morphological-close sequence.
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Highlight small dark text against a lighter background
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

    # Emphasize horizontal edges (MRZ lines are long horizontal text runs)
    grad_x = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
    grad_x = np.absolute(grad_x)
    min_val, max_val = np.min(grad_x), np.max(grad_x)
    grad_x = (255 * ((grad_x - min_val) / (max_val - min_val + 1e-6))).astype("uint8")

    grad_x = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, rect_kernel)
    thresh = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    sq_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sq_kernel)
    thresh = cv2.erode(thresh, None, iterations=4)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_img, w_img = gray.shape

    mrz_candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        aspect_ratio = w / float(h)
        coverage = w / float(w_img)
        # MRZ lines are wide, short, and sit in the bottom third of the document
        if aspect_ratio > 5 and coverage > 0.5 and y > h_img * 0.6:
            mrz_candidates.append((x, y, w, h))

    if not mrz_candidates:
        return None

    # Merge all candidate boxes into one region covering both MRZ lines
    x1 = min(c[0] for c in mrz_candidates)
    y1 = min(c[1] for c in mrz_candidates)
    x2 = max(c[0] + c[2] for c in mrz_candidates)
    y2 = max(c[1] + c[3] for c in mrz_candidates)

    pad = 10
    mrz_crop = img[max(0, y1 - pad): y2 + pad, max(0, x1 - pad): x2 + pad]
    out_path = "mrz_region.jpg"
    cv2.imwrite(out_path, mrz_crop)
    return out_path


if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else "sample_document.jpg"

    print(f"Trying PassportEye on {image_path}...")
    result = extract_mrz(image_path)

    if result is None:
        print("No clean MRZ found. Falling back to manual OpenCV localization...")
        cropped = locate_mrz_manually(image_path)
        if cropped:
            print(f"Found a candidate MRZ region -> {cropped}. Retrying OCR on the crop...")
            result = extract_mrz(cropped)

    print(result if result else "Still no MRZ detected — try a clearer/straighter photo.")
