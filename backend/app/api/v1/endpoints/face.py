from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, status

from app.models.face import FaceExtractionResponse, FaceCompareResponse
from app.controllers.face_controller import FaceController

router = APIRouter()


@router.post(
    "/extract-face",
    response_model=FaceExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Cardholder Face from Document",
    description="Detects and crops the portrait face from an identity document image or PDF.",
)
async def extract_face(
    file: UploadFile = File(..., description="Identity document PDF or image file")
) -> FaceExtractionResponse:
    """
    Endpoint handler to detect and crop portrait face from a document.
    """
    return await FaceController.extract_face_from_media(file)


@router.post(
    "/face-compare",
    response_model=FaceCompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare Document Face vs Live Face",
    description="Extracts faces from reference document and live webcam capture, then computes OpenFace embeddings and distance/similarity.",
)
async def compare_faces(
    document_file: UploadFile = File(..., description="Reference document PDF or image"),
    live_file: UploadFile = File(..., description="Live camera snapshot or selfie image"),
    threshold: Optional[float] = Form(default=None, description="Optional match distance threshold (default: 0.75)"),
) -> FaceCompareResponse:
    """
    Endpoint handler for real-time face comparison.
    """
    return await FaceController.compare_faces(
        document_file=document_file,
        live_file=live_file,
        threshold=threshold,
    )
