from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    patient_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    hospital_section_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hospital_sections.id"),
        nullable=True,
    )
    facility: Mapped[str | None] = mapped_column(String(150), nullable=True)
    title: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    village_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_address1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_address2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_address3: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_address4: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_address5: Mapped[str | None] = mapped_column(String(20), nullable=True)

    perm_address1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    perm_address2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    perm_address3: Mapped[str | None] = mapped_column(String(200), nullable=True)
    perm_address4: Mapped[str | None] = mapped_column(String(200), nullable=True)
    perm_address5: Mapped[str | None] = mapped_column(String(20), nullable=True)

    old_software_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scheme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aadhar_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhar_scan_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_existing_patient: Mapped[bool] = mapped_column(Boolean, default=False)
    patient_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(part for part in parts if part)
