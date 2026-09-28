from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyOrder(Base, TimestampMixin):
    __tablename__ = "pathology_orders"
    __table_args__ = (UniqueConstraint("bill_id", name="uq_pathology_order_per_bill"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_bills.id"), nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    sample_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="billed")
    pathologist_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bill: Mapped["PathologyBill"] = relationship("PathologyBill", back_populates="order")
    patient: Mapped["Patient"] = relationship("Patient")
    pathologist: Mapped["Doctor | None"] = relationship("Doctor")
    results: Mapped[list["PathologyResult"]] = relationship(
        "PathologyResult",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PathologyResult.sort_order",
    )


class PathologyResult(Base, TimestampMixin):
    __tablename__ = "pathology_results"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bill_line_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_bill_lines.id"), nullable=True, index=True
    )
    parameter_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_parameters.id"), nullable=False, index=True
    )
    service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=True
    )
    result_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result_numeric: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_units.id"), nullable=True
    )
    reference_range_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    order: Mapped["PathologyOrder"] = relationship("PathologyOrder", back_populates="results")
    parameter: Mapped["PathologyParameter"] = relationship("PathologyParameter")
    unit: Mapped["PathologyUnit | None"] = relationship("PathologyUnit")
    bill_line: Mapped["PathologyBillLine | None"] = relationship("PathologyBillLine")
    service: Mapped["PatientServiceMaster | None"] = relationship("PatientServiceMaster")
