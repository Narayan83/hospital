from datetime import datetime

from decimal import Decimal

from typing import Literal



from pydantic import BaseModel, Field, field_validator, model_validator



from app.schemas.common import ORMModel



LedgerType = Literal["ASSET", "LIABILITY", "INCOME", "EXPENSE"]





class LedgerCreate(BaseModel):

    code: str = Field(..., min_length=1, max_length=30)

    name: str = Field(..., min_length=2, max_length=150)

    ledger_type: LedgerType = "ASSET"

    opening_balance: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    is_cash: bool = False

    is_bank: bool = False

    is_patient_deposit: bool = False

    sort_order: int = 0

    is_active: bool = True



    @field_validator("opening_balance", mode="before")

    @classmethod

    def _coerce_opening(cls, value):

        if value is None or value == "":

            return Decimal("0")

        return value



    @model_validator(mode="after")

    def _validate_flags(self):

        if self.is_cash and self.is_bank:

            raise ValueError("A ledger cannot be both Cash and Bank")

        return self





class LedgerUpdate(BaseModel):

    name: str | None = Field(None, min_length=2, max_length=150)

    ledger_type: LedgerType | None = None

    opening_balance: Decimal | None = Field(None, ge=Decimal("0"))

    is_cash: bool | None = None

    is_bank: bool | None = None

    is_patient_deposit: bool | None = None

    sort_order: int | None = None

    is_active: bool | None = None



    @field_validator("opening_balance", mode="before")

    @classmethod

    def _coerce_opening(cls, value):

        if value is None or value == "":

            return None

        return value



    @model_validator(mode="after")

    def _validate_flags(self):

        if self.is_cash is True and self.is_bank is True:

            raise ValueError("A ledger cannot be both Cash and Bank")

        return self





class LedgerRead(ORMModel):

    id: str

    code: str

    name: str

    ledger_type: str

    opening_balance: Decimal

    is_cash: bool

    is_bank: bool

    is_patient_deposit: bool

    sort_order: int

    is_active: bool

    created_at: datetime

    updated_at: datetime


