from uuid import uuid4

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

LEDGER_TYPES = ("ASSET", "LIABILITY", "INCOME", "EXPENSE")


class Ledger(Base, TimestampMixin):
    __tablename__ = "ledgers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    ledger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSET")
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bank: Mapped[bool] = mapped_column(Boolean, default=False)
    is_patient_deposit: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
