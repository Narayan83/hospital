from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.payment_mode import PaymentModeCreate, PaymentModeRead, PaymentModeUpdate
from app.services.payment_mode import PaymentModeService

router = APIRouter()


@router.get("", response_model=list[PaymentModeRead])
async def list_payment_modes(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PaymentModeService(session).list_payment_modes()


@router.get("/{payment_mode_id}", response_model=PaymentModeRead)
async def get_payment_mode(
    payment_mode_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PaymentModeService(session).get_payment_mode(payment_mode_id)


@router.post("", response_model=PaymentModeRead, status_code=201)
async def create_payment_mode(
    data: PaymentModeCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PaymentModeService(session).create_payment_mode(data)


@router.patch("/{payment_mode_id}", response_model=PaymentModeRead)
async def update_payment_mode(
    payment_mode_id: str,
    data: PaymentModeUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PaymentModeService(session).update_payment_mode(payment_mode_id, data)


@router.delete("/{payment_mode_id}", response_model=PaymentModeRead)
async def delete_payment_mode(
    payment_mode_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PaymentModeService(session).delete_payment_mode(payment_mode_id)
