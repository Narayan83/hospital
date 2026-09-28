from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification import NotificationRepository
from app.repositories.user import UserRepository
from app.schemas.user_mgmt import NotificationSetupBulk


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.repo = NotificationRepository(session)
        self.users = UserRepository(session)

    async def save_setup(self, data: NotificationSetupBulk) -> dict:
        rows = await self.repo.replace_event_recipients(data)
        return {"event_code": data.event_code, "recipient_count": len(rows)}

    async def get_setup(self, event_code: str) -> dict:
        rows = await self.repo.list_by_event(event_code)
        users = await self.users.list_users()
        enabled_ids = {row.user_id for row in rows if row.is_enabled}
        return {
            "event_code": event_code,
            "users": [
                {
                    "user_id": u.id,
                    "full_name": u.full_name,
                    "email": u.email,
                    "is_enabled": u.id in enabled_ids,
                }
                for u in users
            ],
        }
