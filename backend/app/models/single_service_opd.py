from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class SingleServiceOpdOption(Base, TimestampMixin):
    """Setup row. Each active option becomes a menu under Transactions → Billing."""

    __tablename__ = "single_service_opd_options"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    menu_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    service_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=False
    )
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    use_patient_id: Mapped[bool] = mapped_column(Boolean, default=True)
    default_rate: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    bill_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    service: Mapped["PatientServiceMaster"] = relationship("PatientServiceMaster")


class SingleServiceOpdBill(Base, TimestampMixin):
    """One-service OPD bill. Number series is separate and restarts each financial year."""

    __tablename__ = "single_service_opd_bills"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    bill_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    option_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("single_service_opd_options.id"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=True, index=True
    )
    patient_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    doctor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=False, index=True
    )
    service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=True
    )
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_mode_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("payment_modes.id"), nullable=True
    )
    payment_mode_name: Mapped[str] = mapped_column(String(150), default="Cash")
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    option: Mapped["SingleServiceOpdOption"] = relationship("SingleServiceOpdOption")
    patient: Mapped["Patient | None"] = relationship("Patient")
    doctor: Mapped["Doctor"] = relationship("Doctor")
