"""Clean lab-test / profile schemas (no legacy code or parameter jargon)."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ReferenceRangeIn(BaseModel):
    gender: str = Field(default="A", pattern="^[MFA]$")
    age_from: int = Field(default=0, ge=0)
    age_to: int = Field(default=120, ge=0)
    age_unit: str = Field(default="years", pattern="^(days|weeks|months|years)$")
    low: Decimal | None = None
    high: Decimal | None = None
    text_range: str | None = Field(None, max_length=200)


class ReferenceRangeRead(BaseModel):
    id: str
    gender: str
    age_from: int
    age_to: int
    age_unit: str
    low: Decimal | None
    high: Decimal | None
    text_range: str | None

    @field_validator("low", "high", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class LabTestSave(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    unit_id: str | None = None
    result_type: str = Field(default="numeric", pattern="^(numeric|text)$")
    method: str | None = Field(None, max_length=150)
    sub_category_id: str | None = None
    ranges: list[ReferenceRangeIn] = Field(default_factory=list)


class LabTestRead(BaseModel):
    id: str
    code: str | None = None
    name: str
    price: Decimal
    unit_id: str | None = None
    unit_name: str | None = None
    result_type: str
    method: str | None = None
    sub_category_id: str | None = None
    sub_category_name: str | None = None
    is_profile: bool = False
    ranges: list[ReferenceRangeRead] = Field(default_factory=list)

    @field_validator("price", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class ProfileMember(BaseModel):
    id: str
    code: str | None = None
    name: str
    is_bundle: bool = False


class ProfileSave(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    sub_category_id: str | None = None
    member_test_ids: list[str] = Field(default_factory=list)


class ProfileRead(BaseModel):
    id: str
    code: str | None = None
    name: str
    price: Decimal
    sub_category_id: str | None = None
    sub_category_name: str | None = None
    members: list[ProfileMember] = Field(default_factory=list)

    @field_validator("price", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
