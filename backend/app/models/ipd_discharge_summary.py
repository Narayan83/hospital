from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class IpdDischargeSummary(Base, TimestampMixin):
    __tablename__ = "ipd_discharge_summaries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    summary_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)
    discharge_date: Mapped[date] = mapped_column(Date, nullable=False)
    admission_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ipd_admissions.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    history_of_illness: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis_on_admission: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_diagnosis: Mapped[str | None] = mapped_column(String(500), nullable=True)
    investigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_given: Mapped[str | None] = mapped_column(Text, nullable=True)
    procedures: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_on_discharge: Mapped[str | None] = mapped_column(String(100), nullable=True)
    medications_on_discharge: Mapped[str | None] = mapped_column(Text, nullable=True)
    advice_follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_admission_details: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    admission: Mapped["IpdAdmission"] = relationship("IpdAdmission")
    patient: Mapped["Patient"] = relationship("Patient")
    doctor: Mapped["Doctor | None"] = relationship("Doctor")
