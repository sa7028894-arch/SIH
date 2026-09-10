import io
import logging
import os
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image

from app.models.passport import (
    PassportValidationResponse,
    MRZData,
    CheckDigitValidation,
)
from app.services.sarvam_service import SarvamDocAIService
from app.services.mrz_service import MRZValidationService

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class PassportController:
    """
    Controller responsible for handling passport media uploads and running
    hosted Sarvam AI Document AI extraction without local MRZ checksumming.
    """

    @classmethod
    async def validate_passport_media(
        cls,
        upload_file: UploadFile,
        service: Optional[SarvamDocAIService] = None,
    ) -> PassportValidationResponse:
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

        # Prepare appropriate MIME content type and normalize unsupported formats for Sarvam
        content_type, final_bytes, final_filename = cls._prepare_media_for_sarvam(file_bytes, filename, ext)

        sarvam_service = service or SarvamDocAIService()

        try:
            extraction_result = await sarvam_service.extract_passport_data(
                file_bytes=final_bytes,
                filename=final_filename,
                content_type=content_type,
            )

            fields = extraction_result.get("fields", {})
            valid_score = extraction_result.get("valid_score", 100)

            mrz_data = cls._build_passport_data(fields, valid_score)

            # Check if any significant identity or document information was detected
            has_data = any([
                mrz_data.name,
                mrz_data.document_number,
                mrz_data.raw_text,
                mrz_data.date_of_birth,
                mrz_data.nationality,
            ])

            if has_data:
                if mrz_data.raw_text and mrz_data.mrz_valid:
                    message = "Passport MRZ successfully detected and validated."
                elif mrz_data.raw_text:
                    message = f"Passport MRZ detected with checksum warnings ({mrz_data.valid_score}% score)."
                else:
                    message = "Passport identity fields extracted (no MRZ zone detected)."

                return PassportValidationResponse(
                    success=True,
                    mrz_detected=bool(mrz_data.raw_text),
                    message=message,
                    filename=filename,
                    data=mrz_data,
                )

            return PassportValidationResponse(
                success=True,
                mrz_detected=False,
                message="No passport or identity information could be extracted from the document.",
                filename=filename,
                data=None,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing passport media '{filename}' with Sarvam AI: {str(e)}", exc_info=True)
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
        Ensures the media is in a format natively accepted by Sarvam Doc AI (.pdf, .jpg, .png).
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
            # Fallback to original bytes
            return "application/octet-stream", file_bytes, filename

    @staticmethod
    def _clean_field(val: Optional[str], is_name: bool = False) -> Optional[str]:
        """
        Sanitizes extracted fields by removing trailing and filler '<' characters.
        If is_name is True, replaces internal '<' separators with spaces and collapses whitespace.
        Returns None if the cleaned value is empty or consists solely of '<'.
        """
        if not val or not isinstance(val, str):
            return None

        s = val.strip()
        if is_name:
            s = s.replace("<", " ")
            s = " ".join(s.split())
        else:
            s = s.strip("< ").rstrip("<").strip()

        return s if s else None

    @classmethod
    def _build_passport_data(cls, fields: dict, ocr_score: int) -> MRZData:
        """
        Constructs an MRZData object from Sarvam's extracted field dictionary,
        and validates ICAO 9303 MRZ checksums using MRZValidationService if MRZ text is present.
        """
        first_name = cls._clean_field(fields.get("first_name"), is_name=True)
        last_name = cls._clean_field(fields.get("last_name"), is_name=True)

        if first_name and last_name:
            full_name = f"{first_name} {last_name}".strip()
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = None

        document_number = cls._clean_field(fields.get("passport_number"))
        nationality = cls._clean_field(fields.get("nationality"))
        country_code = cls._clean_field(fields.get("country_code"))
        dob = cls._clean_field(fields.get("dob"))
        date_of_expiry = cls._clean_field(fields.get("date_of_expiry"))
        date_of_issue = cls._clean_field(fields.get("date_of_issue"))
        place_of_issue = cls._clean_field(fields.get("place_of_issue"))
        sex = cls._clean_field(fields.get("sex"))
        type_of_passport = cls._clean_field(fields.get("type_of_passport"))
        raw_mrz = fields.get("mrz")

        # Validate MRZ checksums if MRZ text was returned by OCR
        if raw_mrz:
            mrz_result = MRZValidationService.validate_mrz(raw_mrz)
            check_digits = mrz_result.check_digits
            mrz_valid = mrz_result.is_valid
            final_score = mrz_result.valid_score
            cleaned_mrz = mrz_result.cleaned_mrz or raw_mrz
            mrz_type = mrz_result.mrz_type or type_of_passport
        else:
            check_digits = CheckDigitValidation(
                number=None,
                date_of_birth=None,
                expiration_date=None,
                composite=None,
                personal_number=None,
            )
            has_id_data = bool(full_name or document_number)
            mrz_valid = has_id_data
            final_score = ocr_score
            cleaned_mrz = None
            mrz_type = type_of_passport

        return MRZData(
            name=full_name,
            document_number=document_number,
            nationality=nationality,
            date_of_birth=dob,
            expiry_date=date_of_expiry,
            sex=sex,
            country=country_code,
            mrz_type=mrz_type,
            raw_text=cleaned_mrz,
            first_name=first_name,
            last_name=last_name,
            passport_number=document_number,
            dob=dob,
            date_of_issue=date_of_issue,
            date_of_expiry=date_of_expiry,
            place_of_issue=place_of_issue,
            country_code=country_code,
            type_of_passport=type_of_passport,
            mrz=cleaned_mrz,
            mrz_valid=mrz_valid,
            valid_score=final_score,
            extraction_method="sarvam-vision-v1",
            check_digits=check_digits,
        )
