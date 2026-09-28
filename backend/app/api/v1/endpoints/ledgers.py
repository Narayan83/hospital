from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.ledger import LedgerCreate, LedgerRead, LedgerUpdate
from app.services.ledger import LedgerService

router = APIRouter()


@router.get("", response_model=list[LedgerRead])
async def list_ledgers(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LedgerService(session).list_ledgers()


@router.get("/{ledger_id}", response_model=LedgerRead)
async def get_ledger(
    ledger_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LedgerService(session).get_ledger(ledger_id)


@router.post("", response_model=LedgerRead, status_code=201)
async def create_ledger(
    data: LedgerCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LedgerService(session).create_ledger(data)


@router.patch("/{ledger_id}", response_model=LedgerRead)
async def update_ledger(
    ledger_id: str,
    data: LedgerUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LedgerService(session).update_ledger(ledger_id, data)


@router.delete("/{ledger_id}", response_model=LedgerRead)
async def delete_ledger(
    ledger_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LedgerService(session).delete_ledger(ledger_id)
