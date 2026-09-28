from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.lab_test import (
    LabTestRead,
    LabTestSave,
    ProfileRead,
    ProfileSave,
)
from app.services.lab_test import LabTestService

router = APIRouter()


@router.get("/lab-tests", response_model=list[LabTestRead])
async def list_lab_tests(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).list_tests()


@router.post("/lab-tests", response_model=LabTestRead, status_code=201)
async def create_lab_test(
    data: LabTestSave,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).save_test(data)


@router.put("/lab-tests/{test_id}", response_model=LabTestRead)
async def update_lab_test(
    test_id: str,
    data: LabTestSave,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).save_test(data, test_id=test_id)


@router.delete("/lab-tests/{test_id}", status_code=204)
async def delete_lab_test(
    test_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await LabTestService(session).delete_test(test_id)


@router.get("/profiles", response_model=list[ProfileRead])
async def list_profiles(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).list_profiles()


@router.post("/profiles", response_model=ProfileRead, status_code=201)
async def create_profile(
    data: ProfileSave,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).save_profile(data)


@router.put("/profiles/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: str,
    data: ProfileSave,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LabTestService(session).save_profile(data, profile_id=profile_id)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await LabTestService(session).delete_profile(profile_id)
