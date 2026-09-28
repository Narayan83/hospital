from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DashboardShortcutRead(ORMModel):
    id: str
    user_id: str | None = None
    host_code: str = "dashboard"
    module_code: str
    button_label: str
    description: str | None = None
    sort_order: int
    is_active: bool = True


class DashboardShortcutItem(BaseModel):
    module_code: str = Field(..., min_length=1, max_length=100)
    button_label: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=200)
    sort_order: int = 0
    is_active: bool = True


class DashboardShortcutBulkSave(BaseModel):
    host_code: str = Field("dashboard", max_length=100)
    items: list[DashboardShortcutItem] = Field(default_factory=list)


class DashboardShortcutCreate(DashboardShortcutItem):
    host_code: str = Field("dashboard", max_length=100)
