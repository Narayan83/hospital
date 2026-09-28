from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.dashboard_shortcut import (
    DashboardShortcutBulkSave,
    DashboardShortcutCreate,
    DashboardShortcutRead,
)
from app.services.dashboard_shortcut import DashboardShortcutService

router = APIRouter()


@router.get("/shortcuts", response_model=list[DashboardShortcutRead])
async def list_dashboard_shortcuts(
    active_only: bool = True,
    host_code: str = "dashboard",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardShortcutService(session).list_shortcuts(
        user, host_code=host_code, active_only=active_only
    )


@router.get("/shortcut-menus")
async def list_shortcut_candidate_menus(
    host_code: str = "dashboard",
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardShortcutService(session).list_available_menus(host_code=host_code)


@router.put("/shortcuts", response_model=list[DashboardShortcutRead])
async def save_dashboard_shortcuts(
    data: DashboardShortcutBulkSave,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardShortcutService(session).save_all(user, data)


@router.post("/shortcuts", response_model=DashboardShortcutRead, status_code=201)
async def create_dashboard_shortcut(
    data: DashboardShortcutCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardShortcutService(session).create_shortcut(user, data)


@router.delete("/shortcuts/{shortcut_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_shortcut(
    shortcut_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await DashboardShortcutService(session).delete_shortcut(user, shortcut_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
