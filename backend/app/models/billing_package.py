from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class BillingPackage(Base, TimestampMixin):
    __tablename__ = "billing_packages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    items: Mapped[list["BillingPackageItem"]] = relationship(
        "BillingPackageItem",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="BillingPackageItem.sort_order",
    )


class BillingPackageItem(Base, TimestampMixin):
    __tablename__ = "billing_package_items"
    __table_args__ = (
        UniqueConstraint("package_id", "service_id", name="uq_package_service"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    package_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("billing_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patient_service_masters.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    rate_override: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    package: Mapped["BillingPackage"] = relationship("BillingPackage", back_populates="items")
    service: Mapped["PatientServiceMaster"] = relationship("PatientServiceMaster")
