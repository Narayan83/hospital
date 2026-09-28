from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.print_config import PrintConfig
from app.models.user import User
from app.reports.layout_render import render_document_html
from app.reports.print_layouts import (
    DOCUMENT_NAMES,
    STANDARD_PAGES,
    catalog_payload,
    custom_pages_of,
    default_document_layout,
    normalize_layout,
    paper_mm,
    resolve_format,
    sample_context,
)
from app.repositories.print_config import PrintConfigRepository
from app.schemas.print_config import PrintConfigCreate, PrintConfigRead, PrintConfigUpdate
from app.services.print_config import PrintConfigService

router = APIRouter()


class LayoutSaveIn(BaseModel):
    layout: dict = Field(default_factory=dict)
    paper_size: str | None = None
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    orientation: str | None = None


class LayoutPreviewIn(BaseModel):
    code: str
    bill_format: str | None = "A4"
    layout: dict = Field(default_factory=dict)


def _require_document(code: str) -> str:
    code_u = (code or "").strip().upper()
    if code_u not in DOCUMENT_NAMES:
        raise HTTPException(status_code=404, detail="No template for this document")
    return code_u


async def _config_for_document(session: AsyncSession, code: str, *, create: bool) -> PrintConfig | None:
    repo = PrintConfigRepository(session)
    obj = await repo.get_by_code(code)
    if obj or not create:
        return obj
    width, height = paper_mm(None, "A4")
    obj = PrintConfig(
        code=code,
        name=DOCUMENT_NAMES[code],
        paper_size="A4",
        custom_width_mm=width,
        custom_height_mm=height,
        orientation="portrait",
        print_mode="preview",
        is_active=True,
        sort_order=50,
    )
    session.add(obj)
    await session.flush()
    return obj


@router.get("/layouts/catalog")
async def print_layout_catalog(_u: User = Depends(get_current_user)):
    return catalog_payload()


@router.get("/layouts/by-code/{code}")
async def get_print_layout(
    code: str,
    _u: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    code_u = _require_document(code)
    obj = await _config_for_document(session, code_u, create=False)
    layout = normalize_layout(code_u, obj.layout_options if obj else None)
    return {
        "id": obj.id if obj else None,
        "code": code_u,
        "name": DOCUMENT_NAMES[code_u],
        "paper_size": obj.paper_size if obj else "A4",
        "custom_width_mm": obj.custom_width_mm if obj else None,
        "custom_height_mm": obj.custom_height_mm if obj else None,
        "orientation": obj.orientation if obj else "portrait",
        "layout": layout,
    }


@router.put("/layouts/by-code/{code}")
async def save_print_layout(
    code: str,
    data: LayoutSaveIn,
    _u: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    code_u = _require_document(code)
    obj = await _config_for_document(session, code_u, create=True)
    assert obj is not None
    layout = normalize_layout(code_u, data.layout)
    layout["designed"] = True
    obj.layout_options = layout
    paper = (data.paper_size or "").strip().upper()
    if paper in STANDARD_PAGES or paper in custom_pages_of(layout) or paper == "CUSTOM":
        if paper in custom_pages_of(layout):
            page = custom_pages_of(layout)[paper]
            obj.paper_size = "CUSTOM"
            obj.custom_width_mm = page["width_mm"]
            obj.custom_height_mm = page["height_mm"]
        elif paper == "CUSTOM" and data.custom_width_mm and data.custom_height_mm:
            obj.paper_size = "CUSTOM"
            obj.custom_width_mm = data.custom_width_mm
            obj.custom_height_mm = data.custom_height_mm
        elif paper in STANDARD_PAGES:
            obj.paper_size = paper
            obj.custom_width_mm = None
            obj.custom_height_mm = None
    if data.orientation in {"portrait", "landscape"}:
        obj.orientation = data.orientation
        fmt = resolve_format(layout, paper or obj.paper_size)
        page = dict(layout.get("page") or {})
        page[fmt] = {"orientation": data.orientation}
        layout["page"] = page
        obj.layout_options = layout
    await session.flush()
    return {"id": obj.id, "code": code_u, "name": DOCUMENT_NAMES[code_u], "layout": layout, "paper_size": obj.paper_size}


@router.post("/layouts/by-code/{code}/reset")
async def reset_print_layout(
    code: str,
    _u: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    code_u = _require_document(code)
    obj = await _config_for_document(session, code_u, create=True)
    assert obj is not None
    layout = default_document_layout(code_u)
    obj.layout_options = layout
    await session.flush()
    return {"id": obj.id, "code": code_u, "layout": layout}


@router.post("/layouts/preview")
async def preview_print_layout(
    data: LayoutPreviewIn,
    _u: User = Depends(get_current_user),
):
    code_u = _require_document(data.code)
    layout = normalize_layout(code_u, data.layout)
    html = render_document_html(
        code=code_u,
        context=sample_context(code_u),
        layout_raw=layout,
        bill_format=data.bill_format,
    )
    return {"html": html}


@router.get("", response_model=list[PrintConfigRead])
async def list_print_configs(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).list_configs()


@router.get("/by-code/{code}", response_model=PrintConfigRead)
async def get_print_config_by_code(
    code: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).get_config_by_code(code)


@router.get("/{config_id}", response_model=PrintConfigRead)
async def get_print_config(
    config_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).get_config(config_id)


@router.post("", response_model=PrintConfigRead, status_code=201)
async def create_print_config(
    data: PrintConfigCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).create_config(data)


@router.patch("/{config_id}", response_model=PrintConfigRead)
async def update_print_config(
    config_id: str,
    data: PrintConfigUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).update_config(config_id, data)


@router.delete("/{config_id}", response_model=PrintConfigRead)
async def delete_print_config(
    config_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PrintConfigService(session).delete_config(config_id)
