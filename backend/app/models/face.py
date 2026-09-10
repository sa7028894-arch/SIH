from typing import Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int = Field(..., description="Top-left X coordinate of the face bounding box")
    y: int = Field(..., description="Top-left Y coordinate of the face bounding box")
    width: int = Field(..., description="Width of the face bounding box")
    height: int = Field(..., description="Height of the face bounding box")


class ExtractedFace(BaseModel):
    face_detected: bool = Field(default=False, description="Whether a face was found")
    image_base64: Optional[str] = Field(default=None, description="Base64 data URL of the cropped face image")
    bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box of the face in the source image")
    confidence: float = Field(default=0.0, description="Detection confidence score (0.0 to 1.0)")


class FaceExtractionResponse(BaseModel):
    success: bool = Field(..., description="Whether the request succeeded")
    face_detected: bool = Field(..., description="Whether a face was located in the media")
    message: str = Field(..., description="Status or descriptive message")
    filename: str = Field(..., description="Original filename of the submitted media")
    face: Optional[ExtractedFace] = Field(default=None, description="Cropped face details if detected")


class FaceCompareResponse(BaseModel):
    success: bool = Field(..., description="Whether comparison was executed successfully")
    is_match: bool = Field(..., description="Whether both faces match within the threshold")
    similarity_score: float = Field(..., description="Estimated similarity percentage (0.0% to 100.0%)")
    distance: float = Field(..., description="OpenFace embedding Euclidean distance")
    threshold: float = Field(..., description="Distance threshold used for the match decision")
    message: str = Field(..., description="Detailed verification status or warning message")
    doc_face: Optional[ExtractedFace] = Field(default=None, description="Cropped face from reference document")
    live_face: Optional[ExtractedFace] = Field(default=None, description="Cropped face from live camera/selfie")
