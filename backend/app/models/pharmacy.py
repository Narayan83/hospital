from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PharmacyCodeMaster(Base, TimestampMixin):
    __tablename__ = "pharmacy_code_masters"
    __table_args__ = (UniqueConstraint("master_type", "code", name="uq_pharmacy_code_masters_type_code"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    master_type: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PharmacyItem(Base, TimestampMixin):
    __tablename__ = "pharmacy_items"
    __table_args__ = (UniqueConstraint("item_type", "code", name="uq_pharmacy_items_type_code"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    item_type: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    manufacturer_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_code_masters.id"),
        nullable=True,
    )
    category_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_code_masters.id"),
        nullable=True,
    )
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reorder_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PharmacySupplier(Base, TimestampMixin):
    __tablename__ = "pharmacy_suppliers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PharmacyGroupMapping(Base, TimestampMixin):
    __tablename__ = "pharmacy_group_mappings"
    __table_args__ = (UniqueConstraint("group_id", "item_id", name="uq_pharmacy_group_mappings"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    group_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_code_masters.id"),
        index=True,
    )
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_items.id"),
        index=True,
    )


class PharmacySaleBill(Base, TimestampMixin):
    __tablename__ = "pharmacy_sale_bills"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    patient_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=True, index=True
    )
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_mode_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("payment_modes.id"), nullable=True
    )
    is_cash: Mapped[bool] = mapped_column(Boolean, default=True)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    round_off: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    doctor_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    scheme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address3: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="saved")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    lines: Mapped[list["PharmacySaleBillLine"]] = relationship(
        "PharmacySaleBillLine", back_populates="bill", cascade="all, delete-orphan"
    )


class PharmacySaleBillLine(Base, TimestampMixin):
    __tablename__ = "pharmacy_sale_bill_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_sale_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pharmacy_items.id"), nullable=False
    )
    item_code: Mapped[str] = mapped_column(String(30), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nos: Mapped[int] = mapped_column(Integer, default=1)
    factor: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    batch_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    line_discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    line_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    user1: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    bill: Mapped["PharmacySaleBill"] = relationship("PharmacySaleBill", back_populates="lines")


class PharmacyPurchaseBill(Base, TimestampMixin):
    __tablename__ = "pharmacy_purchase_bills"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pharmacy_suppliers.id"), nullable=True, index=True
    )
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="saved")
    bill_kind: Mapped[str] = mapped_column(String(20), default="purchase")  # purchase | return
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    lines: Mapped[list["PharmacyPurchaseBillLine"]] = relationship(
        "PharmacyPurchaseBillLine", back_populates="bill", cascade="all, delete-orphan"
    )


class PharmacyPurchaseBillLine(Base, TimestampMixin):
    __tablename__ = "pharmacy_purchase_bill_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pharmacy_purchase_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pharmacy_items.id"), nullable=False
    )
    item_code: Mapped[str] = mapped_column(String(30), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    bill: Mapped["PharmacyPurchaseBill"] = relationship("PharmacyPurchaseBill", back_populates="lines")
