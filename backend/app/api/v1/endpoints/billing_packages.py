from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.billing_package import (
    BillingPackageCreate,
    BillingPackageDetailRead,
    BillingPackageItemCreate,
    BillingPackageItemsReplace,
    BillingPackageRead,
    BillingPackageUpdate,
)
from app.services.billing_package import BillingPackageService

router = APIRouter()


@router.get("", response_model=list[BillingPackageRead])
async def list_billing_packages(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).list_packages()


@router.get("/{package_id}", response_model=BillingPackageDetailRead)
async def get_billing_package(
    package_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).get_package(package_id)


@router.post("", response_model=BillingPackageRead, status_code=201)
async def create_billing_package(
    data: BillingPackageCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).create_package(data)


@router.patch("/{package_id}", response_model=BillingPackageRead)
async def update_billing_package(
    package_id: str,
    data: BillingPackageUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).update_package(package_id, data)


@router.delete("/{package_id}", response_model=BillingPackageRead)
async def delete_billing_package(
    package_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).delete_package(package_id)


@router.put("/{package_id}/items", response_model=BillingPackageDetailRead)
async def replace_billing_package_items(
    package_id: str,
    data: BillingPackageItemsReplace,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).replace_items(package_id, data)


@router.post("/{package_id}/items", response_model=BillingPackageDetailRead)
async def add_billing_package_item(
    package_id: str,
    data: BillingPackageItemCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).add_item(package_id, data)


@router.delete("/{package_id}/items/{item_id}", response_model=BillingPackageDetailRead)
async def remove_billing_package_item(
    package_id: str,
    item_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingPackageService(session).remove_item(package_id, item_id)
