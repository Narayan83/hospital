from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.billing_type import BillingTypeCreate, BillingTypeRead, BillingTypeUpdate
from app.services.billing_type import BillingTypeService

router = APIRouter()


@router.get("", response_model=list[BillingTypeRead])
async def list_billing_types(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingTypeService(session).list_billing_types()


@router.get("/{billing_type_id}", response_model=BillingTypeRead)
async def get_billing_type(
    billing_type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingTypeService(session).get_billing_type(billing_type_id)


@router.post("", response_model=BillingTypeRead, status_code=201)
async def create_billing_type(
    data: BillingTypeCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingTypeService(session).create_billing_type(data)


@router.patch("/{billing_type_id}", response_model=BillingTypeRead)
async def update_billing_type(
    billing_type_id: str,
    data: BillingTypeUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingTypeService(session).update_billing_type(billing_type_id, data)


@router.delete("/{billing_type_id}", response_model=BillingTypeRead)
async def delete_billing_type(
    billing_type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingTypeService(session).delete_billing_type(billing_type_id)
