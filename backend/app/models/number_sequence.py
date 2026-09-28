from uuid import uuid4

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class NumberSequence(Base, TimestampMixin):
    __tablename__ = "number_sequences"
    __table_args__ = (UniqueConstraint("entity_type", "scope_key", name="uq_number_sequences_scope"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
