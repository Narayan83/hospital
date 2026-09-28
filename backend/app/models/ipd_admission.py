from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class IpdAdmission(Base, TimestampMixin):
    __tablename__ = "ipd_admissions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    admission_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    ward_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("wards.id"), nullable=True
    )
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True
    )
    bed_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    advance_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    diagnosis: Mapped[str | None] = mapped_column(String(250), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="admitted")
    discharge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship("Patient")
    ward: Mapped["Ward | None"] = relationship("Ward")
    doctor: Mapped["Doctor | None"] = relationship("Doctor")
    department: Mapped["Department | None"] = relationship("Department")
    discharge_bill: Mapped["IpdBill | None"] = relationship(
        "IpdBill",
        uselist=False,
        primaryjoin="and_(IpdAdmission.id==IpdBill.admission_id, IpdBill.is_active.is_(True))",
        foreign_keys="[IpdBill.admission_id]",
        viewonly=True,
    )
