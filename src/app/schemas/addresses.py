import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BatchStatusType = Literal["queued", "processing", "completed", "failed"]
ResidentialIndicatorType = Literal["unknown", "yes", "no"]
ValidationStatusType = Literal["verified", "unverified", "error"]
MessageLevelType = Literal["info", "warning", "error"]


class AddressInputSchema(BaseModel):
    """Input schema for address data."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company_name: str | None = None

    address_line1: str = Field(min_length=1, description="Primary address line")
    address_line2: str | None = None
    address_line3: str | None = None

    city_locality: str = Field(min_length=1, description="City or locality name")
    state_province: str = Field(min_length=1, description="State or province code")
    postal_code: str | int | None = None
    country_code: str = Field(min_length=2, max_length=2, description="ISO country code")

    address_residential_indicator: ResidentialIndicatorType = "unknown"

    @field_validator("address_residential_indicator", mode="before")
    @classmethod
    def validate_residential_indicator(cls, value: Any) -> str:
        """Normalize residential indicator value."""
        if value is None:
            return "unknown"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"unknown", "yes", "no"}:
                return normalized
        return "unknown"


class AddressOutputSchema(AddressInputSchema):
    """Output schema for address data."""

    pass


class ValidationMessageSchema(BaseModel):
    """Schema for validation messages."""

    code: str
    message: str
    level: MessageLevelType = "info"


class ValidationResultSchema(BaseModel):
    """Schema for address validation result."""

    status: ValidationStatusType
    original_address: AddressOutputSchema
    matched_address: AddressOutputSchema
    messages: list[ValidationMessageSchema] = Field(default_factory=list)


class BatchInfoSchema(BaseModel):
    """Schema for validation batch information."""

    id: uuid.UUID
    status: BatchStatusType
    created_at: datetime
    items_count: int = 0
    request_payload: list[dict[str, Any]] | None = None


class RecognitionInputAddressSchema(BaseModel):
    """Schema for known address values in recognition request."""

    name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_line3: str | None = None
    city_locality: str | None = None
    state_province: str | None = None
    postal_code: str | int | None = None
    country_code: str | None = None
    address_residential_indicator: ResidentialIndicatorType | None = None


class RecognitionRequestSchema(BaseModel):
    """Schema for address recognition request."""

    text: str = Field(min_length=1, description="Text to recognize address from")
    address: RecognitionInputAddressSchema | None = None


class RecognizedEntitySchema(BaseModel):
    """Schema for recognized entity in address recognition."""

    type: str
    score: float
    text: str | int
    start_index: int
    end_index: int
    result: dict[str, Any]


class RecognitionOutputSchema(BaseModel):
    """Schema for address recognition output."""

    score: float
    address: dict[str, Any]
    entities: list[RecognizedEntitySchema]


class PartialAddressSchema(BaseModel):
    """Schema for partial address data."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company_name: str | None = None

    address_line1: str | None = None
    address_line2: str | None = None
    address_line3: str | None = None
    city_locality: str | None = None
    state_province: str | None = None
    postal_code: str | int | None = None
    country_code: str | None = None
    address_residential_indicator: ResidentialIndicatorType | None = None


class RecognitionResultSchema(BaseModel):
    """Schema for address recognition result."""

    status: Literal["recognized", "error"] = "recognized"
    original_address: PartialAddressSchema
    recognized_address: PartialAddressSchema
