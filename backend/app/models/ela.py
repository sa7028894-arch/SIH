from typing import Optional
from pydantic import BaseModel, Field

from app.models.face import BoundingBox


class ElaAnalysisResponse(BaseModel):
    success: bool = Field(..., description="Whether ELA analysis completed")
    is_suspicious: bool = Field(..., description="Whether photo vs background ELA ratio exceeds the threshold")
    face_detected: bool = Field(..., description="Whether a portrait face was located for the photo ROI")
    photo_ela_mean: float = Field(..., description="Mean ELA intensity in the photo ROI")
    background_ela_mean: float = Field(..., description="Mean ELA intensity in the background ROI")
    ratio: float = Field(..., description="max(photo, eps) / max(background, eps)")
    threshold: float = Field(..., description="Ratio threshold used for the suspicious flag")
    source_reencoded: bool = Field(..., description="True when the source was not a JPEG (ELA is weaker)")
    message: str = Field(..., description="Status or heuristic disclaimer")
    filename: str = Field(..., description="Original uploaded filename")
    heatmap_base64: Optional[str] = Field(default=None, description="JPEG data URL of the ELA heatmap")
    overlay_base64: Optional[str] = Field(default=None, description="JPEG data URL of original with ROI rectangles")
    photo_bbox: Optional[BoundingBox] = Field(default=None, description="Dilated photo region of interest")
    background_bbox: Optional[BoundingBox] = Field(default=None, description="Background region of interest")
