from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.hospital_profile import HospitalProfileRead, HospitalProfileUpdate
from app.services.hospital_profile import HospitalProfileService

router = APIRouter()


@router.get("", response_model=HospitalProfileRead)
async def get_hospital_profile(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalProfileService(session).get_profile()


@router.put("", response_model=HospitalProfileRead)
async def update_hospital_profile(
    data: HospitalProfileUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await HospitalProfileService(session).update_profile(data)
