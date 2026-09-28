from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PathologyUnitCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=100)
    sort_order: int = 0


class PathologyUnitUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class PathologyUnitRead(ORMModel):
    id: str
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PathologyParameterCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=200)
    unit_id: str | None = None
    data_type: str = Field(default="numeric", max_length=20)
    method: str | None = Field(None, max_length=150)
    sort_order: int = 0


class PathologyParameterUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    unit_id: str | None = None
    data_type: str | None = Field(None, max_length=20)
    method: str | None = Field(None, max_length=150)
    sort_order: int | None = None
    is_active: bool | None = None


class PathologyParameterRead(ORMModel):
    id: str
    code: str
    name: str
    unit_id: str | None
    unit_name: str | None = None
    unit_code: str | None = None
    data_type: str
    method: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PathologyServiceParameterCreate(BaseModel):
    service_id: str
    parameter_id: str
    sort_order: int = 0
    is_required: bool = True


class PathologyServiceParameterRead(ORMModel):
    id: str
    service_id: str
    service_code: str | None = None
    service_name: str | None = None
    parameter_id: str
    parameter_code: str | None = None
    parameter_name: str | None = None
    sort_order: int
    is_required: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PathologyNormalRangeCreate(BaseModel):
    parameter_id: str
    gender: str = Field(default="A", pattern="^[MFA]$")
    age_from_days: int = Field(default=0, ge=0)
    age_to_days: int = Field(default=36500, ge=0)
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    text_range: str | None = Field(None, max_length=200)
    unit_id: str | None = None
    sort_order: int = 0


class PathologyNormalRangeUpdate(BaseModel):
    gender: str | None = Field(None, pattern="^[MFA]$")
    age_from_days: int | None = Field(None, ge=0)
    age_to_days: int | None = Field(None, ge=0)
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    text_range: str | None = Field(None, max_length=200)
    unit_id: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class PathologyNormalRangeRead(ORMModel):
    id: str
    parameter_id: str
    parameter_code: str | None = None
    parameter_name: str | None = None
    gender: str
    age_from_days: int
    age_to_days: int
    min_value: Decimal | None
    max_value: Decimal | None
    text_range: str | None
    unit_id: str | None
    unit_name: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("min_value", "max_value", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class PathologyLabServiceCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=200)
    rate: Decimal = Field(default=Decimal("0"), ge=0)
    sub_category_id: str | None = None


class PathologyResultEntry(BaseModel):
    id: str
    result_value: str | None = Field(None, max_length=200)


class PathologyResultsUpdate(BaseModel):
    results: list[PathologyResultEntry]


class ReferenceRangeRow(BaseModel):
    age_group: str
    gender: str | None = None
    range_text: str


class PathologyResultRead(ORMModel):
    id: str
    order_id: str
    bill_line_id: str | None
    parameter_id: str
    parameter_code: str | None = None
    parameter_name: str | None = None
    service_id: str | None
    service_code: str | None = None
    service_name: str | None = None
    result_value: str | None
    result_numeric: Decimal | None
    unit_id: str | None
    unit_name: str | None = None
    reference_range_text: str | None
    additional_ranges: list[ReferenceRangeRow] = Field(default_factory=list)
    is_abnormal: bool
    status: str
    sort_order: int = 0
    bill_line_sort_order: int = 0
    panel_group_order: int = 0
    panel_service_id: str | None = None
    panel_name: str | None = None
    method: str | None = None

    @field_validator("result_numeric", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class PathologyOrderRead(ORMModel):
    id: str
    bill_id: str
    bill_no: str | None = None
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    order_date: date
    sample_date: date | None
    sample_no: str | None
    status: str
    pathologist_id: str | None
    pathologist_name: str | None = None
    authorized_at: datetime | None
    remarks: str | None
    results: list[PathologyResultRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PathologyResultTemplateCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=200)
    body: str = ""
    parameter_id: str | None = None
    service_id: str | None = None
    sort_order: int = 0


class PathologyResultTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    body: str | None = None
    parameter_id: str | None = None
    service_id: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class PathologyResultTemplateRead(ORMModel):
    id: str
    code: str
    name: str
    body: str
    parameter_id: str | None
    parameter_code: str | None = None
    parameter_name: str | None = None
    service_id: str | None
    service_code: str | None = None
    service_name: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PathologyWorkListItem(BaseModel):
    bill_id: str
    bill_no: str
    bill_date: date
    patient_no: str | None
    patient_name: str | None
    order_id: str | None
    order_status: str | None
    sample_no: str | None
    test_count: int
    result_pending: int
    net_amount: Decimal
    referring_doctor: str | None

    @field_validator("net_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
