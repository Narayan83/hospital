import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.repositories.base import BaseRepository

_PS_CODE_RE = re.compile(r"^PS(\d+)$", re.IGNORECASE)
_PLAIN_NUM_RE = re.compile(r"^(\d+)$")


class PatientServiceMasterRepository(BaseRepository[PatientServiceMaster]):
    model = PatientServiceMaster

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def next_auto_code(self) -> str:
        """Next service code: PS{n+1} when PS* codes exist, else plain number, else PS1."""
        result = await self.session.execute(select(PatientServiceMaster.code))
        codes = [str(code).strip() for code in result.scalars().all() if code]
        ps_nums: list[int] = []
        plain_nums: list[int] = []
        for code in codes:
            match = _PS_CODE_RE.match(code)
            if match:
                ps_nums.append(int(match.group(1)))
                continue
            match = _PLAIN_NUM_RE.match(code)
            if match:
                plain_nums.append(int(match.group(1)))
        if ps_nums:
            return f"PS{max(ps_nums) + 1}"
        if plain_nums:
            return str(max(plain_nums) + 1)
        return "PS1"

    async def list_active(
        self, *, exclude_category_codes: tuple[str, ...] = ()
    ) -> list[PatientServiceMaster]:
        stmt = (
            select(PatientServiceMaster)
            .options(
                selectinload(PatientServiceMaster.doctor),
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
            )
            .where(PatientServiceMaster.is_active.is_(True))
        )
        if exclude_category_codes:
            stmt = stmt.outerjoin(PatientServiceMaster.category).where(
                or_(
                    PatientServiceMaster.category_id.is_(None),
                    ServiceCategory.code.notin_(exclude_category_codes),
                )
            )
        result = await self.session.execute(
            stmt.order_by(PatientServiceMaster.code)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> PatientServiceMaster | None:
        result = await self.session.execute(
            select(PatientServiceMaster)
            .options(
                selectinload(PatientServiceMaster.doctor),
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
            )
            .where(PatientServiceMaster.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, service_id: str) -> PatientServiceMaster | None:
        result = await self.session.execute(
            select(PatientServiceMaster)
            .options(
                selectinload(PatientServiceMaster.doctor),
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
            )
            .where(PatientServiceMaster.id == service_id)
        )
        return result.scalar_one_or_none()
