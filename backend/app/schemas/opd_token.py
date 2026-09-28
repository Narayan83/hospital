from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class OpdTokenRead(ORMModel):
    id: str
    doctor_id: str
    doctor_name: str | None = None
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    bill_id: str | None
    bill_no: str | None = None
    token_number: int
    token_date: date
    token_session: str
    visit_category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OpdTokenListQuery(BaseModel):
    doctor_id: str | None = None
    token_date: date | None = None
    token_session: str | None = None
    visit_category: str | None = None
