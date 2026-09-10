import io
import logging
import os
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image

from app.models.evisa import (
    EVisaValidationResponse,
    EVisaData,
)
from app.services.sarvam_service import SarvamDocAIService

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class EVisaController:
    """
    Controller responsible for handling e-visa media uploads, formatting media for Sarvam AI,
    and returning structured e-visa and passport details.
    """

    @classmethod
    async def validate_evisa_media(
        cls,
        upload_file: UploadFile,
        service: Optional[SarvamDocAIService] = None,
    ) -> EVisaValidationResponse:
        filename = upload_file.filename or "unknown_file"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported formats: Images (.jpg, .png, .webp, .tiff) and PDF (.pdf)."
            )

        file_bytes = await upload_file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        content_type, final_bytes, final_filename = cls._prepare_media_for_sarvam(file_bytes, filename, ext)

        sarvam_service = service or SarvamDocAIService()

        try:
            extraction_result = await sarvam_service.extract_evisa_data(
                file_bytes=final_bytes,
                filename=final_filename,
                content_type=content_type,
            )

            fields = extraction_result.get("fields", {})
            valid_score = extraction_result.get("valid_score", 100)

            evisa_data = cls._build_evisa_data(fields, valid_score)

            has_data = any([
                evisa_data.visa_number,
                evisa_data.passport_number,
                evisa_data.name,
                evisa_data.visa_type,
                evisa_data.nationality,
            ])

            if has_data:
                return EVisaValidationResponse(
                    success=True,
                    visa_detected=True,
                    message="E-Visa document successfully extracted via Sarvam AI.",
                    filename=filename,
                    data=evisa_data,
                )

            return EVisaValidationResponse(
                success=True,
                visa_detected=False,
                message="No e-visa information could be extracted from the document.",
                filename=filename,
                data=None,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing e-visa media '{filename}' with Sarvam AI: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing document: {str(e)}"
            )

    @classmethod
    def _prepare_media_for_sarvam(
        cls,
        file_bytes: bytes,
        filename: str,
        ext: str,
    ) -> tuple[str, bytes, str]:
        """
        Ensures media is in a format accepted natively by Sarvam Doc AI (.pdf, .jpg, .png).
        Converts .webp, .bmp, and .tiff formats into JPEG in-memory.
        """
        if ext == ".pdf":
            return "application/pdf", file_bytes, filename
        if ext in {".jpg", ".jpeg"}:
            return "image/jpeg", file_bytes, filename
        if ext == ".png":
            return "image/png", file_bytes, filename

        # Format is webp, bmp, tiff, etc. -> convert to JPEG
        try:
            pil_img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=95)
            new_filename = f"{os.path.splitext(filename)[0]}.jpg"
            return "image/jpeg", buf.getvalue(), new_filename
        except Exception as err:
            logger.warning(f"Image conversion to JPEG failed: {err}")
            return "application/octet-stream", file_bytes, filename

    @staticmethod
    def _clean_field(val: Optional[str]) -> Optional[str]:
        """Sanitizes text fields by removing extra whitespace."""
        if not val or not isinstance(val, str):
            return None
        s = " ".join(val.strip().split())
        return s if s else None

    @classmethod
    def _build_evisa_data(cls, fields: dict, valid_score: int) -> EVisaData:
        """Constructs an EVisaData instance from extracted fields."""
        first_name = cls._clean_field(fields.get("first_name"))
        last_name = cls._clean_field(fields.get("last_name"))

        if first_name and last_name:
            full_name = f"{first_name} {last_name}".strip()
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = None

        dob = cls._clean_field(fields.get("dob"))
        place_of_birth = cls._clean_field(fields.get("place_of_birth"))
        sex = cls._clean_field(fields.get("sex"))
        nationality = cls._clean_field(fields.get("nationality"))

        passport_number = cls._clean_field(fields.get("passport_number"))
        passport_issuing_country = cls._clean_field(fields.get("passport_issuing_country"))
        passport_issue_date = cls._clean_field(fields.get("passport_issue_date"))
        passport_expiration_date = cls._clean_field(fields.get("passport_expiration_date"))

        visa_number = cls._clean_field(fields.get("visa_number"))
        visa_type = cls._clean_field(fields.get("visa_type"))
        stay_duration = cls._clean_field(fields.get("stay_duration"))
        entry_validation = cls._clean_field(fields.get("entry_validation"))

        has_data = bool(visa_number or passport_number or full_name)

        return EVisaData(
            name=full_name,
            first_name=first_name,
            last_name=last_name,
            dob=dob,
            place_of_birth=place_of_birth,
            sex=sex,
            nationality=nationality,
            passport_number=passport_number,
            passport_issuing_country=passport_issuing_country,
            passport_issue_date=passport_issue_date,
            passport_expiration_date=passport_expiration_date,
            visa_number=visa_number,
            visa_type=visa_type,
            stay_duration=stay_duration,
            entry_validation=entry_validation,
            visa_valid=has_data,
            valid_score=valid_score,
            extraction_method="sarvam-vision-v1",
        )
