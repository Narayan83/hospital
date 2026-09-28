from datetime import date



from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.deps import get_current_user, get_session

from app.models.user import User

from app.schemas.accounting_voucher import (
    AccountingVoucherRead,
    AdvanceCollectionCreate,
    AdvanceCollectionRead,
    AdvanceCollectionUpdate,
    ContraEntryCreate,
    PatientDepositBalanceRead,
    PaymentVoucherCreate,
)

from app.schemas.cashbook import CashbookDaybookRead, CashbookLedgerStatementRead, CashbookPatientAccountRead

from app.services.accounting_voucher import AccountingVoucherService

from app.services.cashbook import CashbookService



router = APIRouter()





@router.get("/ledger/{ledger_id}", response_model=CashbookLedgerStatementRead)

async def ledger_statement(

    ledger_id: str,

    from_date: date | None = Query(None),

    to_date: date | None = Query(None),

    limit: int = Query(500, ge=1, le=2000),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await CashbookService(session).ledger_statement(

        ledger_id,

        from_date=from_date,

        to_date=to_date,

        limit=limit,

    )





@router.get("/patient-account", response_model=CashbookPatientAccountRead)

async def patient_account(

    patient_id: str | None = Query(None),

    patient_no: str | None = Query(None),

    from_date: date | None = Query(None),

    to_date: date | None = Query(None),

    limit: int = Query(500, ge=1, le=2000),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await CashbookService(session).patient_account(

        patient_id=patient_id,

        patient_no=patient_no,

        from_date=from_date,

        to_date=to_date,

        limit=limit,

    )





@router.get("/patient-deposit", response_model=PatientDepositBalanceRead)

async def patient_deposit_balance(

    patient_id: str | None = Query(None),

    patient_no: str | None = Query(None),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await AccountingVoucherService(session).patient_deposit_balance(

        patient_id=patient_id,

        patient_no=patient_no,

    )





@router.get("/daybook", response_model=CashbookDaybookRead)

async def daybook(

    from_date: date | None = Query(None),

    to_date: date | None = Query(None),

    limit: int = Query(2000, ge=1, le=5000),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await CashbookService(session).daybook(

        from_date=from_date,

        to_date=to_date,

        limit=limit,

    )





@router.get("/cash-book", response_model=CashbookDaybookRead)

async def cash_book(

    from_date: date | None = Query(None),

    to_date: date | None = Query(None),

    limit: int = Query(2000, ge=1, le=5000),

    _: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await CashbookService(session).cash_book(

        from_date=from_date,

        to_date=to_date,

        limit=limit,

    )





@router.post("/advance", response_model=AdvanceCollectionRead, status_code=201)
async def collect_advance(
    data: AdvanceCollectionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AccountingVoucherService(session).collect_advance(
        data, created_by_user_id=current_user.id
    )


@router.get("/advance", response_model=list[AdvanceCollectionRead])
async def list_advances(
    patient_id: str | None = Query(None),
    patient_no: str | None = Query(None),
    voucher_no: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AccountingVoucherService(session).list_advances(
        patient_id=patient_id,
        patient_no=patient_no,
        voucher_no=voucher_no,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )


@router.get("/advance/by-no/{voucher_no}", response_model=AdvanceCollectionRead)
async def get_advance_by_no(
    voucher_no: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AccountingVoucherService(session).get_advance_by_no(voucher_no)


@router.get("/advance/{voucher_id}", response_model=AdvanceCollectionRead)
async def get_advance(
    voucher_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AccountingVoucherService(session).get_advance(voucher_id)


@router.patch("/advance/{voucher_id}", response_model=AdvanceCollectionRead)
async def update_advance(
    voucher_id: str,
    data: AdvanceCollectionUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await AccountingVoucherService(session).update_advance(
        voucher_id, data, created_by_user_id=current_user.id
    )


@router.delete("/advance/{voucher_id}", status_code=204)
async def delete_advance(
    voucher_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await AccountingVoucherService(session).delete_advance(voucher_id)


@router.post("/payment", response_model=AccountingVoucherRead, status_code=201)

async def create_payment_voucher(

    data: PaymentVoucherCreate,

    current_user: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await AccountingVoucherService(session).create_payment_voucher(
        data, created_by_user_id=current_user.id
    )





@router.post("/contra", response_model=AccountingVoucherRead, status_code=201)

async def create_contra_entry(

    data: ContraEntryCreate,

    current_user: User = Depends(get_current_user),

    session: AsyncSession = Depends(get_session),

):

    return await AccountingVoucherService(session).create_contra_entry(
        data, created_by_user_id=current_user.id
    )


