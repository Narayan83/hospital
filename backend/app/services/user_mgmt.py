from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.doctor import DoctorRepository
from app.repositories.user import UserRepository
from app.repositories.user_type import UserTypeRepository
from app.schemas.user_mgmt import UserCreate, UserRead, UserUpdate


class UserManagementService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)
        self.user_type_repo = UserTypeRepository(session)
        self.doctor_repo = DoctorRepository(session)

    def _to_read(self, user) -> UserRead:
        roles = [m.role.role_name for m in user.role_mappings if m.role]
        doctor_name = None
        if user.doctor:
            doctor_name = user.doctor.full_name
        return UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            user_type_id=user.user_type_id,
            user_type_code=user.user_type.code if user.user_type else None,
            user_type_name=user.user_type.name if user.user_type else None,
            doctor_id=user.doctor_id,
            doctor_name=doctor_name,
            is_active=user.is_active,
            roles=roles,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def _validate_type_and_doctor(
        self,
        user_type_id: str,
        doctor_id: str | None,
    ) -> None:
        user_type = await self.user_type_repo.get_by_id(user_type_id)
        if not user_type or not user_type.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user type")

        if user_type.maps_to_doctor:
            if not doctor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Doctor is required for this user type",
                )
            doctor = await self.doctor_repo.get_by_id(doctor_id)
            if not doctor or not doctor.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor")
        elif doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor can only be assigned to doctor user type",
            )

    async def list_users(self, *, active_only: bool = True) -> list[UserRead]:
        users = await self.repo.list_users(active_only=active_only)
        return [self._to_read(u) for u in users]

    async def create_user(self, data: UserCreate) -> UserRead:
        existing = await self.repo.get_by_email(data.email.lower())
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        await self._validate_type_and_doctor(data.user_type_id, data.doctor_id)
        user = await self.repo.create(data)
        return self._to_read(user)

    async def update_user(self, user_id: str, data: UserUpdate) -> UserRead:
        user = await self.repo.get_with_roles(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if data.email and data.email.lower() != user.email:
            existing = await self.repo.get_by_email(data.email.lower())
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")

        user_type_id = data.user_type_id if data.user_type_id is not None else user.user_type_id
        if user_type_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User type is required")

        if "doctor_id" in data.model_dump(exclude_unset=True):
            doctor_id = data.doctor_id
        else:
            doctor_id = user.doctor_id

        await self._validate_type_and_doctor(user_type_id, doctor_id)
        updated = await self.repo.update(user, data)
        return self._to_read(updated)

    async def delete_user(self, user_id: str) -> UserRead:
        user = await self.repo.get_with_roles(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.email == "admin@admin.com":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete super admin user")
        deactivated = await self.repo.deactivate(user)
        return self._to_read(deactivated)
