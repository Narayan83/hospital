from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Menu(Base, TimestampMixin):
    __tablename__ = "menus"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("menus.id"),
        nullable=True,
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    legacy_mcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_form: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parameters: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    children: Mapped[list["Menu"]] = relationship(
        "Menu",
        back_populates="parent",
        order_by="Menu.sort_order",
    )
    parent: Mapped["Menu | None"] = relationship(
        "Menu",
        back_populates="children",
        remote_side="Menu.id",
    )
