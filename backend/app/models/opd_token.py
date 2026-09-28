from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class OpdToken(Base, TimestampMixin):
    __tablename__ = "opd_tokens"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "token_date",
            "token_session",
            "visit_category",
            "token_number",
            name="uq_opd_token_slot",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    doctor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    bill_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("opd_bills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    token_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    token_session: Mapped[str] = mapped_column(String(10), nullable=False)
    visit_category: Mapped[str] = mapped_column(String(20), nullable=False)
    bill_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    doctor: Mapped["Doctor"] = relationship("Doctor")
    patient: Mapped["Patient"] = relationship("Patient")
    bill: Mapped["OpdBill | None"] = relationship("OpdBill", back_populates="token")
