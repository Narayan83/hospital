from datetime import date



from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_current_user, get_session

from app.models.user import User

from app.schemas.common import BillCancelRequest

from app.schemas.ipd_discharge import IpdDischargeCreate, IpdDischargeRead, IpdDischargeSummaryRead, IpdDischargeUpdate

from app.schemas.opd_bill import BillingServiceCatalogItem

from app.services.ipd_discharge import IpdDischargeService



router = APIRouter()





@router.get("/catalog/services", response_model=list[BillingServiceCatalogItem])

async def list_billing_services(

    category_id: str | None = Query(None),

    sub_category_id: str | None = Query(None),

    search: str | None = Query(None, max_length=100),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await IpdDischargeService(session).list_catalog(

        category_id=category_id,

        sub_category_id=sub_category_id,

        search=search,

    )





@router.post("", response_model=IpdDischargeRead, status_code=201)

async def create_ipd_discharge(

    data: IpdDischargeCreate,

    current_user: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await IpdDischargeService(session).discharge(data, entered_by_user_id=current_user.id)


@router.get("/by-patient", response_model=list[IpdDischargeSummaryRead])
async def list_ipd_discharges_by_patient(
    patient_id: str | None = Query(None),
    patient_no: str | None = Query(None, max_length=50),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeService(session).list_discharges_by_patient(
        patient_id=patient_id,
        patient_no=patient_no,
    )


@router.get("/{bill_id}", response_model=IpdDischargeRead)

async def get_ipd_discharge(

    bill_id: str,

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await IpdDischargeService(session).get_discharge(bill_id)





@router.get("/by-no/{bill_no}", response_model=IpdDischargeRead)

async def get_ipd_discharge_by_no(

    bill_no: str,

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await IpdDischargeService(session).get_discharge_by_no(bill_no)


@router.put("/{bill_id}", response_model=IpdDischargeRead)
async def update_ipd_discharge(
    bill_id: str,
    data: IpdDischargeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeService(session).update_discharge(
        bill_id, data, entered_by_user_id=current_user.id
    )


@router.post("/{bill_id}/cancel", response_model=IpdDischargeRead)
async def cancel_ipd_discharge(
    bill_id: str,
    data: BillCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeService(session).cancel_bill(
        bill_id, reason=data.reason, cancelled_by_user_id=current_user.id
    )

