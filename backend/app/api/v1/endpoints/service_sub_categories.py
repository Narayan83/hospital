from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.service_sub_category import (
    ServiceSubCategoryCreate,
    ServiceSubCategoryRead,
    ServiceSubCategoryUpdate,
)
from app.services.service_sub_category import ServiceSubCategoryService

router = APIRouter()


@router.get("", response_model=list[ServiceSubCategoryRead])
async def list_service_sub_categories(
    category_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceSubCategoryService(session).list_sub_categories(category_id)


@router.get("/{sub_category_id}", response_model=ServiceSubCategoryRead)
async def get_service_sub_category(
    sub_category_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceSubCategoryService(session).get_sub_category(sub_category_id)


@router.post("", response_model=ServiceSubCategoryRead, status_code=201)
async def create_service_sub_category(
    data: ServiceSubCategoryCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceSubCategoryService(session).create_sub_category(data)


@router.patch("/{sub_category_id}", response_model=ServiceSubCategoryRead)
async def update_service_sub_category(
    sub_category_id: str,
    data: ServiceSubCategoryUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceSubCategoryService(session).update_sub_category(sub_category_id, data)


@router.delete("/{sub_category_id}", response_model=ServiceSubCategoryRead)
async def delete_service_sub_category(
    sub_category_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceSubCategoryService(session).delete_sub_category(sub_category_id)
