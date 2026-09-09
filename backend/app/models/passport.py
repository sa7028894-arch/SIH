from typing import Optional
from pydantic import BaseModel, Field


class CheckDigitValidation(BaseModel):
    number: Optional[bool] = Field(default=None, description="Document number check digit validity")
    date_of_birth: Optional[bool] = Field(default=None, description="Date of birth check digit validity")
    expiration_date: Optional[bool] = Field(default=None, description="Expiration date check digit validity")
    composite: Optional[bool] = Field(default=None, description="Composite checksum validity")
    personal_number: Optional[bool] = Field(default=None, description="Personal number check digit validity")


class MRZData(BaseModel):
    name: Optional[str] = Field(default=None, description="Full name (names + surname)")
    document_number: Optional[str] = Field(default=None, description="Passport or document number")
    nationality: Optional[str] = Field(default=None, description="3-letter nationality code")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth (YYMMDD)")
    expiry_date: Optional[str] = Field(default=None, description="Expiration date (YYMMDD)")
    sex: Optional[str] = Field(default=None, description="Sex (M/F/<)")
    mrz_valid: bool = Field(default=False, description="Whether the MRZ validation passed (score > 80)")
    valid_score: int = Field(default=0, description="Confidence score 0-100 based on ICAO 9303 checksums")
    mrz_type: Optional[str] = Field(default=None, description="MRZ format type, e.g. TD1, TD2, TD3")
    country: Optional[str] = Field(default=None, description="Issuing country code")
    raw_text: Optional[str] = Field(default=None, description="Raw scanned MRZ lines text")
    extraction_method: str = Field(
        default="none",
        description="Method that succeeded ('passporteye_direct', 'opencv_crop_fallback', or 'none')"
    )
    check_digits: CheckDigitValidation = Field(
        default_factory=CheckDigitValidation,
        description="Individual checksum check digit validation states"
    )


class PassportValidationResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was processed successfully")
    mrz_detected: bool = Field(..., description="Whether an MRZ was located and read")
    message: str = Field(..., description="Descriptive status or error message")
    filename: str = Field(..., description="Original filename of the submitted media")
    data: Optional[MRZData] = Field(default=None, description="Extracted passport and MRZ data if detected")
