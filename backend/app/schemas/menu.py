from pydantic import BaseModel

from app.schemas.common import ORMModel


class MenuPermissions(BaseModel):
    can_view: bool = True
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class MenuTreeNode(ORMModel):
    id: str
    code: str
    label: str
    icon: str | None = None
    sort_order: int
    legacy_mcode: int | None = None
    legacy_form: str | None = None
    parameters: str | None = None
    permissions: MenuPermissions
    children: list["MenuTreeNode"] = []


class MenuRead(ORMModel):
    id: str
    code: str
    label: str
    parent_id: str | None
    icon: str | None
    sort_order: int
    legacy_mcode: int | None
    legacy_form: str | None
    parameters: str | None
    is_active: bool


MenuTreeNode.model_rebuild()
