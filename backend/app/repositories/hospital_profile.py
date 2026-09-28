from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hospital_profile import HospitalProfile
from app.repositories.base import BaseRepository
from app.schemas.hospital_profile import HospitalProfileUpdate

DEFAULT_CODE = "MAIN"
DEFAULT_NAME = "City Care Hospital & Research Centre"
DEFAULT_SETTINGS = {
    "name": DEFAULT_NAME,
    "pathology_name": f"{DEFAULT_NAME} Pathology Lab",
    "medical_shop_name": f"{DEFAULT_NAME} Medical Shop",
    "address_line1": "123 Medical Complex, 1st Floor",
    "address_line2": "Near City General Hospital",
    "address_line3": "MG Road, Central Business District",
    "address_line4": "Bangalore, Karnataka",
    "pin_code": "560001",
    "phone": "080-12345678",
    "email": "info@citycarehospital.com",
    "gstin": "29ABCDE1234F1Z5",
    "software_id": "HMS-2025-001",
}


class HospitalProfileRepository(BaseRepository[HospitalProfile]):
    model = HospitalProfile

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_singleton(self) -> HospitalProfile | None:
        result = await self.session.execute(
            select(HospitalProfile).where(HospitalProfile.code == DEFAULT_CODE)
        )
        return result.scalar_one_or_none()

    async def get_or_create_default(self) -> HospitalProfile:
        profile = await self.get_singleton()
        if profile:
            return profile
        profile = HospitalProfile(code=DEFAULT_CODE, **DEFAULT_SETTINGS)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def update_singleton(self, data: HospitalProfileUpdate) -> HospitalProfile:
        profile = await self.get_or_create_default()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile
