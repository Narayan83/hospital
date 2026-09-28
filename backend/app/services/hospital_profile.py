from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.hospital_profile import HospitalProfileRepository
from app.schemas.hospital_profile import HospitalProfileRead, HospitalProfileUpdate


class HospitalProfileService:
    def __init__(self, session: AsyncSession):
        self.repo = HospitalProfileRepository(session)

    async def get_profile(self) -> HospitalProfileRead:
        profile = await self.repo.get_or_create_default()
        return HospitalProfileRead.model_validate(profile)

    async def update_profile(self, data: HospitalProfileUpdate) -> HospitalProfileRead:
        profile = await self.repo.update_singleton(data)
        return HospitalProfileRead.model_validate(profile)
