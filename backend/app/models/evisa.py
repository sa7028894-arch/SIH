from typing import Optional
from pydantic import BaseModel, Field


class EVisaData(BaseModel):
    # Personal Identity Information
    name: Optional[str] = Field(default=None, description="Full name (first name + last name)")
    first_name: Optional[str] = Field(default=None, description="First name of the visa holder")
    last_name: Optional[str] = Field(default=None, description="Last name of the visa holder")
    dob: Optional[str] = Field(default=None, description="Date of birth")
    place_of_birth: Optional[str] = Field(default=None, description="Place or city of birth")
    sex: Optional[str] = Field(default=None, description="Sex / Gender")
    nationality: Optional[str] = Field(default=None, description="Nationality")

    # Associated Passport Details
    passport_number: Optional[str] = Field(default=None, description="Passport number")
    passport_issuing_country: Optional[str] = Field(default=None, description="Passport issuing country")
    passport_issue_date: Optional[str] = Field(default=None, description="Passport issue date")
    passport_expiration_date: Optional[str] = Field(default=None, description="Passport expiration date")

    # Visa Authorization Details
    visa_number: Optional[str] = Field(default=None, description="Visa number or application ID")
    visa_type: Optional[str] = Field(default=None, description="Type or purpose of visa (e.g. e-Tourist, e-Business)")
    stay_duration: Optional[str] = Field(default=None, description="Permitted duration of stay")
    entry_validation: Optional[str] = Field(default=None, description="Entry validity dates or validity period")

    # Validation Status & Metadata
    visa_valid: bool = Field(
        default=True,
        description="Whether visa information was successfully recognized and extracted",
    )
    valid_score: int = Field(
        default=100,
        description="Extraction confidence score (0-100)",
    )
    extraction_method: str = Field(
        default="sarvam-vision-v1",
        description="Service used for extraction",
    )


class EVisaValidationResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was processed successfully")
    visa_detected: bool = Field(..., description="Whether an e-visa was located and parsed")
    message: str = Field(..., description="Descriptive status or error message")
    filename: str = Field(..., description="Original filename of the submitted media")
    data: Optional[EVisaData] = Field(default=None, description="Extracted e-visa data if detected")
