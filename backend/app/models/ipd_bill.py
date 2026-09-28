from datetime import date

from uuid import uuid4



from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text, text

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import Mapped, mapped_column, relationship



from app.core.database import Base

from app.models.base import TimestampMixin





class IpdBill(Base, TimestampMixin):

    __tablename__ = "ipd_bills"

    __table_args__ = (
        Index(
            "uq_ipd_bill_per_admission_active",
            "admission_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
    )



    id: Mapped[str] = mapped_column(

        UUID(as_uuid=False),

        primary_key=True,

        default=lambda: str(uuid4()),

    )

    bill_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)

    bill_date: Mapped[date] = mapped_column(Date, nullable=False)

    admission_id: Mapped[str | None] = mapped_column(

        UUID(as_uuid=False), ForeignKey("ipd_admissions.id"), nullable=True, index=True

    )

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

    admission_date: Mapped[date] = mapped_column(Date, nullable=False)

    discharge_date: Mapped[date] = mapped_column(Date, nullable=False)

    stay_days: Mapped[int] = mapped_column(Integer, default=1)

    payment_mode_id: Mapped[str | None] = mapped_column(

        UUID(as_uuid=False), ForeignKey("payment_modes.id"), nullable=True

    )

    is_cash: Mapped[bool] = mapped_column(Boolean, default=True)

    scheme: Mapped[str | None] = mapped_column(String(100), nullable=True)

    admin_charges: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    scheme_discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    sanctioned_scheme_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    adjust_advance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    hide_advance_on_bill: Mapped[bool] = mapped_column(Boolean, default=False)

    gross_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="discharged")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True
    )



    admission: Mapped["IpdAdmission | None"] = relationship("IpdAdmission")

    patient: Mapped["Patient"] = relationship("Patient")

    ward: Mapped["Ward | None"] = relationship("Ward")

    doctor: Mapped["Doctor | None"] = relationship("Doctor")

    department: Mapped["Department | None"] = relationship("Department")

    payment_mode: Mapped["PaymentMode | None"] = relationship("PaymentMode")

    lines: Mapped[list["IpdBillLine"]] = relationship(

        "IpdBillLine", back_populates="bill", cascade="all, delete-orphan"

    )

    payments: Mapped[list["IpdBillPayment"]] = relationship(

        "IpdBillPayment", back_populates="bill", cascade="all, delete-orphan"

    )





class IpdBillPayment(Base, TimestampMixin):

    __tablename__ = "ipd_bill_payments"



    id: Mapped[str] = mapped_column(

        UUID(as_uuid=False),

        primary_key=True,

        default=lambda: str(uuid4()),

    )

    bill_id: Mapped[str] = mapped_column(

        UUID(as_uuid=False), ForeignKey("ipd_bills.id", ondelete="CASCADE"), nullable=False, index=True

    )

    payment_mode_id: Mapped[str] = mapped_column(

        UUID(as_uuid=False), ForeignKey("payment_modes.id"), nullable=False

    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)



    bill: Mapped["IpdBill"] = relationship("IpdBill", back_populates="payments")

    payment_mode: Mapped["PaymentMode"] = relationship("PaymentMode")





class IpdBillLine(Base, TimestampMixin):

    __tablename__ = "ipd_bill_lines"



    id: Mapped[str] = mapped_column(

        UUID(as_uuid=False),

        primary_key=True,

        default=lambda: str(uuid4()),

    )

    bill_id: Mapped[str] = mapped_column(

        UUID(as_uuid=False), ForeignKey("ipd_bills.id", ondelete="CASCADE"), nullable=False, index=True

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

    original_rate: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    hospital_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    doctor_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    sharing_doctor_id: Mapped[str | None] = mapped_column(

        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True, index=True

    )

    line_source: Mapped[str] = mapped_column(String(20), default="manual")

    package_id: Mapped[str | None] = mapped_column(

        UUID(as_uuid=False), ForeignKey("billing_packages.id"), nullable=True

    )

    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)



    bill: Mapped["IpdBill"] = relationship("IpdBill", back_populates="lines")

    service: Mapped["PatientServiceMaster | None"] = relationship("PatientServiceMaster")

    sharing_doctor: Mapped["Doctor | None"] = relationship("Doctor")

