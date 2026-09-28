from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.hospital_section import (
    HospitalSectionCreate,
    HospitalSectionRead,
    HospitalSectionUpdate,
)
from app.services.hospital_section import HospitalSectionService

router = APIRouter()


@router.get("", response_model=list[HospitalSectionRead])
async def list_hospital_sections(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalSectionService(session).list_sections()


@router.get("/{section_id}", response_model=HospitalSectionRead)
async def get_hospital_section(
    section_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalSectionService(session).get_section(section_id)


@router.post("", response_model=HospitalSectionRead, status_code=201)
async def create_hospital_section(
    data: HospitalSectionCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalSectionService(session).create_section(data)


@router.patch("/{section_id}", response_model=HospitalSectionRead)
async def update_hospital_section(
    section_id: str,
    data: HospitalSectionUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalSectionService(session).update_section(section_id, data)


@router.delete("/{section_id}", response_model=HospitalSectionRead)
async def delete_hospital_section(
    section_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalSectionService(session).delete_section(section_id)
