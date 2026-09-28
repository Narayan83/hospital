from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.ipd_discharge_summary import (
    IpdDischargeSummaryCreate,
    IpdDischargeSummaryListRead,
    IpdDischargeSummaryRead,
    IpdDischargeSummaryUpdate,
)
from app.services.ipd_discharge_summary import IpdDischargeSummaryService

router = APIRouter()


@router.get("", response_model=list[IpdDischargeSummaryListRead])
async def list_discharge_summaries(
    search: str | None = Query(None, max_length=100),
    patient_id: str | None = Query(None),
    patient_no: str | None = Query(None, max_length=30),
    admission_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).list_summaries(
        search=search,
        patient_id=patient_id,
        patient_no=patient_no,
        admission_id=admission_id,
    )


@router.post("", response_model=IpdDischargeSummaryRead, status_code=201)
async def create_discharge_summary(
    data: IpdDischargeSummaryCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).create_summary(data)


@router.get("/by-admission/{admission_id}", response_model=IpdDischargeSummaryRead)
async def get_discharge_summary_by_admission(
    admission_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).get_summary_by_admission(admission_id)


@router.get("/by-no/{summary_no}", response_model=IpdDischargeSummaryRead)
async def get_discharge_summary_by_no(
    summary_no: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).get_summary_by_no(summary_no)


@router.get("/{summary_id}", response_model=IpdDischargeSummaryRead)
async def get_discharge_summary(
    summary_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).get_summary(summary_id)


@router.put("/{summary_id}", response_model=IpdDischargeSummaryRead)
async def update_discharge_summary(
    summary_id: str,
    data: IpdDischargeSummaryUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdDischargeSummaryService(session).update_summary(summary_id, data)
