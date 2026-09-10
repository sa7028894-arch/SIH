import io
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.controllers.passport_controller import PassportController
from app.services.sarvam_service import SarvamDocAIService
from app.services.mrz_service import MRZValidationService

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


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_blank_image(mock_extract):
    """Verify that an image without passport data returns success=True with mrz_detected=False."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("blank_scan.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mrz_detected"] is False
    assert data["filename"] == "blank_scan.jpg"
    assert data["data"] is None


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_blank_pdf(mock_extract):
    """Verify that a blank PDF document returns mrz_detected=False and data=None."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    pdf_dummy_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("blank_document.pdf", pdf_dummy_bytes, "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mrz_detected"] is False
    assert data["filename"] == "blank_document.pdf"


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_valid_passport(mock_extract):
    """Verify valid passport extraction with full ICAO 9303 MRZ checksum validation."""
    mock_extract.return_value = {
        "fields": {
            "first_name": "ANNA MARIA",
            "last_name": "ERIKSSON",
            "passport_number": "L898902C3",
            "nationality": "UTO",
            "country_code": "UTO",
            "dob": "740812",
            "date_of_expiry": "120415",
            "date_of_issue": "020415",
            "place_of_issue": "UTOPIA",
            "sex": "F",
            "type_of_passport": "P",
            "mrz": "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10",
        },
        "valid_score": 96,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("passport_sample.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["mrz_detected"] is True
    assert "successfully detected and validated" in res_data["message"]

    data = res_data["data"]
    assert data["name"] == "ANNA MARIA ERIKSSON"
    assert data["first_name"] == "ANNA MARIA"
    assert data["last_name"] == "ERIKSSON"
    assert data["document_number"] == "L898902C3"
    assert data["passport_number"] == "L898902C3"
    assert data["nationality"] == "UTO"
    assert data["country"] == "UTO"
    assert data["mrz_type"] == "TD3"
    assert data["date_of_issue"] == "020415"
    assert data["place_of_issue"] == "UTOPIA"
    assert data["valid_score"] == 100
    assert data["mrz_valid"] is True

    # Verify all check digits are validated as True
    assert data["check_digits"]["number"] is True
    assert data["check_digits"]["date_of_birth"] is True
    assert data["check_digits"]["expiration_date"] is True
    assert data["check_digits"]["composite"] is True
    assert data["check_digits"]["personal_number"] is True


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_invalid_checksum(mock_extract):
    """Verify that an altered check digit results in mrz_valid=False and reflects failed check digits."""
    # Alter document number check digit from 6 to 9 in line 2
    mock_extract.return_value = {
        "fields": {
            "first_name": "ANNA MARIA",
            "last_name": "ERIKSSON",
            "passport_number": "L898902C3",
            "nationality": "UTO",
            "country_code": "UTO",
            "dob": "740812",
            "date_of_expiry": "120415",
            "sex": "F",
            "type_of_passport": "P",
            "mrz": "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C39UTO7408122F1204159ZE184226B<<<<<10",
        },
        "valid_score": 90,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("tampered_passport.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["mrz_detected"] is True
    assert "checksum warnings" in res_data["message"]

    data = res_data["data"]
    assert data["mrz_valid"] is False
    assert data["check_digits"]["number"] is False
    assert data["check_digits"]["composite"] is False
    assert data["check_digits"]["date_of_birth"] is True
    assert data["check_digits"]["expiration_date"] is True
    assert data["valid_score"] < 100


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_td1_card(mock_extract):
    """Verify that 3-line TD1 ID cards are recognized and validated."""
    td1_mrz = (
        "I<SWE59000002<8198703142391<<<\n"
        "8703145M1701027SWE<<<<<<<<<<<8\n"
        "SPECIMEN<<SVEN<<<<<<<<<<<<<<<<"
    )
    mock_extract.return_value = {
        "fields": {
            "first_name": "SVEN",
            "last_name": "SPECIMEN",
            "passport_number": "59000002",
            "nationality": "SWE",
            "country_code": "SWE",
            "dob": "870314",
            "date_of_expiry": "170102",
            "sex": "M",
            "type_of_passport": "I",
            "mrz": td1_mrz,
        },
        "valid_score": 95,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("id_card.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    data = res_data["data"]
    assert data["mrz_valid"] is True
    assert data["mrz_type"] == "TD1"
    assert data["check_digits"]["number"] is True
    assert data["check_digits"]["date_of_birth"] is True
    assert data["check_digits"]["expiration_date"] is True
    assert data["check_digits"]["composite"] is True


@patch.object(SarvamDocAIService, "extract_passport_data", new_callable=AsyncMock)
def test_passport_validation_no_mrz_visual_only(mock_extract):
    """Verify handling when visual fields are extracted but MRZ zone is absent."""
    mock_extract.return_value = {
        "fields": {
            "first_name": "JOHN",
            "last_name": "DOE",
            "passport_number": "A12345678",
            "nationality": "USA",
            "country_code": "USA",
            "dob": "900101",
            "date_of_expiry": "300101",
            "mrz": None,
        },
        "valid_score": 88,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/passport-validation",
        files={"file": ("visual_only.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["mrz_detected"] is False
    assert "no MRZ zone detected" in res_data["message"]
    data = res_data["data"]
    assert data["name"] == "JOHN DOE"
    assert data["check_digits"]["number"] is None


def test_mrz_service_edge_cases():
    """Verify MRZValidationService handling of irregular inputs and malformed strings."""
    # None or empty
    r_none = MRZValidationService.validate_mrz(None)
    assert r_none.is_valid is False
    assert r_none.valid_score == 0
    assert r_none.check_digits.number is None

    # Garbage text
    r_garbage = MRZValidationService.validate_mrz("NOT AN MRZ STRING")
    assert r_garbage.is_valid is False
    assert r_garbage.valid_score == 0
    assert r_garbage.check_digits.number is False
    assert len(r_garbage.errors) > 0

    # Continuous 88 characters without newline
    mrz_continuous = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    r_cont = MRZValidationService.validate_mrz(mrz_continuous)
    assert r_cont.is_valid is True
    assert r_cont.valid_score == 100
    assert r_cont.mrz_type == "TD3"


def test_clean_mrz_field_logic():
    """Directly test PassportController._clean_field edge cases."""
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


def test_sarvam_normalization():
    """Verify that _normalize_extracted_fields processes various annotation structures."""
    service = SarvamDocAIService(api_key="test_key")

    # Dict annotations with confidence
    raw_response = {
        "type": "extract",
        "annotations": {
            "first_name": {"value": "John", "confidence": 0.98},
            "last_name": {"value": "Doe", "confidence": 0.96},
            "passport_number": {"value": "Z1234567", "confidence": 0.99},
        }
    }
    normalized = service._normalize_extracted_fields(raw_response)
    assert normalized["fields"]["first_name"] == "John"
    assert normalized["fields"]["last_name"] == "Doe"
    assert normalized["fields"]["passport_number"] == "Z1234567"
    assert normalized["valid_score"] >= 95

    # Direct primitive string annotations
    raw_primitives = {
        "annotations": {
            "first_name": "Jane",
            "last_name": "Smith",
        }
    }
    normalized_prim = service._normalize_extracted_fields(raw_primitives)
    assert normalized_prim["fields"]["first_name"] == "Jane"
    assert normalized_prim["fields"]["last_name"] == "Smith"
    assert normalized_prim["valid_score"] == 100


@pytest.mark.anyio
async def test_sarvam_service_end_to_end_mock():
    """Verify SarvamDocAIService submit, poll, and result retrieval flow."""
    service = SarvamDocAIService(api_key="mock_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Mock submission
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = {"job_id": "job_12345", "status": "pending"}
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
                "first_name": {"value": "RAVI", "confidence": 0.99},
                "last_name": {"value": "KUMAR", "confidence": 0.99},
                "passport_number": {"value": "P9876543", "confidence": 0.98},
            }
        }

        # First call is status, second is results
        mock_get.side_effect = [mock_status_resp, mock_results_resp]

        res = await service.extract_passport_data(
            file_bytes=b"dummy",
            filename="passport.pdf",
            content_type="application/pdf",
        )

        assert res["fields"]["first_name"] == "RAVI"
        assert res["fields"]["last_name"] == "KUMAR"
        assert res["fields"]["passport_number"] == "P9876543"
        assert res["valid_score"] >= 98


if __name__ == "__main__":
    pytest.main([__file__])
