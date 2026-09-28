from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyServiceMember(Base, TimestampMixin):
    """A bundle/package service that contains other billable services.

    Unlike ``PathologyServiceParameter`` (service -> analyte/component), this is a
    service -> service link, so a bundle can contain plain tests *and* other
    bundles (nested), expanded recursively at billing time.
    """

    __tablename__ = "pathology_service_members"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    bundle_service_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patient_service_masters.id"),
        nullable=False,
        index=True,
    )
    member_service_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patient_service_masters.id"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bundle: Mapped["PatientServiceMaster"] = relationship(
        "PatientServiceMaster", foreign_keys=[bundle_service_id]
    )
    member: Mapped["PatientServiceMaster"] = relationship(
        "PatientServiceMaster", foreign_keys=[member_service_id]
    )
