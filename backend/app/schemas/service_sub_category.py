from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ServiceSubCategoryBase(BaseModel):
    category_id: str
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    sort_order: int = 0


class ServiceSubCategoryCreate(ServiceSubCategoryBase):
    pass


class ServiceSubCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    sort_order: int | None = None


class ServiceSubCategoryRead(ORMModel):
    id: str
    category_id: str
    category_code: str | None = None
    category_name: str | None = None
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
