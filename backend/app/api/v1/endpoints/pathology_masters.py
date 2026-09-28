from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.pathology import (
    PathologyLabServiceCreate,
    PathologyNormalRangeCreate,
    PathologyNormalRangeRead,
    PathologyNormalRangeUpdate,
    PathologyOrderRead,
    PathologyParameterCreate,
    PathologyParameterRead,
    PathologyParameterUpdate,
    PathologyResultsUpdate,
    PathologyResultTemplateCreate,
    PathologyResultTemplateRead,
    PathologyResultTemplateUpdate,
    PathologyServiceParameterCreate,
    PathologyServiceParameterRead,
    PathologyUnitCreate,
    PathologyUnitRead,
    PathologyUnitUpdate,
    PathologyWorkListItem,
)
from app.schemas.service_note import (
    ServiceNoteCreate,
    ServiceNoteRead,
    ServiceNoteUpdate,
)
from app.services.pathology_masters import PathologyMastersService, PathologyOrderService
from app.services.service_note import ServiceNoteService

router = APIRouter()


@router.get("/notes", response_model=list[ServiceNoteRead])
async def list_service_notes(
    _: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await ServiceNoteService(session).list_notes()


@router.post("/notes", response_model=ServiceNoteRead, status_code=201)
async def create_service_note(
    data: ServiceNoteCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceNoteService(session).create_note(data)


@router.patch("/notes/{note_id}", response_model=ServiceNoteRead)
async def update_service_note(
    note_id: str,
    data: ServiceNoteUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceNoteService(session).update_note(note_id, data)


@router.delete("/notes/{note_id}", response_model=ServiceNoteRead)
async def delete_service_note(
    note_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ServiceNoteService(session).delete_note(note_id)


@router.get("/units", response_model=list[PathologyUnitRead])
async def list_units(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await PathologyMastersService(session).list_units()


@router.post("/units", response_model=PathologyUnitRead, status_code=201)
async def create_unit(
    data: PathologyUnitCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_unit(data)


@router.patch("/units/{unit_id}", response_model=PathologyUnitRead)
async def update_unit(
    unit_id: str,
    data: PathologyUnitUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).update_unit(unit_id, data)


@router.delete("/units/{unit_id}", response_model=PathologyUnitRead)
async def delete_unit(
    unit_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).delete_unit(unit_id)


@router.get("/parameters", response_model=list[PathologyParameterRead])
async def list_parameters(
    _: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await PathologyMastersService(session).list_parameters()


@router.post("/parameters", response_model=PathologyParameterRead, status_code=201)
async def create_parameter(
    data: PathologyParameterCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_parameter(data)


@router.patch("/parameters/{parameter_id}", response_model=PathologyParameterRead)
async def update_parameter(
    parameter_id: str,
    data: PathologyParameterUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).update_parameter(parameter_id, data)


@router.delete("/parameters/{parameter_id}", response_model=PathologyParameterRead)
async def delete_parameter(
    parameter_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).delete_parameter(parameter_id)


@router.get("/service-parameters", response_model=list[PathologyServiceParameterRead])
async def list_mappings(
    service_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).list_mappings(service_id=service_id)


@router.post("/service-parameters", response_model=PathologyServiceParameterRead, status_code=201)
async def create_mapping(
    data: PathologyServiceParameterCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_mapping(data)


@router.delete("/service-parameters/{mapping_id}", response_model=PathologyServiceParameterRead)
async def delete_mapping(
    mapping_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).delete_mapping(mapping_id)


@router.get("/normal-ranges", response_model=list[PathologyNormalRangeRead])
async def list_ranges(
    parameter_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).list_ranges(parameter_id=parameter_id)


@router.post("/normal-ranges", response_model=PathologyNormalRangeRead, status_code=201)
async def create_range(
    data: PathologyNormalRangeCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_range(data)


@router.patch("/normal-ranges/{range_id}", response_model=PathologyNormalRangeRead)
async def update_range(
    range_id: str,
    data: PathologyNormalRangeUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).update_range(range_id, data)


@router.delete("/normal-ranges/{range_id}", response_model=PathologyNormalRangeRead)
async def delete_range(
    range_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).delete_range(range_id)


@router.get("/lab-services")
async def list_lab_services(
    _: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await PathologyMastersService(session).list_lab_services()


@router.post("/lab-services", status_code=201)
async def create_lab_service(
    data: PathologyLabServiceCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_lab_service(data)


@router.get("/result-templates", response_model=list[PathologyResultTemplateRead])
async def list_result_templates(
    parameter_id: str | None = Query(None),
    service_id: str | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).list_result_templates(
        parameter_id=parameter_id,
        service_id=service_id,
    )


@router.get("/result-templates/{template_id}", response_model=PathologyResultTemplateRead)
async def get_result_template(
    template_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).get_result_template(template_id)


@router.post("/result-templates", response_model=PathologyResultTemplateRead, status_code=201)
async def create_result_template(
    data: PathologyResultTemplateCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).create_result_template(data)


@router.patch("/result-templates/{template_id}", response_model=PathologyResultTemplateRead)
async def update_result_template(
    template_id: str,
    data: PathologyResultTemplateUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).update_result_template(template_id, data)


@router.delete("/result-templates/{template_id}", response_model=PathologyResultTemplateRead)
async def delete_result_template(
    template_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyMastersService(session).delete_result_template(template_id)


@router.get("/work-list", response_model=list[PathologyWorkListItem])
async def work_list(
    bill_date: date | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyOrderService(session).work_list(bill_date=bill_date)


@router.get("/orders/by-bill/{bill_id}", response_model=PathologyOrderRead)
async def get_order_by_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyOrderService(session).get_order_by_bill(bill_id)


@router.put("/orders/by-bill/{bill_id}/results", response_model=PathologyOrderRead)
async def update_results(
    bill_id: str,
    data: PathologyResultsUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyOrderService(session).update_results(bill_id, data)


@router.post("/orders/by-bill/{bill_id}/authorize", response_model=PathologyOrderRead)
async def authorize_order(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyOrderService(session).authorize_order(bill_id)
