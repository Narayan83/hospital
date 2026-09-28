from uuid import uuid4

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class PatientNoFormat(Base, TimestampMixin):
    """Configurable patient number pattern for a hospital installation."""

    __tablename__ = "patient_no_formats"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    pattern: Mapped[str] = mapped_column(String(100), nullable=False)
    sample_output: Mapped[str] = mapped_column(String(50), nullable=False)
    seq_pad_width: Mapped[int] = mapped_column(Integer, default=3)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
