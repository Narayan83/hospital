from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.single_service_opd import (
    SingleServiceOpdBillCreate,
    SingleServiceOpdBillRead,
    SingleServiceOpdOptionCreate,
    SingleServiceOpdOptionRead,
    SingleServiceOpdOptionUpdate,
)
from app.services.single_service_opd import SingleServiceOpdService

router = APIRouter()


@router.get("/options", response_model=list[SingleServiceOpdOptionRead])
async def list_options(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await SingleServiceOpdService(session).list_options()


@router.get("/options/by-menu/{menu_code}", response_model=SingleServiceOpdOptionRead)
async def get_option_by_menu(
    menu_code: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await SingleServiceOpdService(session).get_option_by_menu(menu_code)


@router.post("/options", response_model=SingleServiceOpdOptionRead, status_code=201)
async def create_option(
    data: SingleServiceOpdOptionCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await SingleServiceOpdService(session).create_option(data)
    await session.commit()
    return result


@router.patch("/options/{option_id}", response_model=SingleServiceOpdOptionRead)
async def update_option(
    option_id: str,
    data: SingleServiceOpdOptionUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await SingleServiceOpdService(session).update_option(option_id, data)
    await session.commit()
    return result


@router.get("/bills", response_model=list[SingleServiceOpdBillRead])
async def list_bills(
    option_id: str = Query(...),
    bill_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await SingleServiceOpdService(session).list_bills(option_id, bill_date)


@router.post("/bills", response_model=SingleServiceOpdBillRead, status_code=201)
async def create_bill(
    data: SingleServiceOpdBillCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await SingleServiceOpdService(session).create_bill(data, user_id=user.id)
    await session.commit()
    return result


@router.delete("/bills/{bill_id}", response_model=SingleServiceOpdBillRead)
async def cancel_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await SingleServiceOpdService(session).cancel_bill(bill_id)
    await session.commit()
    return result
