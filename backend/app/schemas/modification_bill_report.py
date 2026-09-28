from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ModificationBillReportRow(BaseModel):
    serial_no: int
    bill_type: str
    bill_date: date
    bill_no: str
    patient_no: str
    patient_name: str
    net_amount: Decimal = Field(..., decimal_places=2)
    modified_at: datetime | None = None
    modified_by: str | None = None


class ModificationBillReportRead(BaseModel):
    from_date: date
    to_date: date
    bill_type: str
    rows: list[ModificationBillReportRow]
    grand_total: Decimal = Field(..., decimal_places=2)
