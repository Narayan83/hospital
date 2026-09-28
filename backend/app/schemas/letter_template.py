from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LetterTemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=200)
    subject: str | None = Field(None, max_length=300)
    body: str = ""
    sort_order: int = 0
    is_active: bool = True


class LetterTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    subject: str | None = Field(None, max_length=300)
    body: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class LetterTemplateRead(ORMModel):
    id: str
    code: str
    name: str
    subject: str | None
    body: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
