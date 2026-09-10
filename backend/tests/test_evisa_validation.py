import io
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.sarvam_service import SarvamDocAIService, EVISA_EXTRACTION_SCHEMA

client = TestClient(app)


def test_evisa_validation_unsupported_file_extension():
    """Verify that unsupported media formats are rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/evisa-validation",
        files={"file": ("malicious.exe", b"binary content", "application/x-msdownload")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["detail"]


@patch.object(SarvamDocAIService, "extract_evisa_data", new_callable=AsyncMock)
def test_evisa_validation_blank_image(mock_extract):
    """Verify that an image without e-visa data returns success=True with visa_detected=False."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/evisa-validation",
        files={"file": ("blank_scan.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["visa_detected"] is False
    assert data["filename"] == "blank_scan.jpg"
    assert data["data"] is None


@patch.object(SarvamDocAIService, "extract_evisa_data", new_callable=AsyncMock)
def test_evisa_validation_blank_pdf(mock_extract):
    """Verify that a blank PDF document returns visa_detected=False and data=None."""
    mock_extract.return_value = {
        "fields": {},
        "valid_score": 0,
        "raw_response": {"type": "extract", "annotations": {}},
    }

    pdf_dummy_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF"

    response = client.post(
        "/api/v1/evisa-validation",
        files={"file": ("blank_document.pdf", pdf_dummy_bytes, "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["visa_detected"] is False
    assert data["filename"] == "blank_document.pdf"
    assert data["data"] is None


@patch.object(SarvamDocAIService, "extract_evisa_data", new_callable=AsyncMock)
def test_evisa_validation_valid_document(mock_extract):
    """Verify end-to-end e-visa extraction and structured field parsing."""
    mock_extract.return_value = {
        "fields": {
            "first_name": "SARAH",
            "last_name": "CONNOR",
            "dob": "1985-05-15",
            "place_of_birth": "LOS ANGELES",
            "sex": "F",
            "nationality": "USA",
            "passport_number": "P12345678",
            "passport_issuing_country": "USA",
            "passport_issue_date": "2020-01-10",
            "passport_expiration_date": "2030-01-09",
            "visa_number": "IN-EV-2024-987654",
            "visa_type": "e-Tourist Visa (30 Days)",
            "stay_duration": "30 Days",
            "entry_validation": "From 2024-06-01 to 2024-06-30",
        },
        "valid_score": 98,
        "raw_response": {},
    }

    dummy_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"

    response = client.post(
        "/api/v1/evisa-validation",
        files={"file": ("evisa_sample.jpg", dummy_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["visa_detected"] is True
    assert "successfully extracted" in res_data["message"]

    data = res_data["data"]
    assert data["name"] == "SARAH CONNOR"
    assert data["first_name"] == "SARAH"
    assert data["last_name"] == "CONNOR"
    assert data["dob"] == "1985-05-15"
    assert data["place_of_birth"] == "LOS ANGELES"
    assert data["sex"] == "F"
    assert data["nationality"] == "USA"
    assert data["passport_number"] == "P12345678"
    assert data["passport_issuing_country"] == "USA"
    assert data["passport_issue_date"] == "2020-01-10"
    assert data["passport_expiration_date"] == "2030-01-09"
    assert data["visa_number"] == "IN-EV-2024-987654"
    assert data["visa_type"] == "e-Tourist Visa (30 Days)"
    assert data["stay_duration"] == "30 Days"
    assert data["entry_validation"] == "From 2024-06-01 to 2024-06-30"
    assert data["visa_valid"] is True
    assert data["valid_score"] == 98
    assert data["extraction_method"] == "sarvam-vision-v1"


@pytest.mark.anyio
async def test_evisa_sarvam_service_workflow():
    """Verify SarvamDocAIService.extract_evisa_data uses EVISA_EXTRACTION_SCHEMA."""
    service = SarvamDocAIService(api_key="mock_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Mock submission
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = {"job_id": "evisa_job_456", "status": "pending"}
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
                "visa_number": {"value": "V123456", "confidence": 0.99},
                "passport_number": {"value": "X789012", "confidence": 0.98},
                "visa_type": {"value": "e-Business Visa", "confidence": 0.97},
            }
        }

        mock_get.side_effect = [mock_status_resp, mock_results_resp]

        res = await service.extract_evisa_data(
            file_bytes=b"dummy_evisa_bytes",
            filename="evisa.pdf",
            content_type="application/pdf",
        )

        assert res["fields"]["visa_number"] == "V123456"
        assert res["fields"]["passport_number"] == "X789012"
        assert res["fields"]["visa_type"] == "e-Business Visa"
        assert res["valid_score"] >= 95

        # Verify EVISA_EXTRACTION_SCHEMA was sent
        call_args = mock_post.call_args
        sent_data = call_args.kwargs["data"]
        import json
        schema_dict = json.loads(sent_data["schema"])
        assert "visa_number" in schema_dict["properties"]
        assert "stay_duration" in schema_dict["properties"]
        assert "entry_validation" in schema_dict["properties"]


if __name__ == "__main__":
    pytest.main([__file__])
