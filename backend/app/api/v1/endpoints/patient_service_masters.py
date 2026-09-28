from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.patient_service_master import (
    PatientServiceMasterCreate,
    PatientServiceMasterRead,
    PatientServiceMasterUpdate,
)
from app.services.patient_service_master import PatientServiceMasterService

router = APIRouter()


@router.get("", response_model=list[PatientServiceMasterRead])
async def list_patient_services(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientServiceMasterService(session).list_services()


@router.get("/{service_id}", response_model=PatientServiceMasterRead)
async def get_patient_service(
    service_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientServiceMasterService(session).get_service(service_id)


@router.post("", response_model=PatientServiceMasterRead, status_code=201)
async def create_patient_service(
    data: PatientServiceMasterCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientServiceMasterService(session).create_service(data)


@router.patch("/{service_id}", response_model=PatientServiceMasterRead)
async def update_patient_service(
    service_id: str,
    data: PatientServiceMasterUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientServiceMasterService(session).update_service(service_id, data)


@router.delete("/{service_id}", response_model=PatientServiceMasterRead)
async def delete_patient_service(
    service_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PatientServiceMasterService(session).delete_service(service_id)
