from uuid import uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ServiceNote(Base, TimestampMixin):
    """A reusable note for the pathology report.

    ``service_code`` empty/NULL means a general note that applies to every
    service; a code ties the note to that specific service.
    """

    __tablename__ = "service_notes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    service_code: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
