from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

PaperSize = Literal["A4", "A5", "A6", "LETTER", "LEGAL", "CUSTOM"]
Orientation = Literal["portrait", "landscape"]
PrintMode = Literal["preview", "direct"]


class PrintConfigCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=2, max_length=200)
    printer_name: str | None = Field(None, max_length=300)
    paper_size: PaperSize = "A4"
    custom_width_mm: float | None = Field(None, gt=0, le=1000)
    custom_height_mm: float | None = Field(None, gt=0, le=1000)
    orientation: Orientation = "portrait"
    print_mode: PrintMode = "preview"
    margin_top_mm: float = Field(12.0, ge=0, le=100)
    margin_right_mm: float = Field(12.0, ge=0, le=100)
    margin_bottom_mm: float = Field(15.0, ge=0, le=100)
    margin_left_mm: float = Field(12.0, ge=0, le=100)
    copies: int = Field(1, ge=1, le=20)
    layout_options: dict[str, Any] | None = None
    sort_order: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def validate_custom_size(self) -> "PrintConfigCreate":
        if self.paper_size == "CUSTOM":
            if not self.custom_width_mm or not self.custom_height_mm:
                raise ValueError("Custom width and height (mm) are required for CUSTOM paper size")
        return self


class PrintConfigUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    printer_name: str | None = Field(None, max_length=300)
    paper_size: PaperSize | None = None
    custom_width_mm: float | None = Field(None, gt=0, le=1000)
    custom_height_mm: float | None = Field(None, gt=0, le=1000)
    orientation: Orientation | None = None
    print_mode: PrintMode | None = None
    margin_top_mm: float | None = Field(None, ge=0, le=100)
    margin_right_mm: float | None = Field(None, ge=0, le=100)
    margin_bottom_mm: float | None = Field(None, ge=0, le=100)
    margin_left_mm: float | None = Field(None, ge=0, le=100)
    copies: int | None = Field(None, ge=1, le=20)
    layout_options: dict[str, Any] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class PrintConfigRead(ORMModel):
    id: str
    code: str
    name: str
    printer_name: str | None
    paper_size: str
    custom_width_mm: float | None
    custom_height_mm: float | None
    orientation: str
    print_mode: str
    margin_top_mm: float
    margin_right_mm: float
    margin_bottom_mm: float
    margin_left_mm: float
    copies: int
    layout_options: dict[str, Any] | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
