from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.department import DepartmentService

router = APIRouter()


@router.get("", response_model=list[DepartmentRead])
async def list_departments(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DepartmentService(session).list_departments()


@router.get("/{department_id}", response_model=DepartmentRead)
async def get_department(
    department_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DepartmentService(session).get_department(department_id)


@router.post("", response_model=DepartmentRead, status_code=201)
async def create_department(
    data: DepartmentCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DepartmentService(session).create_department(data)


@router.patch("/{department_id}", response_model=DepartmentRead)
async def update_department(
    department_id: str,
    data: DepartmentUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DepartmentService(session).update_department(department_id, data)


@router.delete("/{department_id}", response_model=DepartmentRead)
async def delete_department(
    department_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DepartmentService(session).delete_department(department_id)
