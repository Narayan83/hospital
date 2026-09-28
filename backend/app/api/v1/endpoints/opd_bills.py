from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.common import BillCancelRequest
from app.schemas.opd_bill import BillingServiceCatalogItem, OpdBillCreate, OpdBillRead, OpdBillSummaryRead, OpdBillUpdate
from app.schemas.opd_token import OpdTokenRead
from app.services.opd_bill import OpdBillService
from app.services.opd_token import OpdTokenService

router = APIRouter()


@router.get("/catalog/services", response_model=list[BillingServiceCatalogItem])
async def list_billing_services(
    category_id: str | None = Query(None),
    sub_category_id: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).list_catalog(
        category_id=category_id,
        sub_category_id=sub_category_id,
        search=search,
    )


@router.get("/tokens", response_model=list[OpdTokenRead])
async def list_opd_tokens(
    doctor_id: str | None = Query(None),
    token_date: date | None = Query(None),
    token_session: str | None = Query(None, pattern="^(morning|evening)$"),
    visit_category: str | None = Query(None, pattern="^(opd|reference|appointment|online_booking)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    effective_doctor_id = doctor_id
    if current_user.user_type and current_user.user_type.maps_to_doctor:
        if not current_user.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor login is not linked to a doctor profile",
            )
        if doctor_id and doctor_id != current_user.doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view another doctor's tokens",
            )
        effective_doctor_id = current_user.doctor_id

    return await OpdTokenService(session).list_tokens(
        doctor_id=effective_doctor_id,
        token_date=token_date,
        token_session=token_session,
        visit_category=visit_category,
    )


@router.post("", response_model=OpdBillRead, status_code=201)
async def create_opd_bill(
    data: OpdBillCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).create_bill(data, entered_by_user_id=current_user.id)


@router.get("/by-patient", response_model=list[OpdBillSummaryRead])
async def list_opd_bills_by_patient(
    patient_id: str | None = Query(None),
    patient_no: str | None = Query(None, max_length=50),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).list_bills_by_patient(
        patient_id=patient_id,
        patient_no=patient_no,
    )


@router.get("/{bill_id}", response_model=OpdBillRead)
async def get_opd_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).get_bill(bill_id)


@router.get("/by-no/{bill_no}", response_model=OpdBillRead)
async def get_opd_bill_by_no(
    bill_no: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).get_bill_by_no(bill_no)


@router.put("/{bill_id}", response_model=OpdBillRead)
async def update_opd_bill(
    bill_id: str,
    data: OpdBillUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).update_bill(
        bill_id, data, entered_by_user_id=current_user.id
    )


@router.post("/{bill_id}/cancel", response_model=OpdBillRead)
async def cancel_opd_bill(
    bill_id: str,
    data: BillCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await OpdBillService(session).cancel_bill(
        bill_id, reason=data.reason, cancelled_by_user_id=current_user.id
    )
