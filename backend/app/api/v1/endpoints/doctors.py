from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorUpdate
from app.services.doctor import DoctorService
from app.services.doctor_files import resolve_doctor_file

router = APIRouter()


@router.get("", response_model=PaginatedResponse[DoctorRead])
async def list_doctors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).list_doctors(page=page, page_size=page_size, search=search)


@router.get("/{doctor_id}", response_model=DoctorRead)
async def get_doctor(
    doctor_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).get_doctor(doctor_id)


@router.post("", response_model=DoctorRead, status_code=201)
async def create_doctor(
    data: DoctorCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).create_doctor(data)


@router.patch("/{doctor_id}", response_model=DoctorRead)
async def update_doctor(
    doctor_id: str,
    data: DoctorUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).update_doctor(doctor_id, data)


@router.delete("/{doctor_id}", response_model=DoctorRead)
async def delete_doctor(
    doctor_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).delete_doctor(doctor_id)


@router.post("/{doctor_id}/photo", response_model=DoctorRead)
async def upload_doctor_photo(
    doctor_id: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).upload_photo(doctor_id, file)


@router.post("/{doctor_id}/certificate", response_model=DoctorRead)
async def upload_doctor_certificate(
    doctor_id: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorService(session).upload_certificate(doctor_id, file)


@router.get("/{doctor_id}/photo")
async def get_doctor_photo(
    doctor_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doctor = await DoctorService(session).get_doctor(doctor_id)
    file_path = resolve_doctor_file(doctor.photo_path)
    if not file_path:
        return {"detail": "Photo not found"}
    return FileResponse(file_path)


@router.get("/{doctor_id}/certificate")
async def get_doctor_certificate(
    doctor_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doctor = await DoctorService(session).get_doctor(doctor_id)
    file_path = resolve_doctor_file(doctor.certificate_path)
    if not file_path:
        return {"detail": "Certificate not found"}
    return FileResponse(file_path, filename=Path(doctor.certificate_path or "certificate").name)
