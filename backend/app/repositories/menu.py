from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import Menu
from app.repositories.base import BaseRepository


class MenuRepository(BaseRepository[Menu]):
    model = Menu

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active_tree(self) -> list[Menu]:
        result = await self.session.execute(
            select(Menu)
            .options(selectinload(Menu.children))
            .where(Menu.parent_id.is_(None), Menu.is_active.is_(True))
            .order_by(Menu.sort_order)
        )
        roots = list(result.scalars().unique().all())
        for root in roots:
            root.children = sorted(
                [c for c in root.children if c.is_active],
                key=lambda m: m.sort_order,
            )
        return roots

    async def list_all_active(self) -> list[Menu]:
        result = await self.session.execute(
            select(Menu).where(Menu.is_active.is_(True)).order_by(Menu.sort_order)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Menu | None:
        result = await self.session.execute(select(Menu).where(Menu.code == code))
        return result.scalar_one_or_none()
