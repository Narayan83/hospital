from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_patient_service, get_session
from app.models.user import User
from app.services.patient_files import resolve_patient_file
from app.schemas.common import PaginatedResponse
from app.schemas.patient import PatientCreate, PatientNoPreview, PatientRead, PatientSearchFilters, PatientUpdate
from app.services.patient import PatientService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PatientRead])
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.list_patients(page=page, page_size=page_size, search=search)


@router.get("/search", response_model=PaginatedResponse[PatientRead])
async def search_patients(
    patient_no: str | None = Query(None, max_length=20),
    first_name: str | None = Query(None, max_length=100),
    middle_name: str | None = Query(None, max_length=100),
    last_name: str | None = Query(None, max_length=100),
    village: str | None = Query(None, max_length=100),
    post: str | None = Query(None, max_length=100),
    taluk: str | None = Query(None, max_length=100),
    district: str | None = Query(None, max_length=100),
    phone: str | None = Query(None, max_length=20),
    mobile: str | None = Query(None, max_length=20),
    mobile2: str | None = Query(None, max_length=20),
    pin_code: str | None = Query(None, max_length=20),
    old_id: str | None = Query(None, max_length=50),
    aadhar_no: str | None = Query(None, max_length=20),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    active_only: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    filters = PatientSearchFilters(
        patient_no=patient_no,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        village=village,
        post=post,
        taluk=taluk,
        district=district,
        phone=phone,
        mobile=mobile,
        mobile2=mobile2,
        pin_code=pin_code,
        old_id=old_id,
        aadhar_no=aadhar_no,
        page=page,
        page_size=page_size,
        active_only=active_only,
    )
    return await service.search_patients(filters)


@router.get("/next-id-preview", response_model=PatientNoPreview)
async def preview_next_patient_id(
    hospital_section_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.preview_next_patient_no(hospital_section_id)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.get_patient(patient_id)


@router.post("", response_model=PatientRead, status_code=201)
async def create_patient(
    data: PatientCreate,
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.create_patient(data)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: str,
    data: PatientUpdate,
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.update_patient(patient_id, data)


@router.post("/{patient_id}/aadhar-scan", response_model=PatientRead)
async def upload_aadhar_scan(
    patient_id: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    return await service.upload_aadhar_scan(patient_id, file)


@router.get("/{patient_id}/aadhar-scan")
async def get_aadhar_scan(
    patient_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = get_patient_service(session)
    patient = await service.get_patient(patient_id)
    file_path = resolve_patient_file(patient.aadhar_scan_path)
    if not file_path:
        return {"detail": "Aadhar scan not found"}
    return FileResponse(file_path)
