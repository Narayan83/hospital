from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field

from app.schemas.common import ORMModel


def _calc_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return max(years, 0)


class DoctorBase(BaseModel):
    title: str | None = Field(None, max_length=20)
    first_name: str = Field(..., min_length=1, max_length=100)
    second_name: str | None = Field(None, max_length=100)
    third_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = Field(None, max_length=10)
    perm_village: str | None = Field(None, max_length=150)
    perm_post: str | None = Field(None, max_length=150)
    perm_taluk: str | None = Field(None, max_length=150)
    perm_district: str | None = Field(None, max_length=150)
    perm_pincode: str | None = Field(None, max_length=20)
    temp_village: str | None = Field(None, max_length=150)
    temp_post: str | None = Field(None, max_length=150)
    temp_taluk: str | None = Field(None, max_length=150)
    temp_district: str | None = Field(None, max_length=150)
    temp_pincode: str | None = Field(None, max_length=20)
    is_reference_doctor: bool = False
    remarks: str | None = None
    phone: str | None = Field(None, max_length=20)
    mobile: str | None = Field(None, max_length=20)
    mobile2: str | None = Field(None, max_length=20)
    join_date: date | None = None
    qualification: str | None = Field(None, max_length=255)
    department_id: str | None = None
    is_existing: bool = True
    release_date: date | None = None
    register_no: str | None = Field(None, max_length=80)
    morning_token_start: int = 0
    evening_token_start: int = 0
    appointment_token_start: int = Field(default=1, ge=1)
    appointment_token_end: int = Field(default=5, ge=1)
    online_booking_token_start: int = Field(default=1, ge=1)
    online_booking_token_end: int = Field(default=10, ge=1)
    is_pathology_doctor: bool = False
    email: str | None = Field(None, max_length=255)
    specialization: str | None = Field(None, max_length=150)


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    title: str | None = Field(None, max_length=20)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    second_name: str | None = Field(None, max_length=100)
    third_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = Field(None, max_length=10)
    perm_village: str | None = Field(None, max_length=150)
    perm_post: str | None = Field(None, max_length=150)
    perm_taluk: str | None = Field(None, max_length=150)
    perm_district: str | None = Field(None, max_length=150)
    perm_pincode: str | None = Field(None, max_length=20)
    temp_village: str | None = Field(None, max_length=150)
    temp_post: str | None = Field(None, max_length=150)
    temp_taluk: str | None = Field(None, max_length=150)
    temp_district: str | None = Field(None, max_length=150)
    temp_pincode: str | None = Field(None, max_length=20)
    is_reference_doctor: bool | None = None
    remarks: str | None = None
    phone: str | None = Field(None, max_length=20)
    mobile: str | None = Field(None, max_length=20)
    mobile2: str | None = Field(None, max_length=20)
    join_date: date | None = None
    qualification: str | None = Field(None, max_length=255)
    department_id: str | None = None
    is_existing: bool | None = None
    release_date: date | None = None
    register_no: str | None = Field(None, max_length=80)
    morning_token_start: int | None = None
    evening_token_start: int | None = None
    appointment_token_start: int | None = Field(None, ge=1)
    appointment_token_end: int | None = Field(None, ge=1)
    online_booking_token_start: int | None = Field(None, ge=1)
    online_booking_token_end: int | None = Field(None, ge=1)
    is_pathology_doctor: bool | None = None
    email: str | None = Field(None, max_length=255)
    specialization: str | None = Field(None, max_length=150)
    is_active: bool | None = None


class DoctorRead(DoctorBase, ORMModel):
    id: str
    doctor_code: str
    photo_path: str | None = None
    certificate_path: str | None = None
    department_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def age(self) -> int | None:
        return _calc_age(self.date_of_birth)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.second_name, self.third_name) if p]
        name = " ".join(parts)
        if self.title:
            return f"{self.title} {name}".strip()
        return name
