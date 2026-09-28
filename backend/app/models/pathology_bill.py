from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyBill(Base, TimestampMixin):
    __tablename__ = "pathology_bills"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    referring_doctor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_mode_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("payment_modes.id"), nullable=True
    )
    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True
    )
    is_cash: Mapped[bool] = mapped_column(Boolean, default=True)
    scheme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admin_charges: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    scheme_discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    adjust_advance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gross_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="saved")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True
    )

    patient: Mapped["Patient"] = relationship("Patient")
    doctor: Mapped["Doctor | None"] = relationship("Doctor")
    payment_mode: Mapped["PaymentMode | None"] = relationship("PaymentMode")
    department: Mapped["Department | None"] = relationship("Department")
    lines: Mapped[list["PathologyBillLine"]] = relationship(
        "PathologyBillLine", back_populates="bill", cascade="all, delete-orphan"
    )
    order: Mapped["PathologyOrder | None"] = relationship(
        "PathologyOrder", back_populates="bill", uselist=False
    )


class PathologyBillLine(Base, TimestampMixin):
    __tablename__ = "pathology_bill_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pathology_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=True
    )
    service_code: Mapped[str] = mapped_column(String(30), nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sub_category_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    line_source: Mapped[str] = mapped_column(String(20), default="manual")
    package_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("billing_packages.id"), nullable=True
    )
    panel_service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=True
    )
    panel_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_panel_parent: Mapped[bool] = mapped_column(Boolean, default=False)
    reference_range_text: Mapped[str | None] = mapped_column(String(250), nullable=True)
    result_value: Mapped[str | None] = mapped_column(String(250), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bill: Mapped["PathologyBill"] = relationship("PathologyBill", back_populates="lines")
    service: Mapped["PatientServiceMaster | None"] = relationship(
        "PatientServiceMaster",
        foreign_keys=[service_id],
    )
    panel_service: Mapped["PatientServiceMaster | None"] = relationship(
        "PatientServiceMaster",
        foreign_keys=[panel_service_id],
    )
