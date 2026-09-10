import io
import logging
import os
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image

from app.models.aadhaar import (
    AadhaarValidationResponse,
    AadhaarData,
)
from app.services.sarvam_service import SarvamDocAIService
from app.services.aadhaar_service import AadhaarValidationService

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class AadhaarController:
    """
    Controller responsible for handling Aadhaar media uploads, formatting media for Sarvam AI,
    validating UIDAI Verhoeff checksums, and returning structured Aadhaar card details.
    """

    @classmethod
    async def validate_aadhaar_media(
        cls,
        upload_file: UploadFile,
        service: Optional[SarvamDocAIService] = None,
    ) -> AadhaarValidationResponse:
        filename = upload_file.filename or "unknown_file"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported formats: Images (.jpg, .png, .webp, .tiff) and PDF (.pdf).",
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
            extraction_result = await sarvam_service.extract_aadhaar_data(
                file_bytes=final_bytes,
                filename=final_filename,
                content_type=content_type,
            )

            fields = extraction_result.get("fields", {})
            valid_score = extraction_result.get("valid_score", 100)

            aadhaar_data = cls._build_aadhaar_data(fields, valid_score)

            has_data = any([
                aadhaar_data.aadhaar_no,
                aadhaar_data.name,
                aadhaar_data.first_name,
                aadhaar_data.dob,
            ])

            if has_data:
                message = "Aadhaar card document successfully extracted via Sarvam AI."
                if aadhaar_data.checksum_valid is False:
                    message += " Warning: Aadhaar number failed Verhoeff checksum validation."

                return AadhaarValidationResponse(
                    success=True,
                    aadhaar_detected=True,
                    message=message,
                    filename=filename,
                    data=aadhaar_data,
                )

            return AadhaarValidationResponse(
                success=True,
                aadhaar_detected=False,
                message="No Aadhaar card information could be extracted from the document.",
                filename=filename,
                data=None,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing Aadhaar media '{filename}' with Sarvam AI: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing document: {str(e)}",
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
    def _build_aadhaar_data(cls, fields: dict, valid_score: int) -> AadhaarData:
        """Constructs an AadhaarData instance from extracted fields and runs Verhoeff checksum."""
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
        sex = cls._clean_field(fields.get("sex"))
        raw_aadhaar = cls._clean_field(fields.get("aadhaar_no"))

        # Run Verhoeff validation
        val_res = AadhaarValidationService.validate_aadhaar_number(raw_aadhaar)

        # Aadhaar validity considers whether number check digit succeeded (or if detected without number)
        if val_res.is_12_digits:
            aadhaar_valid = bool(val_res.is_valid)
        else:
            aadhaar_valid = bool(full_name or dob)

        return AadhaarData(
            name=full_name,
            first_name=first_name,
            last_name=last_name,
            dob=dob,
            sex=sex,
            aadhaar_no=val_res.clean_number or raw_aadhaar,
            formatted_aadhaar_no=val_res.formatted_number,
            checksum_valid=val_res.checksum_valid,
            aadhaar_valid=aadhaar_valid,
            valid_score=valid_score,
            extraction_method="sarvam-vision-v1",
        )
