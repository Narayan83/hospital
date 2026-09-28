from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    doctor_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    second_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    third_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    certificate_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    perm_village: Mapped[str | None] = mapped_column(String(150), nullable=True)
    perm_post: Mapped[str | None] = mapped_column(String(150), nullable=True)
    perm_taluk: Mapped[str | None] = mapped_column(String(150), nullable=True)
    perm_district: Mapped[str | None] = mapped_column(String(150), nullable=True)
    perm_pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    temp_village: Mapped[str | None] = mapped_column(String(150), nullable=True)
    temp_post: Mapped[str | None] = mapped_column(String(150), nullable=True)
    temp_taluk: Mapped[str | None] = mapped_column(String(150), nullable=True)
    temp_district: Mapped[str | None] = mapped_column(String(150), nullable=True)
    temp_pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_reference_doctor: Mapped[bool] = mapped_column(Boolean, default=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    join_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("departments.id"),
        nullable=True,
    )
    is_existing: Mapped[bool] = mapped_column(Boolean, default=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    register_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    morning_token_start: Mapped[int] = mapped_column(Integer, default=0)
    evening_token_start: Mapped[int] = mapped_column(Integer, default=0)
    appointment_token_start: Mapped[int] = mapped_column(Integer, default=1)
    appointment_token_end: Mapped[int] = mapped_column(Integer, default=5)
    online_booking_token_start: Mapped[int] = mapped_column(Integer, default=1)
    online_booking_token_end: Mapped[int] = mapped_column(Integer, default=10)
    is_pathology_doctor: Mapped[bool] = mapped_column(Boolean, default=False)

    # legacy / optional
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped["Department | None"] = relationship("Department")

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.second_name, self.third_name) if p]
        name = " ".join(parts)
        if self.title:
            return f"{self.title} {name}".strip()
        return name
