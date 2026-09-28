from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.common import BillCancelRequest
from app.schemas.opd_bill import BillingServiceCatalogItem
from app.schemas.pathology_bill import (
    PathologyBillCreate,
    PathologyBillExpandLine,
    PathologyBillRead,
    PathologyBillSummaryRead,
    PathologyBillUpdate,
)
from app.services.pathology_bill import PathologyBillService

router = APIRouter()


@router.get("/expand/{service_code}", response_model=list[PathologyBillExpandLine])
async def expand_pathology_service(
    service_code: str,
    patient_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).expand_service(
        service_code, patient_id=patient_id
    )


@router.get("/catalog/services", response_model=list[BillingServiceCatalogItem])
async def list_pathology_services(
    sub_category_id: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).list_catalog(
        sub_category_id=sub_category_id,
        search=search,
    )


@router.get("", response_model=list[PathologyBillRead])
async def list_pathology_bills(
    bill_date: date | None = Query(None),
    search: str | None = Query(None, max_length=100),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).list_bills(bill_date=bill_date, search=search)


@router.post("", response_model=PathologyBillRead, status_code=201)
async def create_pathology_bill(
    data: PathologyBillCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).create_bill(data, entered_by_user_id=current_user.id)


@router.get("/by-patient", response_model=list[PathologyBillSummaryRead])
async def list_pathology_bills_by_patient(
    patient_id: str | None = Query(None),
    patient_no: str | None = Query(None, max_length=50),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).list_bills_by_patient(
        patient_id=patient_id,
        patient_no=patient_no,
    )


@router.get("/{bill_id}", response_model=PathologyBillRead)
async def get_pathology_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).get_bill(bill_id)


@router.get("/by-no/{bill_no}", response_model=PathologyBillRead)
async def get_pathology_bill_by_no(
    bill_no: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).get_bill_by_no(bill_no)


@router.put("/{bill_id}", response_model=PathologyBillRead)
async def update_pathology_bill(
    bill_id: str,
    data: PathologyBillUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).update_bill(
        bill_id, data, entered_by_user_id=current_user.id
    )


@router.post("/{bill_id}/cancel", response_model=PathologyBillRead)
async def cancel_pathology_bill(
    bill_id: str,
    data: BillCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyBillService(session).cancel_bill(
        bill_id, reason=data.reason, cancelled_by_user_id=current_user.id
    )
