from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class BillPaymentCreate(BaseModel):
    payment_mode_id: str
    amount: Decimal = Field(..., gt=0)

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class BillPaymentRead(ORMModel):
    id: str
    payment_mode_id: str
    payment_mode_code: str | None = None
    payment_mode_name: str | None = None
    ledger_id: str | None = None
    ledger_code: str | None = None
    ledger_name: str | None = None
    amount: Decimal
    sort_order: int

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
