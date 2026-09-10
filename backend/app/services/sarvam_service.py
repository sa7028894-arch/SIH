import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional, Tuple
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

PASSPORT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "country_code": {"description": "Country code or issuing authority code", "type": "string"},
        "date_of_expiry": {"description": "Date of passport expiration or expiry", "type": "string"},
        "date_of_issue": {"description": "Date of passport issuance or issue", "type": "string"},
        "dob": {"description": "Date of birth of the passport holder", "type": "string"},
        "first_name": {"description": "First name or given names of the person", "type": "string"},
        "last_name": {"description": "Last name or surname of the person", "type": "string"},
        "mrz": {"description": "Machine Readable Zone (MRZ) lines text", "type": "string"},
        "nationality": {"description": "Nationality of the passport holder", "type": "string"},
        "passport_number": {"description": "Passport number or document number", "type": "string"},
        "place_of_issue": {"description": "Place or authority where passport was issued", "type": "string"},
        "sex": {"description": "Sex or gender of the passport holder", "type": "string"},
        "type_of_passport": {"description": "Type of passport document", "type": "string"},
    },
}

EVISA_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "dob": {"description": "Date of birth of the visa holder", "type": "string"},
        "entry_validation": {"description": "Entry validation, validity period or expiry date of the visa", "type": "string"},
        "first_name": {"description": "First name or given names of the visa holder", "type": "string"},
        "last_name": {"description": "Last name or surname of the visa holder", "type": "string"},
        "nationality": {"description": "Nationality of the visa holder", "type": "string"},
        "passport_expiration_date": {"description": "Expiration date of the associated passport", "type": "string"},
        "passport_issue_date": {"description": "Issue date of the associated passport", "type": "string"},
        "passport_issuing_country": {"description": "Country that issued the passport", "type": "string"},
        "passport_number": {"description": "Passport number associated with the visa", "type": "string"},
        "place_of_birth": {"description": "Place or city of birth of the visa holder", "type": "string"},
        "sex": {"description": "Sex or gender of the visa holder", "type": "string"},
        "stay_duration": {"description": "Maximum permitted duration of stay", "type": "string"},
        "visa_number": {"description": "E-visa document, sticker, or application number", "type": "string"},
        "visa_type": {"description": "Type or category of visa (e.g., e-Tourist, e-Business)", "type": "string"},
    },
}

AADHAAR_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "aadhaar_no": {"description": "12-digit Aadhaar card number", "type": "string"},
        "dob": {"description": "Date of birth of the Aadhaar holder", "type": "string"},
        "first_name": {"description": "First name or given names of the person", "type": "string"},
        "last_name": {"description": "Last name or surname of the person", "type": "string"},
        "sex": {"description": "Sex or gender of the person (Male/Female/Transgender)", "type": "string"},
    },
}


class SarvamDocAIService:
    """
    Service to interact with Sarvam AI Document AI extraction API.
    Handles submitting extraction jobs, polling until completion, and retrieving structured results.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.base_url = (base_url or settings.SARVAM_BASE_URL).rstrip("/")
        self.poll_interval = settings.SARVAM_POLL_INTERVAL
        self.timeout_seconds = settings.SARVAM_TIMEOUT_SECONDS

    def _get_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SARVAM_API_KEY is not configured. Please set SARVAM_API_KEY in backend/.env.",
            )
        headers = {
            "api-subscription-key": self.api_key,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def submit_job(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
        schema: Optional[Dict[str, Any]] = None,
        language: str = "en-IN",
        model: str = "sarvam-vision-v1",
    ) -> Tuple[str, str]:
        """
        Submits an extraction job to Sarvam Doc AI.
        Returns a tuple of (job_id, initial_status).
        """
        url = f"{self.base_url}/doc-ai/v1/job/extract"
        idempotency_key = str(uuid.uuid4())
        headers = self._get_headers(idempotency_key=idempotency_key)

        data = {
            "language": language,
            "output_format": "json",
            "model": model,
            "schema": json.dumps(schema or PASSPORT_EXTRACTION_SCHEMA),
        }

        files = {
            "file": (filename, file_bytes, content_type)
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, data=data, files=files)

            if response.status_code not in (200, 201):
                logger.error(f"Sarvam API job submission failed: {response.status_code} - {response.text}")
                try:
                    err_json = response.json()
                    err_msg = err_json.get("message") or err_json.get("detail") or response.text
                except Exception:
                    err_msg = response.text
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Sarvam Doc AI submission error: {err_msg}",
                )

            job_resp = response.json()
            job_id = job_resp.get("job_id")
            job_status = job_resp.get("status", "pending")

            if not job_id:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Sarvam Doc AI did not return a valid job_id.",
                )

            logger.info(f"Sarvam Doc AI job submitted: job_id={job_id}, status={job_status}")
            return job_id, job_status

        except httpx.RequestError as exc:
            logger.error(f"Network error communicating with Sarvam AI: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Network error connecting to Sarvam AI: {str(exc)}",
            )

    async def poll_job_status(self, job_id: str) -> str:
        """
        Polls the job status until it reaches a terminal state or times out.
        Terminal states: completed, partially_completed, failed, rejected.
        """
        url = f"{self.base_url}/doc-ai/v1/job/{job_id}/status"
        headers = self._get_headers()
        start_time = asyncio.get_event_loop().time()

        terminal_states = {"completed", "partially_completed", "failed", "rejected"}

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.timeout_seconds:
                logger.error(f"Sarvam Doc AI job {job_id} timed out after {elapsed:.1f}s")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Sarvam Doc AI extraction job timed out after {self.timeout_seconds} seconds.",
                )

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    logger.warning(f"Error checking status for job {job_id}: {response.status_code}")
                    # Brief pause before retrying status check
                    await asyncio.sleep(self.poll_interval)
                    continue

                status_data = response.json()
                current_status = status_data.get("status", "").lower()
                logger.debug(f"Job {job_id} status: {current_status}")

                if current_status in terminal_states:
                    if current_status in {"failed", "rejected"}:
                        detail_msg = status_data.get("message") or f"Sarvam AI job ended with status: {current_status}"
                        logger.error(f"Job {job_id} failed: {detail_msg}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Sarvam Doc AI processing failed: {detail_msg}",
                        )
                    return current_status

            except httpx.RequestError as exc:
                logger.warning(f"Transient error polling Sarvam job {job_id}: {exc}")

            await asyncio.sleep(self.poll_interval)

    async def get_job_results(self, job_id: str) -> Dict[str, Any]:
        """
        Fetches the extraction results for a completed job.
        """
        url = f"{self.base_url}/doc-ai/v1/job/{job_id}/results"
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers, params={"format": "json"})

            if response.status_code != 200:
                logger.error(f"Failed to fetch results for job {job_id}: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to retrieve results from Sarvam AI for job {job_id}.",
                )

            return response.json()

        except httpx.RequestError as exc:
            logger.error(f"Network error fetching results for Sarvam job {job_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Network error retrieving Sarvam results: {str(exc)}",
            )

    async def extract_document_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generic end-to-end extraction workflow: submits job with custom schema,
        waits for completion, and returns parsed fields.
        """
        job_id, init_status = await self.submit_job(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            schema=schema,
        )

        final_status = await self.poll_job_status(job_id)
        logger.info(f"Sarvam job {job_id} finished with status: {final_status}")

        results = await self.get_job_results(job_id)
        return self._normalize_extracted_fields(results)

    async def extract_passport_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> Dict[str, Any]:
        """
        Passport-specific extraction workflow using PASSPORT_EXTRACTION_SCHEMA.
        """
        return await self.extract_document_data(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            schema=PASSPORT_EXTRACTION_SCHEMA,
        )

    async def extract_evisa_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> Dict[str, Any]:
        """
        E-Visa specific extraction workflow using EVISA_EXTRACTION_SCHEMA.
        """
        return await self.extract_document_data(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            schema=EVISA_EXTRACTION_SCHEMA,
        )

    async def extract_aadhaar_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> Dict[str, Any]:
        """
        Aadhaar-specific extraction workflow using AADHAAR_EXTRACTION_SCHEMA.
        """
        return await self.extract_document_data(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            schema=AADHAAR_EXTRACTION_SCHEMA,
        )

    def _normalize_extracted_fields(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses annotations dictionary into a flat dictionary of extracted field values and confidences.
        Supports both dict format { "value": ..., "confidence": ... } and direct values.
        """
        annotations = results.get("annotations") or {}
        direct_result = results.get("result") or {}
        extracted_fields: Dict[str, Optional[str]] = {}
        confidences = []

        # Process annotations (which typically contain values and confidence scores)
        if isinstance(annotations, dict):
            for field, data in annotations.items():
                if isinstance(data, dict):
                    val = data.get("value")
                    conf = data.get("confidence")
                else:
                    val = data
                    conf = None

                if conf is not None and isinstance(conf, (int, float)):
                    confidences.append(float(conf))

                if val is not None:
                    s_val = str(val).strip()
                    extracted_fields[field] = s_val if s_val else None
                else:
                    extracted_fields[field] = None

        # Supplement with direct_result if any fields were placed there directly
        if isinstance(direct_result, dict):
            for field, val in direct_result.items():
                if field not in extracted_fields or extracted_fields[field] is None:
                    if val is not None:
                        s_val = str(val).strip()
                        extracted_fields[field] = s_val if s_val else None

        # Calculate average confidence percentage (0-100)
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            # If confidence is 0.0 - 1.0, convert to 0-100
            score = int(avg_conf * 100) if avg_conf <= 1.0 else int(avg_conf)
            score = max(0, min(100, score))
        else:
            score = 100 if any(extracted_fields.values()) else 0

        return {
            "fields": extracted_fields,
            "valid_score": score,
            "raw_response": results,
        }
