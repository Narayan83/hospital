from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PaymentMode(Base, TimestampMixin):
    __tablename__ = "payment_modes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    ledger_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ledgers.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    ledger: Mapped["Ledger | None"] = relationship("Ledger")
