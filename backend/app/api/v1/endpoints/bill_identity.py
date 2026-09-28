from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.bill_identity import BillIdentityLookupRead, BillIdentityUpdate
from app.services.bill_identity import BillIdentityService

router = APIRouter()


@router.get("/lookup", response_model=BillIdentityLookupRead)
async def lookup_bill_identity(
    bill_type: str = Query(..., pattern="^(OPD|IPD|opd|ipd)$"),
    bill_no: str = Query(..., min_length=1, max_length=50),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillIdentityService(session).lookup(
        bill_type=bill_type.upper(),
        bill_no=bill_no,
    )


@router.post("", response_model=BillIdentityLookupRead)
async def update_bill_identity(
    data: BillIdentityUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillIdentityService(session).update(data)
