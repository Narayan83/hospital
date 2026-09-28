from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class NotificationSetup(Base, TimestampMixin):
    __tablename__ = "notification_setups"
    __table_args__ = (UniqueConstraint("event_code", "user_id", name="uq_notification_user"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    event_code: Mapped[str] = mapped_column(String(80), index=True)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
