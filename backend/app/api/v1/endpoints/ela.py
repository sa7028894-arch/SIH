from fastapi import APIRouter, File, UploadFile, status

from app.controllers.ela_controller import ElaController
from app.models.ela import ElaAnalysisResponse

router = APIRouter()


@router.post(
    "/ela-analysis",
    response_model=ElaAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Error Level Analysis for photo replacement",
    description=(
        "Re-compresses the document as JPEG and compares ELA intensity in the "
        "portrait region versus the document background. Heuristic only."
    ),
)
async def analyze_ela(
    file: UploadFile = File(..., description="Identity document PDF or image file"),
) -> ElaAnalysisResponse:
    return await ElaController.analyze_media(file)
