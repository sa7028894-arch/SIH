from fastapi import APIRouter, File, UploadFile, status
from app.models.evisa import EVisaValidationResponse
from app.controllers.evisa_controller import EVisaController

router = APIRouter()


@router.post(
    "/evisa-validation",
    response_model=EVisaValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate E-Visa Media",
    description=(
        "Accepts an e-visa PDF document or image file and extracts structured visa, "
        "passport reference, and personal identity fields using Sarvam AI Document AI."
    ),
)
async def validate_evisa(
    file: UploadFile = File(..., description="E-visa PDF document or image file")
) -> EVisaValidationResponse:
    """
    Endpoint handler for e-visa media validation.
    Delegates extraction logic to EVisaController and SarvamDocAIService.
    """
    return await EVisaController.validate_evisa_media(file)
