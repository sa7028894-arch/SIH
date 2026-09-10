import logging
import os
from typing import Optional
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.models.face import (
    FaceExtractionResponse,
    FaceCompareResponse,
)
from app.services.face_detector import FaceDetectorService
from app.services.openface_service import OpenFaceService

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class FaceController:
    """
    Controller handling document face extraction and real-time face comparison
    between reference identity documents and live camera captures.
    """

    @classmethod
    async def extract_face_from_media(cls, upload_file: UploadFile) -> FaceExtractionResponse:
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

        try:
            face, _ = FaceDetectorService.extract_face_from_bytes(file_bytes, filename)

            if face.face_detected:
                return FaceExtractionResponse(
                    success=True,
                    face_detected=True,
                    message="Face successfully detected and cropped from document.",
                    filename=filename,
                    face=face,
                )

            return FaceExtractionResponse(
                success=True,
                face_detected=False,
                message="No face could be detected in the provided media.",
                filename=filename,
                face=None,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during face extraction for '{filename}': {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error extracting face from media: {str(e)}",
            )

    @classmethod
    async def compare_faces(
        cls,
        document_file: UploadFile,
        live_file: UploadFile,
        threshold: Optional[float] = None,
    ) -> FaceCompareResponse:
        doc_filename = document_file.filename or "document_file"
        live_filename = live_file.filename or "live_file"

        doc_ext = os.path.splitext(doc_filename)[1].lower()
        live_ext = os.path.splitext(live_filename)[1].lower()

        if doc_ext not in ALLOWED_EXTENSIONS or live_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported media format. Supported formats: Images (.jpg, .png, .webp, .tiff) and PDF (.pdf).",
            )

        doc_bytes = await document_file.read()
        live_bytes = await live_file.read()

        if not doc_bytes or not live_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or both uploaded files are empty.",
            )

        match_threshold = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD

        try:
            # 1. Detect and crop face from reference document
            doc_face, doc_crop = FaceDetectorService.extract_face_from_bytes(doc_bytes, doc_filename)
            if not doc_face.face_detected or doc_crop is None:
                return FaceCompareResponse(
                    success=True,
                    is_match=False,
                    similarity_score=0.0,
                    distance=2.0,
                    threshold=match_threshold,
                    message="Could not detect a clear face in the reference document. Please upload a clear document image.",
                    doc_face=doc_face,
                    live_face=None,
                )

            # 2. Detect and crop face from live snapshot
            live_face, live_crop = FaceDetectorService.extract_face_from_bytes(live_bytes, live_filename)
            if not live_face.face_detected or live_crop is None:
                return FaceCompareResponse(
                    success=True,
                    is_match=False,
                    similarity_score=0.0,
                    distance=2.0,
                    threshold=match_threshold,
                    message="Could not detect a face in the live camera image. Please ensure your face is well-lit and facing the camera.",
                    doc_face=doc_face,
                    live_face=live_face,
                )

            # 3. Compute OpenFace embeddings and compare
            is_match, similarity_score, distance = OpenFaceService.compare_faces(
                doc_crop,
                live_crop,
                threshold=match_threshold,
            )

            if is_match:
                msg = f"Identity verified: Faces match with {similarity_score}% similarity."
            else:
                msg = f"Identity mismatch: Faces do not match within threshold (Similarity: {similarity_score}%, Distance: {distance:.2f}, Threshold: {match_threshold:.2f})."

            return FaceCompareResponse(
                success=True,
                is_match=is_match,
                similarity_score=similarity_score,
                distance=distance,
                threshold=match_threshold,
                message=msg,
                doc_face=doc_face,
                live_face=live_face,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error comparing faces: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Face comparison error: {str(e)}",
            )
