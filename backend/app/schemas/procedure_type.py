from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProcedureTypeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=150)
    sort_order: int = 0
    is_active: bool = True


class ProcedureTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    sort_order: int | None = None
    is_active: bool | None = None


class ProcedureTypeRead(ORMModel):
    id: str
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
