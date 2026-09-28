from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.print_config import PrintConfig
from app.repositories.base import BaseRepository


class PrintConfigRepository(BaseRepository[PrintConfig]):
    model = PrintConfig

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[PrintConfig]:
        result = await self.session.execute(
            select(PrintConfig)
            .where(PrintConfig.is_active.is_(True))
            .order_by(PrintConfig.sort_order, PrintConfig.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> PrintConfig | None:
        result = await self.session.execute(
            select(PrintConfig).where(PrintConfig.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: str) -> PrintConfig | None:
        result = await self.session.execute(
            select(PrintConfig).where(PrintConfig.id == config_id)
        )
        return result.scalar_one_or_none()
