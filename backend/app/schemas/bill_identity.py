"""Change patient name (master) and/or consulting doctor on an existing OPD/IPD bill."""

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class BillIdentityLookupRead(ORMModel):
    bill_type: str
    bill_id: str
    bill_no: str
    bill_date: str | None = None
    patient_id: str
    patient_no: str
    title: str | None = None
    first_name: str
    middle_name: str | None = None
    last_name: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
    net_amount: float | None = None


class BillIdentityUpdate(BaseModel):
    bill_type: str = Field(..., pattern="^(OPD|IPD)$")
    bill_no: str = Field(..., min_length=1, max_length=50)
    title: str | None = Field(None, max_length=10)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    doctor_id: str | None = None
    update_patient_name: bool = False
    update_doctor: bool = False
