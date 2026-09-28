from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class BillCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
