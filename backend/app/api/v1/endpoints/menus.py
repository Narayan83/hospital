from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.repositories.menu import MenuRepository
from app.schemas.menu import MenuRead

router = APIRouter()


@router.get("", response_model=list[MenuRead])
async def list_menus(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    repo = MenuRepository(session)
    menus = await repo.list_all_active()
    return [MenuRead.model_validate(m) for m in menus]
