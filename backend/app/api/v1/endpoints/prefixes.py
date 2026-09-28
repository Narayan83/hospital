from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.prefix import PrefixCreate, PrefixRead, PrefixUpdate
from app.services.prefix import PrefixService

router = APIRouter()


@router.get("", response_model=list[PrefixRead])
async def list_prefixes(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrefixService(session).list_prefixes()


@router.get("/{prefix_id}", response_model=PrefixRead)
async def get_prefix(
    prefix_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrefixService(session).get_prefix(prefix_id)


@router.post("", response_model=PrefixRead, status_code=201)
async def create_prefix(
    data: PrefixCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrefixService(session).create_prefix(data)


@router.patch("/{prefix_id}", response_model=PrefixRead)
async def update_prefix(
    prefix_id: str,
    data: PrefixUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrefixService(session).update_prefix(prefix_id, data)


@router.delete("/{prefix_id}", response_model=PrefixRead)
async def delete_prefix(
    prefix_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrefixService(session).delete_prefix(prefix_id)
