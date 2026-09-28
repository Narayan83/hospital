from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.patient_document import PatientDocumentCreate, PatientDocumentRead, PatientDocumentViewRead
from app.services.patient_document import PatientDocumentService
from app.services.patient_document_files import resolve_patient_document_file

router = APIRouter()


def _effective_doctor_id(user: User, doctor_id: str | None) -> str | None:
    if user.user_type and user.user_type.maps_to_doctor:
        return user.doctor_id
    return doctor_id


@router.get("", response_model=list[PatientDocumentRead])
async def list_patient_documents(
    patient_id: str = Query(...),
    doctor_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    effective_doctor = _effective_doctor_id(current_user, doctor_id)
    if current_user.user_type and current_user.user_type.maps_to_doctor and not effective_doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor login is not linked to a doctor profile",
        )
    return await PatientDocumentService(session).list_documents(
        patient_id=patient_id,
        doctor_id=effective_doctor,
    )


@router.post("", response_model=PatientDocumentRead, status_code=201)
async def upload_patient_document(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
    document_date: str | None = Form(None),
    scanner_name: str | None = Form(None),
    remarks: str | None = Form(None),
    page_count: int = Form(1),
    original_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from datetime import date as date_type

    parsed_date = None
    if document_date:
        parsed_date = date_type.fromisoformat(document_date)

    data = PatientDocumentCreate(
        patient_id=patient_id,
        document_date=parsed_date,
        scanner_name=scanner_name,
        remarks=remarks,
        page_count=page_count,
        original_name=original_name,
    )
    return await PatientDocumentService(session).upload_document(
        data=data,
        upload=file,
        user=current_user,
    )


@router.get("/{document_id}", response_model=PatientDocumentRead)
async def get_patient_document(
    document_id: str,
    doctor_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    effective_doctor = _effective_doctor_id(current_user, doctor_id)
    return await PatientDocumentService(session).get_document(
        document_id,
        doctor_id=effective_doctor,
    )


@router.get("/{document_id}/file")
async def download_patient_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc = await PatientDocumentService(session).get_document(document_id)
    file_path = resolve_patient_document_file(doc.file_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found on disk ({doc.original_name or doc.file_path})",
        )
    filename = doc.original_name or Path(doc.file_path).name
    if not filename.lower().endswith(".pdf"):
        filename = f"{Path(filename).stem}.pdf"
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


@router.post("/{document_id}/view", response_model=PatientDocumentViewRead)
async def mark_patient_document_viewed(
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not current_user.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only doctor users can mark documents as viewed",
        )
    return await PatientDocumentService(session).mark_viewed(
        document_id,
        doctor_id=current_user.doctor_id,
    )
