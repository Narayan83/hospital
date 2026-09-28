from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class DepartmentRead(ORMModel):
    id: str
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(BaseModel):
    """Code is optional — blank/omitted values get the next number on save."""

    code: str | None = Field(default=None, max_length=30)
    name: str = Field(..., min_length=2, max_length=150)
    sort_order: int = 0
    is_active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def blank_code_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    sort_order: int | None = None
    is_active: bool | None = None
