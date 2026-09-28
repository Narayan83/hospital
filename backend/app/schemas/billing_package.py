from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class BillingPackageItemBase(BaseModel):
    service_id: str
    quantity: int = Field(default=1, ge=1)
    rate_override: Decimal | None = Field(None, ge=0)
    sort_order: int = 0


class BillingPackageItemCreate(BillingPackageItemBase):
    pass


class BillingPackageItemRead(ORMModel):
    id: str
    service_id: str
    service_code: str | None = None
    service_name: str | None = None
    service_rate: Decimal | None = None
    quantity: int
    rate_override: Decimal | None
    sort_order: int
    is_active: bool

    @field_validator("rate_override", "service_rate", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class BillingPackageBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=200)
    package_total: Decimal | None = Field(None, ge=0)
    description: str | None = None
    sort_order: int = 0


class BillingPackageCreate(BillingPackageBase):
    pass


class BillingPackageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    package_total: Decimal | None = Field(None, ge=0)
    description: str | None = None
    sort_order: int | None = None


class BillingPackageRead(ORMModel):
    id: str
    code: str
    name: str
    package_total: Decimal | None
    description: str | None
    sort_order: int
    is_active: bool
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator("package_total", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class BillingPackageDetailRead(BillingPackageRead):
    items: list[BillingPackageItemRead] = Field(default_factory=list)


class BillingPackageItemsReplace(BaseModel):
    items: list[BillingPackageItemCreate] = Field(default_factory=list)
