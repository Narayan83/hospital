from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.patient_no_format import (
    PatientNoFormatCreate,
    PatientNoFormatRead,
    PatientNoFormatUpdate,
)
from app.services.patient_no_format import PatientNoFormatService

router = APIRouter()


@router.get("", response_model=list[PatientNoFormatRead])
async def list_patient_no_formats(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientNoFormatService(session).list_formats()


@router.get("/{format_id}", response_model=PatientNoFormatRead)
async def get_patient_no_format(
    format_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientNoFormatService(session).get_format(format_id)


@router.post("", response_model=PatientNoFormatRead, status_code=201)
async def create_patient_no_format(
    data: PatientNoFormatCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientNoFormatService(session).create_format(data)


@router.patch("/{format_id}", response_model=PatientNoFormatRead)
async def update_patient_no_format(
    format_id: str,
    data: PatientNoFormatUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientNoFormatService(session).update_format(format_id, data)


@router.delete("/{format_id}", response_model=PatientNoFormatRead)
async def delete_patient_no_format(
    format_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientNoFormatService(session).delete_format(format_id)
