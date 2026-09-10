import io
import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.sarvam_service import SarvamDocAIService, AADHAAR_EXTRACTION_SCHEMA
from app.services.aadhaar_service import (
    validate_verhoeff,
    generate_verhoeff,
    format_aadhaar_number,
    AadhaarValidationService,
)

client = TestClient(app)


def test_verhoeff_algorithm_direct():
    """Unit tests for Verhoeff check digit generation and validation."""
    # Test generation and validation with known test vectors
    assert generate_verhoeff("99994105703") == "6"
    assert validate_verhoeff("999941057036") is True

    # Wikipedia standard example: 236 -> check digit 3 -> 2363
    assert generate_verhoeff("236") == "3"
    assert validate_verhoeff("2363") is True

    # Altered check digit should fail
    assert validate_verhoeff("999941057035") is False
    assert validate_verhoeff("999941057030") is False

    # Transposition error (swapping adjacent digits 05 -> 50) should fail
    assert validate_verhoeff("999941507036") is False

    # Non-digits and empty string
    assert validate_verhoeff("") is False
    assert validate_verhoeff("ABC") is False


def test_aadhaar_service_validate_number():
    """Tests AadhaarValidationService validation logic, cleaning, and formatting."""
    # Valid Aadhaar with spaces
    res = AadhaarValidationService.validate_aadhaar_number("9999 4105 7036")
    assert res.is_12_digits is True
    assert res.checksum_valid is True
    assert res.is_valid is True
    assert res.clean_number == "999941057036"
    assert res.formatted_number == "9999 4105 7036"

    # Valid Aadhaar with dashes
    res_dash = AadhaarValidationService.validate_aadhaar_number("9999-4105-7036")
    assert res_dash.checksum_valid is True
    assert res_dash.formatted_number == "9999 4105 7036"

    # Invalid check digit
    res_invalid = AadhaarValidationService.validate_aadhaar_number("999941057035")
    assert res_invalid.is_12_digits is True
    assert res_invalid.checksum_valid is False
    assert res_invalid.is_valid is False

    # Incorrect length
    res_short = AadhaarValidationService.validate_aadhaar_number("12345")
    assert res_short.is_12_digits is False
    assert res_short.checksum_valid is False
    assert res_short.is_valid is False

    # Empty / None
    res_none = AadhaarValidationService.validate_aadhaar_number(None)
    assert res_none.is_valid is False
    assert res_none.clean_number is None


def test_aadhaar_validation_unsupported_file_extension():
    """Verify that unsupported media formats are rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/aadhaar-validation",
        files={"file": ("malicious.sh", b"#!/bin/bash", "application/x-sh")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["detail"]


@patch.object(SarvamDocAIService, "extract_aadhaar_data", new_callable=AsyncMock)
def test_aadhaar_validation_blank_image(mock_extract):
    """Verify that an image without Aadhaar data returns success=True with aadhaar_detected=False."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/aadhaar-validation",
        files={"file": ("blank_scan.jpg", dummy_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["aadhaar_detected"] is False
    assert data["filename"] == "blank_scan.jpg"
    assert data["data"] is None


@patch.object(SarvamDocAIService, "extract_aadhaar_data", new_callable=AsyncMock)
def test_aadhaar_validation_blank_pdf(mock_extract):
    """Verify that a blank PDF document returns aadhaar_detected=False and data=None."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    pdf_dummy_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF"

    response = client.post(
        "/api/v1/aadhaar-validation",
        files={"file": ("blank_document.pdf", pdf_dummy_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["aadhaar_detected"] is False
    assert data["filename"] == "blank_document.pdf"
    assert data["data"] is None


@patch.object(SarvamDocAIService, "extract_aadhaar_data", new_callable=AsyncMock)
def test_aadhaar_validation_valid_document(mock_extract):
    """Verify end-to-end Aadhaar extraction and Verhoeff verification."""
    mock_extract.return_value = {
        "fields": {
            "aadhaar_no": "9999 4105 7036",
            "first_name": "RAMESH",
            "last_name": "KUMAR",
            "dob": "1990-08-25",
            "sex": "MALE",
        },
        "valid_score": 97,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/aadhaar-validation",
        files={"file": ("aadhaar_sample.jpg", dummy_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["aadhaar_detected"] is True
    assert "successfully extracted" in res_data["message"]

    data = res_data["data"]
    assert data["name"] == "RAMESH KUMAR"
    assert data["first_name"] == "RAMESH"
    assert data["last_name"] == "KUMAR"
    assert data["dob"] == "1990-08-25"
    assert data["sex"] == "MALE"
    assert data["aadhaar_no"] == "999941057036"
    assert data["formatted_aadhaar_no"] == "9999 4105 7036"
    assert data["checksum_valid"] is True
    assert data["aadhaar_valid"] is True
    assert data["valid_score"] == 97
    assert data["extraction_method"] == "sarvam-vision-v1"


@patch.object(SarvamDocAIService, "extract_aadhaar_data", new_callable=AsyncMock)
def test_aadhaar_validation_invalid_checksum(mock_extract):
    """Verify detection and warning when Verhoeff checksum fails."""
    # 999941057035 has invalid check digit (correct is 6)
    mock_extract.return_value = {
        "fields": {
            "aadhaar_no": "9999 4105 7035",
            "first_name": "SITA",
            "last_name": "SHARMA",
            "dob": "1992-01-01",
            "sex": "FEMALE",
        },
        "valid_score": 90,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/aadhaar-validation",
        files={"file": ("aadhaar_bad_checksum.jpg", dummy_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["aadhaar_detected"] is True
    assert "failed Verhoeff checksum" in res_data["message"]

    data = res_data["data"]
    assert data["checksum_valid"] is False
    assert data["aadhaar_valid"] is False


@pytest.mark.anyio
async def test_aadhaar_sarvam_service_workflow():
    """Verify SarvamDocAIService.extract_aadhaar_data uses AADHAAR_EXTRACTION_SCHEMA."""
    service = SarvamDocAIService(api_key="mock_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Mock submission
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = {"job_id": "aadhaar_job_789", "status": "pending"}
        mock_post.return_value = mock_post_resp

        # Mock status poll and results
        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {"status": "completed"}

        mock_results_resp = MagicMock()
        mock_results_resp.status_code = 200
        mock_results_resp.json.return_value = {
            "type": "extract",
            "annotations": {
                "aadhaar_no": {"value": "9999 4105 7036", "confidence": 0.99},
                "first_name": {"value": "RAMESH", "confidence": 0.98},
                "last_name": {"value": "KUMAR", "confidence": 0.97},
            },
        }

        mock_get.side_effect = [mock_status_resp, mock_results_resp]

        res = await service.extract_aadhaar_data(
            file_bytes=b"dummy_aadhaar_bytes",
            filename="aadhaar.pdf",
            content_type="application/pdf",
        )

        assert res["fields"]["aadhaar_no"] == "9999 4105 7036"
        assert res["fields"]["first_name"] == "RAMESH"
        assert res["fields"]["last_name"] == "KUMAR"
        assert res["valid_score"] >= 95

        # Verify AADHAAR_EXTRACTION_SCHEMA was sent
        call_args = mock_post.call_args
        sent_data = call_args.kwargs["data"]
        schema_dict = json.loads(sent_data["schema"])
        assert "aadhaar_no" in schema_dict["properties"]
        assert "dob" in schema_dict["properties"]
        assert "first_name" in schema_dict["properties"]
        assert "last_name" in schema_dict["properties"]
        assert "sex" in schema_dict["properties"]

        # Ensure all descriptions are non-empty strings (critical Sarvam requirement)
        for field, props in schema_dict["properties"].items():
            assert "description" in props
            assert len(props["description"].strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__])
