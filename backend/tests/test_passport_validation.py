import io
import pytest
import numpy as np
import cv2
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_passport_validation_unsupported_file_extension():
    """Verify that unsupported media formats are rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("malicious.exe", b"binary content", "application/x-msdownload")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["detail"]


def test_passport_validation_blank_image():
    """Verify that an image without an MRZ returns success=True with mrz_detected=False."""
    blank_img = np.zeros((400, 600, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", blank_img)

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("blank_scan.jpg", encoded.tobytes(), "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mrz_detected"] is False
    assert data["filename"] == "blank_scan.jpg"
    assert data["data"] is None


def test_passport_validation_blank_pdf():
    """Verify that a PDF document is accepted and processed cleanly."""
    from PIL import Image

    # Create a blank image and save as PDF
    pil_img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    pdf_bytes_io = io.BytesIO()
    pil_img.save(pdf_bytes_io, format="PDF")

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("blank_document.pdf", pdf_bytes_io.getvalue(), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mrz_detected"] is False
    assert data["filename"] == "blank_document.pdf"


def test_passport_validation_valid_mrz():
    """Verify end-to-end MRZ OCR extraction and checksum calculation."""
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaMono-Bold.ttf", 30)
    img = Image.new("RGB", (1000, 700), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    mrz_line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    mrz_line2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    draw.text((60, 560), mrz_line1, fill=(0, 0, 0), font=font)
    draw.text((60, 610), mrz_line2, fill=(0, 0, 0), font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("passport_sample.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["mrz_detected"] is True
    assert res_data["data"]["document_number"] == "L898902C3"
    assert res_data["data"]["valid_score"] >= 80
    assert res_data["data"]["mrz_valid"] is True

    # Verify that trailing/filler '<' characters are cleaned from all fields
    for field_name in ["name", "document_number", "nationality", "country", "mrz_type", "sex"]:
        val = res_data["data"].get(field_name)
        if val:
            assert "<" not in val, f"Field '{field_name}' still contains '<': {val}"


def test_clean_mrz_field_logic():
    """Directly test PassportController._clean_field edge cases."""
    from app.controllers.passport_controller import PassportController

    # Standard fields with trailing chevrons
    assert PassportController._clean_field("L898902C3<") == "L898902C3"
    assert PassportController._clean_field("P<") == "P"
    assert PassportController._clean_field("D<<") == "D"
    assert PassportController._clean_field("ZE184226B<<<<<") == "ZE184226B"
    assert PassportController._clean_field("<<<") is None
    assert PassportController._clean_field("<") is None
    assert PassportController._clean_field(None) is None

    # Name fields with interior and trailing chevrons
    assert PassportController._clean_field("ANNA<MARIA<<<<", is_name=True) == "ANNA MARIA"
    assert PassportController._clean_field("ERIKSSON<<<<", is_name=True) == "ERIKSSON"
    assert PassportController._clean_field("MUSTERFRAU<<ISOLDE<<<<", is_name=True) == "MUSTERFRAU ISOLDE"


if __name__ == "__main__":
    pytest.main([__file__])

