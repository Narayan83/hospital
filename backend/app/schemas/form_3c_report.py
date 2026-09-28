from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Form3CReportRow(BaseModel):
    serial_no: int
    bill_date: date
    bill_no: str
    payment_mode: str
    patient_name: str
    service_name: str
    total_amount: Decimal = Field(..., decimal_places=2)


class Form3CReportRead(BaseModel):
    billing_type_id: str
    billing_type_code: str
    billing_type_name: str
    from_date: date
    to_date: date
    rows: list[Form3CReportRow]
    grand_total: Decimal = Field(..., decimal_places=2)
