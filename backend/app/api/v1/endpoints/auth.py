import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.app_data import AppDataResponse
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo
from app.schemas.menu import MenuTreeNode
from app.services.app_data import AppDataService
from app.services.auth import AuthService
from app.services.menu import MenuService

router = APIRouter()

_perf_logger = logging.getLogger("hms.perf")
if not _perf_logger.handlers:
    _log_dir = Path(__file__).resolve().parents[4] / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(_log_dir / "login_perf.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    _perf_logger.addHandler(handler)
    _perf_logger.setLevel(logging.INFO)
    _perf_logger.propagate = False


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_session)):
    t0 = time.perf_counter()
    service = AuthService(session)
    response = await service.login(data)
    _perf_logger.info("POST /auth/login total_ms=%.1f", (time.perf_counter() - t0) * 1000)
    return response


@router.get("/me", response_model=UserInfo)
async def me(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    roles = [m.role.role_name for m in current_user.role_mappings if m.role]
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        roles=roles,
    )


@router.get("/my-menus", response_model=list[MenuTreeNode])
async def my_menus(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    service = MenuService(session)
    return await service.get_user_menu_tree(current_user.id)


@router.get("/app-data", response_model=AppDataResponse)
async def app_data(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    t0 = time.perf_counter()
    payload = await AppDataService(session).get_app_data()
    _perf_logger.info("GET /auth/app-data total_ms=%.1f", (time.perf_counter() - t0) * 1000)
    return payload
