from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.service_category import (
    ServiceCategoryCreate,
    ServiceCategoryRead,
    ServiceCategoryUpdate,
)
from app.services.service_category import ServiceCategoryService

router = APIRouter()


@router.get("", response_model=list[ServiceCategoryRead])
async def list_service_categories(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceCategoryService(session).list_categories()


@router.get("/{category_id}", response_model=ServiceCategoryRead)
async def get_service_category(
    category_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceCategoryService(session).get_category(category_id)


@router.post("", response_model=ServiceCategoryRead, status_code=201)
async def create_service_category(
    data: ServiceCategoryCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceCategoryService(session).create_category(data)


@router.patch("/{category_id}", response_model=ServiceCategoryRead)
async def update_service_category(
    category_id: str,
    data: ServiceCategoryUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceCategoryService(session).update_category(category_id, data)


@router.delete("/{category_id}", response_model=ServiceCategoryRead)
async def delete_service_category(
    category_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceCategoryService(session).delete_category(category_id)
