from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.procedure_type import ProcedureTypeCreate, ProcedureTypeRead, ProcedureTypeUpdate
from app.services.procedure_type import ProcedureTypeService

router = APIRouter()


@router.get("", response_model=list[ProcedureTypeRead])
async def list_procedure_types(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ProcedureTypeService(session).list_procedure_types()


@router.get("/{procedure_type_id}", response_model=ProcedureTypeRead)
async def get_procedure_type(
    procedure_type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ProcedureTypeService(session).get_procedure_type(procedure_type_id)


@router.post("", response_model=ProcedureTypeRead, status_code=201)
async def create_procedure_type(
    data: ProcedureTypeCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ProcedureTypeService(session).create_procedure_type(data)


@router.patch("/{procedure_type_id}", response_model=ProcedureTypeRead)
async def update_procedure_type(
    procedure_type_id: str,
    data: ProcedureTypeUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ProcedureTypeService(session).update_procedure_type(procedure_type_id, data)


@router.delete("/{procedure_type_id}", response_model=ProcedureTypeRead)
async def delete_procedure_type(
    procedure_type_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ProcedureTypeService(session).delete_procedure_type(procedure_type_id)
