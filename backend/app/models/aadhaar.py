from typing import Optional
from pydantic import BaseModel, Field


class AadhaarData(BaseModel):
    # Personal Identity Information
    name: Optional[str] = Field(default=None, description="Full name (first name + last name)")
    first_name: Optional[str] = Field(default=None, description="First name or given names of the person")
    last_name: Optional[str] = Field(default=None, description="Last name or surname of the person")
    dob: Optional[str] = Field(default=None, description="Date of birth")
    sex: Optional[str] = Field(default=None, description="Sex or gender of the card holder")

    # Aadhaar Number & Checksum
    aadhaar_no: Optional[str] = Field(default=None, description="Extracted 12-digit Aadhaar number")
    formatted_aadhaar_no: Optional[str] = Field(default=None, description="Formatted Aadhaar number (XXXX XXXX XXXX)")
    checksum_valid: Optional[bool] = Field(
        default=None,
        description="Whether the Verhoeff checksum algorithm verified the 12th check digit",
    )

    # Validation Status & Metadata
    aadhaar_valid: bool = Field(
        default=True,
        description="Whether Aadhaar details were successfully recognized and validated",
    )
    valid_score: int = Field(
        default=100,
        description="Extraction confidence score (0-100)",
    )
    extraction_method: str = Field(
        default="sarvam-vision-v1",
        description="Service used for extraction",
    )


class AadhaarValidationResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was processed successfully")
    aadhaar_detected: bool = Field(..., description="Whether an Aadhaar card was located and parsed")
    message: str = Field(..., description="Descriptive status or error message")
    filename: str = Field(..., description="Original filename of the submitted media")
    data: Optional[AadhaarData] = Field(default=None, description="Extracted Aadhaar data if detected")
