from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_setup import NotificationSetup
from app.repositories.base import BaseRepository
from app.schemas.user_mgmt import NotificationSetupBulk


class NotificationRepository(BaseRepository[NotificationSetup]):
    model = NotificationSetup

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_by_event(self, event_code: str) -> list[NotificationSetup]:
        result = await self.session.execute(
            select(NotificationSetup).where(NotificationSetup.event_code == event_code)
        )
        return list(result.scalars().all())

    async def replace_event_recipients(self, data: NotificationSetupBulk) -> list[NotificationSetup]:
        await self.session.execute(
            delete(NotificationSetup).where(NotificationSetup.event_code == data.event_code)
        )
        created: list[NotificationSetup] = []
        for item in data.recipients:
            if not item.is_enabled:
                continue
            row = NotificationSetup(event_code=data.event_code, user_id=item.user_id, is_enabled=True)
            self.session.add(row)
            created.append(row)
        await self.session.flush()
        return created
