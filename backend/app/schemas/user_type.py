from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class UserTypeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=30)
    name: str = Field(..., min_length=2, max_length=100)
    sort_order: int = 0
    maps_to_doctor: bool = False
    is_active: bool = True


class UserTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    sort_order: int | None = None
    maps_to_doctor: bool | None = None
    is_active: bool | None = None


class UserTypeRead(ORMModel):
    id: str
    code: str
    name: str
    sort_order: int
    maps_to_doctor: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
