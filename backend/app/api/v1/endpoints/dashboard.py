from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.dashboard import DashboardStats
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DashboardService(session).get_stats()
