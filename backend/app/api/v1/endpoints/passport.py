from fastapi import APIRouter, File, UploadFile, status
from app.models.passport import PassportValidationResponse
from app.controllers.passport_controller import PassportController

router = APIRouter()


@router.post(
    "/passport-validation",
    response_model=PassportValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Passport Media",
    description=(
        "Accepts a passport image (JPG, PNG, WEBP, TIFF) or PDF document, "
        "and extracts structured identity fields and MRZ using Sarvam AI Document AI."
    ),
)
async def validate_passport(
    file: UploadFile = File(..., description="Passport image or PDF document file")
) -> PassportValidationResponse:
    """
    View / Endpoint handler for passport media validation.
    Delegates extraction logic to PassportController and SarvamDocAIService.
    """
    return await PassportController.validate_passport_media(file)
