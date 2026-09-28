from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.user_mgmt import NotificationSetupBulk
from app.services.notification import NotificationService

router = APIRouter()


@router.get("/setup")
async def get_notification_setup(
    event_code: str = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await NotificationService(session).get_setup(event_code)


@router.put("/setup")
async def save_notification_setup(
    data: NotificationSetupBulk,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await NotificationService(session).save_setup(data)
