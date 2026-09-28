from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.repositories.user_role import UserRoleRepository
from app.schemas.user_mgmt import UserRoleAssign, UserRoleMappingRead


class UserRoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRoleRepository(session)
        self.users = UserRepository(session)

    async def list_for_user(self, user_id: str) -> list[UserRoleMappingRead]:
        mappings = await self.repo.list_for_user(user_id)
        return [
            UserRoleMappingRead(
                id=m.id,
                user_id=m.user_id,
                role_id=m.role_id,
                role_name=m.role.role_name if m.role else "",
                priority=m.priority,
                created_at=m.created_at,
            )
            for m in mappings
        ]

    async def assign(self, data: UserRoleAssign) -> UserRoleMappingRead:
        user = await self.users.get_by_id(data.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        await self.repo.assign(data)
        mappings = await self.repo.list_for_user(data.user_id)
        mapping = next((m for m in mappings if m.role_id == data.role_id), None)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role assignment failed")
        return UserRoleMappingRead(
            id=mapping.id,
            user_id=mapping.user_id,
            role_id=mapping.role_id,
            role_name=mapping.role.role_name if mapping.role else "",
            priority=mapping.priority,
            created_at=mapping.created_at,
        )

    async def remove(self, mapping_id: str) -> None:
        await self.repo.remove(mapping_id)
