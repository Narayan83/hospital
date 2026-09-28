from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.short_bill import (
    ShortBillCreate,
    ShortBillRead,
    ShortBillReportRead,
    ShortBillTypeCreate,
    ShortBillTypeRead,
    ShortBillTypeUpdate,
    ShortBillUpdate,
)
from app.services.short_bill import ShortBillService

router = APIRouter()


@router.get("/types", response_model=list[ShortBillTypeRead])
async def list_short_bill_types(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).list_types()


@router.get("/types/by-menu/{menu_code}", response_model=ShortBillTypeRead)
async def get_short_bill_type_by_menu(
    menu_code: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).get_type_by_menu(menu_code)


@router.get("/types/{type_id}", response_model=ShortBillTypeRead)
async def get_short_bill_type(
    type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).get_type(type_id)


@router.post("/types", response_model=ShortBillTypeRead, status_code=201)
async def create_short_bill_type(
    data: ShortBillTypeCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).create_type(data)
    await session.commit()
    return result


@router.patch("/types/{type_id}", response_model=ShortBillTypeRead)
async def update_short_bill_type(
    type_id: str,
    data: ShortBillTypeUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).update_type(type_id, data)
    await session.commit()
    return result


@router.delete("/types/{type_id}", response_model=ShortBillTypeRead)
async def delete_short_bill_type(
    type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).delete_type(type_id)
    await session.commit()
    return result


@router.post("", response_model=ShortBillRead, status_code=201)
async def create_short_bill(
    data: ShortBillCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).create_bill(data, user_id=user.id)
    await session.commit()
    return result


@router.patch("/{bill_id}", response_model=ShortBillRead)
async def update_short_bill(
    bill_id: str,
    data: ShortBillUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).update_bill(bill_id, data)
    await session.commit()
    return result


@router.delete("/{bill_id}", response_model=ShortBillRead)
async def delete_short_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await ShortBillService(session).delete_bill(bill_id)
    await session.commit()
    return result


@router.get("/search", response_model=list[ShortBillRead])
async def search_short_bills(
    short_bill_type_id: str = Query(...),
    q: str = Query(..., min_length=1),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).search_bills(short_bill_type_id=short_bill_type_id, query=q)


@router.get("/report", response_model=ShortBillReportRead)
async def short_bill_report(
    short_bill_type_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).build_report(
        short_bill_type_id=short_bill_type_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/{bill_id}", response_model=ShortBillRead)
async def get_short_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ShortBillService(session).get_bill(bill_id)
