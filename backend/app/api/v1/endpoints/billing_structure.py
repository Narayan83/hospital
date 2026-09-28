from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.billing_structure import (
    BillingStructureCreate,
    BillingStructureRead,
    BillingStructureTreeNode,
    BillingStructureUpdate,
)
from app.services.billing_structure import BillingStructureService

router = APIRouter()


@router.get("", response_model=list[BillingStructureRead])
async def list_billing_structure(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingStructureService(session).list_mappings()


@router.get("/tree", response_model=list[BillingStructureTreeNode])
async def get_billing_structure_tree(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingStructureService(session).get_tree()


@router.post("", response_model=BillingStructureRead, status_code=201)
async def create_billing_structure(
    data: BillingStructureCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingStructureService(session).create_mapping(data)


@router.patch("/{mapping_id}", response_model=BillingStructureRead)
async def update_billing_structure(
    mapping_id: str,
    data: BillingStructureUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingStructureService(session).update_mapping(mapping_id, data)


@router.delete("/{mapping_id}", response_model=BillingStructureRead)
async def delete_billing_structure(
    mapping_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await BillingStructureService(session).delete_mapping(mapping_id)
