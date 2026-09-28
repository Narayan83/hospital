from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_type_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_types.id"),
        nullable=True,
    )
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("doctors.id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_type: Mapped["UserType | None"] = relationship("UserType")
    doctor: Mapped["Doctor | None"] = relationship("Doctor")
    role_mappings: Mapped[list["UserRoleMapping"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
