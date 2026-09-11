import logging
import os

from fastapi import HTTPException, UploadFile, status

from app.models.ela import ElaAnalysisResponse
from app.services.ela_service import ElaService

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class ElaController:
    @classmethod
    async def analyze_media(cls, upload_file: UploadFile) -> ElaAnalysisResponse:
        filename = upload_file.filename or "unknown_file"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file format '{ext}'. "
                    "Supported formats: Images (.jpg, .png, .webp, .tiff) and PDF (.pdf)."
                ),
            )

        file_bytes = await upload_file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        try:
            return ElaService.analyze_bytes(file_bytes, filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            logger.error("ELA analysis failed for '%s': %s", filename, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to run error level analysis on the uploaded document.",
            ) from exc
