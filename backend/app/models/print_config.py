from uuid import uuid4

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class PrintConfig(Base, TimestampMixin):
    """Per-report printer and paper settings (configured in Print Master)."""

    __tablename__ = "print_configs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    printer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    paper_size: Mapped[str] = mapped_column(String(20), nullable=False, default="A4")
    custom_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    orientation: Mapped[str] = mapped_column(String(20), nullable=False, default="portrait")
    print_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="preview")
    margin_top_mm: Mapped[float] = mapped_column(Float, nullable=False, default=12.0)
    margin_right_mm: Mapped[float] = mapped_column(Float, nullable=False, default=12.0)
    margin_bottom_mm: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    margin_left_mm: Mapped[float] = mapped_column(Float, nullable=False, default=12.0)
    copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    layout_options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
