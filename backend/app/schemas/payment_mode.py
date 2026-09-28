from datetime import datetime



from pydantic import BaseModel, Field



from app.schemas.common import ORMModel





class PaymentModeCreate(BaseModel):

    code: str = Field(..., min_length=1, max_length=30)

    name: str = Field(..., min_length=2, max_length=150)

    is_cash: bool = False

    ledger_id: str | None = None

    sort_order: int = 0

    is_active: bool = True





class PaymentModeUpdate(BaseModel):

    name: str | None = Field(None, min_length=2, max_length=150)

    is_cash: bool | None = None

    ledger_id: str | None = None

    sort_order: int | None = None

    is_active: bool | None = None





class PaymentModeRead(ORMModel):

    id: str

    code: str

    name: str

    is_cash: bool

    ledger_id: str | None = None

    ledger_code: str | None = None

    ledger_name: str | None = None

    sort_order: int

    is_active: bool

    created_at: datetime

    updated_at: datetime

