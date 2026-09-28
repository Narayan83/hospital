from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class HospitalProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    pathology_name: str | None = Field(None, max_length=200)
    medical_shop_name: str | None = Field(None, max_length=200)
    address_line1: str | None = Field(None, max_length=200)
    address_line2: str | None = Field(None, max_length=200)
    address_line3: str | None = Field(None, max_length=200)
    address_line4: str | None = Field(None, max_length=200)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    pin_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=30)
    mobile: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=255)
    gstin: str | None = Field(None, max_length=20)
    software_id: str | None = Field(None, max_length=50)


class HospitalProfileUpdate(HospitalProfileBase):
    pass


class HospitalProfileRead(HospitalProfileBase, ORMModel):
    id: str
    code: str
    created_at: datetime
    updated_at: datetime
