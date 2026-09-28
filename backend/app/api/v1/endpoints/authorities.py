from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.authority import AuthorityCreate, AuthorityRead, AuthorityUpdate
from app.services.authority import AuthorityService

router = APIRouter()


@router.get("", response_model=list[AuthorityRead])
async def list_authorities(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AuthorityService(session).list_authorities()


@router.get("/{authority_id}", response_model=AuthorityRead)
async def get_authority(
    authority_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AuthorityService(session).get_authority(authority_id)


@router.post("", response_model=AuthorityRead, status_code=201)
async def create_authority(
    data: AuthorityCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AuthorityService(session).create_authority(data)


@router.patch("/{authority_id}", response_model=AuthorityRead)
async def update_authority(
    authority_id: str,
    data: AuthorityUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AuthorityService(session).update_authority(authority_id, data)


@router.delete("/{authority_id}", response_model=AuthorityRead)
async def delete_authority(
    authority_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AuthorityService(session).delete_authority(authority_id)
