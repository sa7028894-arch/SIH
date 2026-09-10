from fastapi import APIRouter, File, UploadFile, status
from app.models.aadhaar import AadhaarValidationResponse
from app.controllers.aadhaar_controller import AadhaarController

router = APIRouter()


@router.post(
    "/aadhaar-validation",
    response_model=AadhaarValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Aadhaar Card Media",
    description=(
        "Accepts an Aadhaar card PDF document or image file and extracts structured Aadhaar number, "
        "personal identity fields, and validates the 12th check digit using the Verhoeff algorithm via Sarvam AI Document AI."
    ),
)
async def validate_aadhaar(
    file: UploadFile = File(..., description="Aadhaar card PDF document or image file")
) -> AadhaarValidationResponse:
    """
    Endpoint handler for Aadhaar card media validation.
    Delegates extraction logic to AadhaarController, SarvamDocAIService, and AadhaarValidationService.
    """
    return await AadhaarController.validate_aadhaar_media(file)
