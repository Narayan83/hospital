from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RoleBase(BaseModel):
    role_name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    role_name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class RoleRead(RoleBase, ORMModel):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RoleMenuPermissionItem(BaseModel):
    menu_id: str
    can_view: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class RolePermissionsUpdate(BaseModel):
    permissions: list[RoleMenuPermissionItem]


class RoleMenuPermissionRead(RoleMenuPermissionItem):
    pass
