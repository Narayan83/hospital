import asyncio
import logging
import time

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo
from app.services.app_data import AppDataService
from app.services.menu import MenuService

_logger = logging.getLogger("hms.perf")


class AuthService:
    SUPER_ADMIN_ROLE = "Super Admin"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.menus = MenuService(session)

    async def login(self, data: LoginRequest) -> LoginResponse:
        t0 = time.perf_counter()
        user = await self.users.get_by_email(data.email.lower())
        t_user = time.perf_counter()
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        t_pass = time.perf_counter()
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

        roles = [m.role.role_name for m in user.role_mappings if m.role and m.role.is_active]
        token = create_access_token(user.id)

        async def _timed(label: str, coro):
            t = time.perf_counter()
            value = await coro
            return value, (time.perf_counter() - t) * 1000, label

        (menu_tree, menu_ms, _), (app_data, app_data_ms, _) = await asyncio.gather(
            _timed("menus", self.menus.get_user_menu_tree(user.id)),
            _timed("app_data", AppDataService(self.session).get_app_data()),
        )
        t_done = time.perf_counter()
        _logger.info(
            "login breakdown ms: load_user=%.1f password=%.1f menus=%.1f app_data=%.1f total=%.1f",
            (t_user - t0) * 1000,
            (t_pass - t_user) * 1000,
            menu_ms,
            app_data_ms,
            (t_done - t0) * 1000,
        )

        return LoginResponse(
            access_token=token,
            user=UserInfo(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                roles=roles,
                doctor_id=user.doctor_id,
                maps_to_doctor=bool(user.user_type and user.user_type.maps_to_doctor),
                user_type_sort_order=user.user_type.sort_order if user.user_type else None,
            ),
            menus=menu_tree,
            app_data=app_data,
        )
