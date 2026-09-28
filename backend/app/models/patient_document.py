from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PatientDocument(Base, TimestampMixin):
    __tablename__ = "patient_documents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    patient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), default="patient_document")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    scanner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scanned_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    document_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship("Patient")
    scanned_by: Mapped["User | None"] = relationship("User")
    views: Mapped[list["PatientDocumentView"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class PatientDocumentView(Base, TimestampMixin):
    __tablename__ = "patient_document_views"
    __table_args__ = (UniqueConstraint("document_id", "doctor_id", name="uq_patient_document_view"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patient_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    doctor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=False, index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["PatientDocument"] = relationship("PatientDocument", back_populates="views")
    doctor: Mapped["Doctor"] = relationship("Doctor")
