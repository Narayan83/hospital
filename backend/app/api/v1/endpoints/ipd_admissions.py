from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.ipd_admission import IpdAdmissionCreate, IpdAdmissionRead
from app.services.ipd_admission import IpdAdmissionService

router = APIRouter()


@router.get("", response_model=list[IpdAdmissionRead])
async def list_ipd_admissions(
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    patient_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdAdmissionService(session).list_admissions(
        status=status, search=search, patient_id=patient_id
    )


@router.post("", response_model=IpdAdmissionRead, status_code=201)
async def create_ipd_admission(
    data: IpdAdmissionCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdAdmissionService(session).create_admission(data)


@router.get("/{admission_id}", response_model=IpdAdmissionRead)
async def get_ipd_admission(
    admission_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdAdmissionService(session).get_admission(admission_id)


@router.get("/by-no/{admission_no}", response_model=IpdAdmissionRead)
async def get_ipd_admission_by_no(
    admission_no: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await IpdAdmissionService(session).get_admission_by_no(admission_no)
