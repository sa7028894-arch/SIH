from typing import Optional
from pydantic import BaseModel, Field


class CheckDigitValidation(BaseModel):
    number: Optional[bool] = Field(default=None, description="Document number check digit validity")
    date_of_birth: Optional[bool] = Field(default=None, description="Date of birth check digit validity")
    expiration_date: Optional[bool] = Field(default=None, description="Expiration date check digit validity")
    composite: Optional[bool] = Field(default=None, description="Composite checksum validity")
    personal_number: Optional[bool] = Field(default=None, description="Personal number check digit validity")


class MRZData(BaseModel):
    # Normalized / Common fields for frontend and general consumers
    name: Optional[str] = Field(default=None, description="Full name (first name + last name)")
    document_number: Optional[str] = Field(default=None, description="Passport or document number")
    nationality: Optional[str] = Field(default=None, description="Nationality or issuing nationality code")
    date_of_birth: Optional[str] = Field(default=None, description="Date of birth")
    expiry_date: Optional[str] = Field(default=None, description="Date of expiry")
    sex: Optional[str] = Field(default=None, description="Sex / Gender")
    country: Optional[str] = Field(default=None, description="Issuing country code")
    mrz_type: Optional[str] = Field(default=None, description="MRZ / Passport format type")
    raw_text: Optional[str] = Field(default=None, description="Raw scanned MRZ lines text")

    # Detailed Sarvam AI Document AI extracted fields
    first_name: Optional[str] = Field(default=None, description="First name of the person")
    last_name: Optional[str] = Field(default=None, description="Last name of the person")
    passport_number: Optional[str] = Field(default=None, description="Passport number")
    dob: Optional[str] = Field(default=None, description="Date of birth")
    date_of_issue: Optional[str] = Field(default=None, description="Date of issue")
    date_of_expiry: Optional[str] = Field(default=None, description="Date of expiry")
    place_of_issue: Optional[str] = Field(default=None, description="Place of issue")
    country_code: Optional[str] = Field(default=None, description="Country code")
    type_of_passport: Optional[str] = Field(default=None, description="Type of passport")
    mrz: Optional[str] = Field(default=None, description="Extracted MRZ string")

    # Status & metadata
    mrz_valid: bool = Field(
        default=True,
        description="Whether passport document information was successfully extracted",
    )
    valid_score: int = Field(
        default=100,
        description="Confidence score 0-100 from extraction service",
    )
    extraction_method: str = Field(
        default="sarvam-vision-v1",
        description="Extraction service/engine used",
    )
    check_digits: CheckDigitValidation = Field(
        default_factory=CheckDigitValidation,
        description="Checksum validation states (skipped when using hosted Sarvam Doc AI)",
    )


class PassportValidationResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was processed successfully")
    mrz_detected: bool = Field(..., description="Whether passport data / MRZ was located and read")
    message: str = Field(..., description="Descriptive status or error message")
    filename: str = Field(..., description="Original filename of the submitted media")
    data: Optional[MRZData] = Field(default=None, description="Extracted passport data if detected")
