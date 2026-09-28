from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.number_sequence import NumberSequence


class NumberSequenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def peek_value(self, entity_type: str, scope_key: str) -> int:
        result = await self.session.execute(
            select(NumberSequence)
            .where(NumberSequence.entity_type == entity_type)
            .where(NumberSequence.scope_key == scope_key)
        )
        row = result.scalar_one_or_none()
        return row.last_value if row else 0

    async def get_next_value(self, entity_type: str, scope_key: str) -> int:
        result = await self.session.execute(
            select(NumberSequence)
            .where(NumberSequence.entity_type == entity_type)
            .where(NumberSequence.scope_key == scope_key)
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = NumberSequence(entity_type=entity_type, scope_key=scope_key, last_value=1)
            self.session.add(row)
            await self.session.flush()
            return row.last_value
        row.last_value += 1
        await self.session.flush()
        return row.last_value
