from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pathology_bill import PathologyBill
from app.models.pathology_normal_range import PathologyNormalRange
from app.models.pathology_order import PathologyOrder, PathologyResult
from app.models.pathology_parameter import PathologyParameter, PathologyServiceParameter
from app.models.pathology_result_template import PathologyResultTemplate
from app.models.pathology_service_member import PathologyServiceMember
from app.models.pathology_unit import PathologyUnit
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.repositories.pathology_bill import PathologyBillRepository
from app.repositories.pathology_masters import (
    ORDER_STATUS_BILLED,
    ORDER_STATUS_REPORT_READY,
    PathologyNormalRangeRepository,
    PathologyParameterRepository,
    PathologyServiceParameterRepository,
    PathologyUnitRepository,
    can_authorize,
    format_range_text,
    is_value_abnormal,
    reference_range_rows,
)
from app.repositories.pathology_result_template import PathologyResultTemplateRepository
from app.repositories.patient import PatientRepository
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.pathology import (
    PathologyLabServiceCreate,
    PathologyNormalRangeCreate,
    PathologyNormalRangeRead,
    PathologyNormalRangeUpdate,
    PathologyOrderRead,
    PathologyParameterCreate,
    PathologyParameterRead,
    PathologyParameterUpdate,
    PathologyResultRead,
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


class PathologyMastersService:
    LAB_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.unit_repo = PathologyUnitRepository(session)
        self.param_repo = PathologyParameterRepository(session)
        self.map_repo = PathologyServiceParameterRepository(session)
        self.range_repo = PathologyNormalRangeRepository(session)
        self.service_repo = PatientServiceMasterRepository(session)
        self.template_repo = PathologyResultTemplateRepository(session)

    def _template_read(self, item: PathologyResultTemplate) -> PathologyResultTemplateRead:
        read = PathologyResultTemplateRead.model_validate(item)
        return read.model_copy(
            update={
                "parameter_code": item.parameter.code if item.parameter else None,
                "parameter_name": item.parameter.name if item.parameter else None,
                "service_code": item.service.code if item.service else None,
                "service_name": item.service.name if item.service else None,
            }
        )

    def _param_read(self, item: PathologyParameter) -> PathologyParameterRead:
        read = PathologyParameterRead.model_validate(item)
        return read.model_copy(
            update={
                "unit_name": item.unit.name if item.unit else None,
                "unit_code": item.unit.code if item.unit else None,
            }
        )

    async def list_units(self) -> list[PathologyUnitRead]:
        items = await self.unit_repo.list_active()
        return [PathologyUnitRead.model_validate(i) for i in items]

    async def create_unit(self, data: PathologyUnitCreate) -> PathologyUnitRead:
        code = data.code.strip().upper()
        existing = await self.unit_repo.get_by_code(code)
        if existing and existing.is_active:
            raise HTTPException(status_code=400, detail="Unit code already exists")
        if existing:
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.session.flush()
            return PathologyUnitRead.model_validate(existing)
        item = PathologyUnit(code=code, name=data.name.strip(), sort_order=data.sort_order, is_active=True)
        self.session.add(item)
        await self.session.flush()
        return PathologyUnitRead.model_validate(item)

    async def update_unit(self, unit_id: str, data: PathologyUnitUpdate) -> PathologyUnitRead:
        item = await self.unit_repo.get_by_id(unit_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Unit not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value:
                value = value.strip()
            setattr(item, field, value)
        await self.session.flush()
        return PathologyUnitRead.model_validate(item)

    async def delete_unit(self, unit_id: str) -> PathologyUnitRead:
        item = await self.unit_repo.get_by_id(unit_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Unit not found")
        item.is_active = False
        await self.session.flush()
        return PathologyUnitRead.model_validate(item)

    async def list_parameters(self) -> list[PathologyParameterRead]:
        items = await self.param_repo.list_active()
        return [self._param_read(i) for i in items]

    async def create_parameter(self, data: PathologyParameterCreate) -> PathologyParameterRead:
        code = data.code.strip().upper()
        existing = await self.param_repo.get_by_code(code)
        if existing and existing.is_active:
            raise HTTPException(status_code=400, detail="Parameter code already exists")
        if existing:
            for field, value in data.model_dump().items():
                if field == "code":
                    continue
                if field == "name" and value:
                    value = value.strip()
                setattr(existing, field, value)
            existing.is_active = True
            await self.session.flush()
            loaded = await self.param_repo.get_with_unit(existing.id)
            return self._param_read(loaded)  # type: ignore[arg-type]
        item = PathologyParameter(
            code=code,
            name=data.name.strip(),
            unit_id=data.unit_id,
            data_type=data.data_type,
            method=data.method,
            sort_order=data.sort_order,
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        loaded = await self.param_repo.get_with_unit(item.id)
        return self._param_read(loaded)  # type: ignore[arg-type]

    async def update_parameter(self, parameter_id: str, data: PathologyParameterUpdate) -> PathologyParameterRead:
        item = await self.param_repo.get_by_id(parameter_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Parameter not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value:
                value = value.strip()
            setattr(item, field, value)
        await self.session.flush()
        loaded = await self.param_repo.get_with_unit(item.id)
        return self._param_read(loaded)  # type: ignore[arg-type]

    async def delete_parameter(self, parameter_id: str) -> PathologyParameterRead:
        item = await self.param_repo.get_by_id(parameter_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Parameter not found")
        item.is_active = False
        await self.session.flush()
        return self._param_read(item)

    async def list_mappings(self, service_id: str | None = None) -> list[PathologyServiceParameterRead]:
        items = (
            await self.map_repo.list_for_service(service_id)
            if service_id
            else await self.map_repo.list_all()
        )
        reads = []
        for item in items:
            read = PathologyServiceParameterRead.model_validate(item)
            reads.append(
                read.model_copy(
                    update={
                        "service_code": item.service.code if item.service else None,
                        "service_name": item.service.name if item.service else None,
                        "parameter_code": item.parameter.code if item.parameter else None,
                        "parameter_name": item.parameter.name if item.parameter else None,
                    }
                )
            )
        return reads

    async def create_mapping(self, data: PathologyServiceParameterCreate) -> PathologyServiceParameterRead:
        service = await self.service_repo.get_by_id(data.service_id)
        if not service or not service.is_active:
            raise HTTPException(status_code=400, detail="Service not found")
        param = await self.param_repo.get_by_id(data.parameter_id)
        if not param or not param.is_active:
            raise HTTPException(status_code=400, detail="Parameter not found")
        existing = await self.map_repo.get_mapping(data.service_id, data.parameter_id)
        if existing:
            existing.sort_order = data.sort_order
            existing.is_required = data.is_required
            existing.is_active = True
            await self.session.flush()
            mappings = await self.map_repo.list_for_service(data.service_id)
            row = next(m for m in mappings if m.id == existing.id)
            read = PathologyServiceParameterRead.model_validate(row)
            return read.model_copy(
                update={
                    "service_code": row.service.code,
                    "service_name": row.service.name,
                    "parameter_code": row.parameter.code,
                    "parameter_name": row.parameter.name,
                }
            )
        item = PathologyServiceParameter(
            service_id=data.service_id,
            parameter_id=data.parameter_id,
            sort_order=data.sort_order,
            is_required=data.is_required,
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        mappings = await self.map_repo.list_for_service(data.service_id)
        row = next(m for m in mappings if m.id == item.id)
        read = PathologyServiceParameterRead.model_validate(row)
        return read.model_copy(
            update={
                "service_code": row.service.code,
                "service_name": row.service.name,
                "parameter_code": row.parameter.code,
                "parameter_name": row.parameter.name,
            }
        )

    async def delete_mapping(self, mapping_id: str) -> PathologyServiceParameterRead:
        item = await self.map_repo.get_by_id(mapping_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Mapping not found")
        item.is_active = False
        await self.session.flush()
        return PathologyServiceParameterRead.model_validate(item)

    async def list_ranges(self, parameter_id: str | None = None) -> list[PathologyNormalRangeRead]:
        items = await self.range_repo.list_active(parameter_id)
        reads = []
        for item in items:
            read = PathologyNormalRangeRead.model_validate(item)
            reads.append(
                read.model_copy(
                    update={
                        "parameter_code": item.parameter.code if item.parameter else None,
                        "parameter_name": item.parameter.name if item.parameter else None,
                        "unit_name": item.unit.name if item.unit else None,
                    }
                )
            )
        return reads

    async def create_range(self, data: PathologyNormalRangeCreate) -> PathologyNormalRangeRead:
        param = await self.param_repo.get_by_id(data.parameter_id)
        if not param or not param.is_active:
            raise HTTPException(status_code=400, detail="Parameter not found")
        item = PathologyNormalRange(**data.model_dump(), is_active=True)
        self.session.add(item)
        await self.session.flush()
        items = await self.range_repo.list_active(data.parameter_id)
        row = next(i for i in items if i.id == item.id)
        read = PathologyNormalRangeRead.model_validate(row)
        return read.model_copy(
            update={
                "parameter_code": row.parameter.code if row.parameter else None,
                "parameter_name": row.parameter.name if row.parameter else None,
                "unit_name": row.unit.name if row.unit else None,
            }
        )

    async def update_range(self, range_id: str, data: PathologyNormalRangeUpdate) -> PathologyNormalRangeRead:
        item = await self.range_repo.get_by_id(range_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Normal range not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.session.flush()
        items = await self.range_repo.list_active(item.parameter_id)
        row = next(i for i in items if i.id == item.id)
        read = PathologyNormalRangeRead.model_validate(row)
        return read.model_copy(
            update={
                "parameter_code": row.parameter.code if row.parameter else None,
                "parameter_name": row.parameter.name if row.parameter else None,
                "unit_name": row.unit.name if row.unit else None,
            }
        )

    async def delete_range(self, range_id: str) -> PathologyNormalRangeRead:
        item = await self.range_repo.get_by_id(range_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Normal range not found")
        item.is_active = False
        await self.session.flush()
        return PathologyNormalRangeRead.model_validate(item)

    async def _lab_category_id(self) -> str:
        result = await self.session.execute(
            select(ServiceCategory).where(ServiceCategory.code == self.LAB_CATEGORY_CODE)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=500, detail="LAB service category not configured")
        return cat.id

    async def list_lab_services(self) -> list:
        from app.schemas.patient_service_master import PatientServiceMasterRead

        cat_id = await self._lab_category_id()
        result = await self.session.execute(
            select(PatientServiceMaster)
            .options(
                selectinload(PatientServiceMaster.category),
                selectinload(PatientServiceMaster.sub_category),
            )
            .where(PatientServiceMaster.is_active.is_(True))
            .where(PatientServiceMaster.category_id == cat_id)
            .order_by(PatientServiceMaster.name)
        )
        items = []
        for row in result.scalars().all():
            read = PatientServiceMasterRead.model_validate(row)
            items.append(
                read.model_copy(
                    update={
                        "category_name": row.category.name if row.category else None,
                        "sub_category_name": row.sub_category.name if row.sub_category else None,
                    }
                )
            )
        return items

    async def create_lab_service(self, data: PathologyLabServiceCreate):
        from app.schemas.patient_service_master import PatientServiceMasterRead

        cat_id = await self._lab_category_id()
        code = data.code.strip().upper()
        existing = await self.service_repo.get_by_code(code)
        if existing and existing.is_active:
            raise HTTPException(status_code=400, detail="Service code already exists")
        if existing:
            existing.name = data.name.strip()
            existing.rate = data.rate
            existing.category_id = cat_id
            existing.sub_category_id = data.sub_category_id
            existing.is_service_active = True
            existing.is_active = True
            await self.session.flush()
            return PatientServiceMasterRead.model_validate(existing)
        item = PatientServiceMaster(
            code=code,
            name=data.name.strip(),
            rate=data.rate,
            service_charge=data.rate,
            category_id=cat_id,
            sub_category_id=data.sub_category_id,
            is_sharing=False,
            discount_apply=False,
            is_renewal=False,
            is_service_active=True,
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        return PatientServiceMasterRead.model_validate(item)

    async def list_result_templates(
        self,
        *,
        parameter_id: str | None = None,
        service_id: str | None = None,
    ) -> list[PathologyResultTemplateRead]:
        if parameter_id or service_id:
            items = await self.template_repo.list_for_result(
                parameter_id=parameter_id,
                service_id=service_id,
            )
        else:
            items = await self.template_repo.list_active()
        return [self._template_read(i) for i in items]

    async def get_result_template(self, template_id: str) -> PathologyResultTemplateRead:
        item = await self.template_repo.get_by_id(template_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Template not found")
        return self._template_read(item)

    async def create_result_template(
        self, data: PathologyResultTemplateCreate
    ) -> PathologyResultTemplateRead:
        code = data.code.strip().upper()
        existing = await self.template_repo.get_by_code(code)
        if existing and existing.is_active:
            raise HTTPException(status_code=400, detail="Template code already exists")
        if data.parameter_id:
            param = await self.param_repo.get_by_id(data.parameter_id)
            if not param or not param.is_active:
                raise HTTPException(status_code=400, detail="Parameter not found")
        if data.service_id:
            service = await self.service_repo.get_by_id(data.service_id)
            if not service or not service.is_active:
                raise HTTPException(status_code=400, detail="Service not found")
        if existing:
            existing.name = data.name.strip()
            existing.body = data.body or ""
            existing.parameter_id = data.parameter_id
            existing.service_id = data.service_id
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.session.flush()
            loaded = await self.template_repo.get_by_id(existing.id)
            return self._template_read(loaded)  # type: ignore[arg-type]
        item = PathologyResultTemplate(
            code=code,
            name=data.name.strip(),
            body=data.body or "",
            parameter_id=data.parameter_id,
            service_id=data.service_id,
            sort_order=data.sort_order,
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        loaded = await self.template_repo.get_by_id(item.id)
        return self._template_read(loaded)  # type: ignore[arg-type]

    async def update_result_template(
        self, template_id: str, data: PathologyResultTemplateUpdate
    ) -> PathologyResultTemplateRead:
        item = await self.template_repo.get_by_id(template_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Template not found")
        payload = data.model_dump(exclude_unset=True)
        if "parameter_id" in payload and payload["parameter_id"]:
            param = await self.param_repo.get_by_id(payload["parameter_id"])
            if not param or not param.is_active:
                raise HTTPException(status_code=400, detail="Parameter not found")
        if "service_id" in payload and payload["service_id"]:
            service = await self.service_repo.get_by_id(payload["service_id"])
            if not service or not service.is_active:
                raise HTTPException(status_code=400, detail="Service not found")
        for field, value in payload.items():
            if field == "name" and value:
                value = value.strip()
            setattr(item, field, value)
        await self.session.flush()
        loaded = await self.template_repo.get_by_id(item.id)
        return self._template_read(loaded)  # type: ignore[arg-type]

    async def delete_result_template(self, template_id: str) -> PathologyResultTemplateRead:
        item = await self.template_repo.get_by_id(template_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=404, detail="Template not found")
        item.is_active = False
        await self.session.flush()
        return self._template_read(item)


class PathologyOrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.bill_repo = PathologyBillRepository(session)
        self.patient_repo = PatientRepository(session)
        self.map_repo = PathologyServiceParameterRepository(session)
        self.range_repo = PathologyNormalRangeRepository(session)
        self.param_repo = PathologyParameterRepository(session)

    async def create_order_for_bill(
        self,
        *,
        bill_id: str,
        patient_id: str,
        order_date: date,
        sample_date: date | None,
        sample_no: str | None,
        pathologist_id: str | None,
    ) -> PathologyOrder:
        bill = await self.bill_repo.get_lines_only(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        patient = await self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        order = PathologyOrder(
            bill_id=bill_id,
            patient_id=patient_id,
            order_date=order_date,
            sample_date=sample_date or order_date,
            sample_no=sample_no,
            status=ORDER_STATUS_BILLED,
            pathologist_id=pathologist_id,
            is_active=True,
        )
        self.session.add(order)
        await self.session.flush()

        active_lines = sorted(
            [ln for ln in bill.lines if ln.is_active],
            key=lambda ln: getattr(ln, "sort_order", 0),
        )
        await self._populate_results(order, active_lines, patient, existing={})
        await self.session.flush()
        return order

    @staticmethod
    def _result_fields(
        line,
        param,
        rng,
        existing: dict,
    ) -> tuple[str | None, bool, str]:
        """Resolve (result_value, is_abnormal, status) for a result row.

        Front-desk entered values on the bill line win; any previously entered
        value (e.g. from the Work List) is preserved when the line has none.
        Numeric values are auto-flagged abnormal against the matched range, and a
        manual abnormal flag set on the line is always respected.
        """
        value = (getattr(line, "result_value", None) or "").strip() or None
        abnormal = bool(getattr(line, "is_abnormal", False))
        key = (line.service_id, getattr(param, "id", None))
        if value is None and key in existing:
            value, abnormal = existing[key]
        if (
            value is not None
            and not abnormal
            and param is not None
            and (param.data_type or "numeric") == "numeric"
        ):
            try:
                abnormal = is_value_abnormal(Decimal(value), rng)
            except (InvalidOperation, ValueError):
                abnormal = False
        status = "entered" if value else "pending"
        return value, abnormal, status

    async def _populate_results(
        self,
        order: PathologyOrder,
        lines: list,
        patient,
        existing: dict,
    ) -> None:
        # Always follow bill-line sort_order (bundle member order from Test Profile).
        ordered_lines = sorted(lines, key=lambda ln: getattr(ln, "sort_order", 0))
        sort_index = 0
        for line in ordered_lines:
            # Bundle/package header line carries the price only — no result rows.
            if getattr(line, "is_panel_parent", False) or not line.service_id:
                continue
            # Robust guard: a bundle service (has members) never produces results,
            # even if the UI failed to flag the header line.
            if await self._is_bundle_service(line.service_id):
                continue

            # A leaf test's own analyte components (self-mapping or multi-component).
            mappings = await self.map_repo.list_for_service(line.service_id)
            if mappings:
                for mapping in mappings:
                    param = mapping.parameter
                    rng = await self.range_repo.find_for_patient(param.id, patient)
                    unit_id = param.unit_id or (rng.unit_id if rng else None)
                    unit_name = await self._safe_unit_name(param, rng)
                    ref_text = (
                        line.reference_range_text
                        if getattr(line, "reference_range_text", None)
                        else format_range_text(rng, unit_name)
                    )
                    sub_service_id = await self._service_id_for_parameter(param)
                    value, abnormal, status = self._result_fields(line, param, rng, existing)
                    self.session.add(
                        PathologyResult(
                            order_id=order.id,
                            bill_line_id=line.id,
                            parameter_id=param.id,
                            service_id=sub_service_id or line.service_id,
                            unit_id=unit_id,
                            reference_range_text=ref_text,
                            result_value=value,
                            is_abnormal=abnormal,
                            status=status,
                            sort_order=sort_index,
                            is_active=True,
                        )
                    )
                    sort_index += 1
                continue

            # No component mapping: resolve the single analyte by code (legacy panel
            # members share the test's code), else fall back to a text result.
            param = await self.param_repo.get_by_code(line.service_code)
            if param:
                rng = await self.range_repo.find_for_patient(param.id, patient)
                unit_id = param.unit_id or (rng.unit_id if rng else None)
                unit_name = await self._safe_unit_name(param, rng)
                ref_text = line.reference_range_text or format_range_text(rng, unit_name)
                value, abnormal, status = self._result_fields(line, param, rng, existing)
                self.session.add(
                    PathologyResult(
                        order_id=order.id,
                        bill_line_id=line.id,
                        parameter_id=param.id,
                        service_id=line.service_id,
                        unit_id=unit_id,
                        reference_range_text=ref_text,
                        result_value=value,
                        is_abnormal=abnormal,
                        status=status,
                        sort_order=sort_index,
                        is_active=True,
                    )
                )
            else:
                fallback = await self._fallback_parameter(line.service_name, line.service_code)
                value, abnormal, status = self._result_fields(line, fallback, None, existing)
                self.session.add(
                    PathologyResult(
                        order_id=order.id,
                        bill_line_id=line.id,
                        parameter_id=fallback.id,
                        service_id=line.service_id,
                        reference_range_text=line.reference_range_text or "—",
                        result_value=value,
                        is_abnormal=abnormal,
                        status=status,
                        sort_order=sort_index,
                        is_active=True,
                    )
                )
            sort_index += 1

    async def resync_order_results(self, bill_id: str) -> None:
        """Rebuild an order's result rows from the bill's current active lines.

        Used after a bill is modified so the report reflects the edited tests and
        any result values entered on the bill, while preserving values already
        captured for unchanged tests.
        """
        result = await self.session.execute(
            select(PathologyOrder)
            .options(
                selectinload(PathologyOrder.patient),
                selectinload(PathologyOrder.results),
            )
            .where(PathologyOrder.bill_id == bill_id)
            .where(PathologyOrder.is_active.is_(True))
            .execution_options(populate_existing=True)
        )
        order = result.scalar_one_or_none()
        if not order:
            return
        bill_result = await self.session.execute(
            select(PathologyBill)
            .options(selectinload(PathologyBill.lines))
            .where(PathologyBill.id == bill_id)
            .execution_options(populate_existing=True)
        )
        bill = bill_result.scalar_one_or_none()
        if not bill:
            return

        existing: dict = {}
        for row in order.results:
            if not row.is_active:
                continue
            if row.result_value:
                existing[(row.service_id, row.parameter_id)] = (row.result_value, row.is_abnormal)
            row.is_active = False

        active_lines = sorted(
            [ln for ln in bill.lines if ln.is_active],
            key=lambda ln: getattr(ln, "sort_order", 0),
        )
        await self._populate_results(order, active_lines, order.patient, existing)
        await self.session.flush()

    async def _is_bundle_service(self, service_id: str | None) -> bool:
        if not service_id:
            return False
        row = (
            await self.session.execute(
                select(PathologyServiceMember.id)
                .where(PathologyServiceMember.bundle_service_id == service_id)
                .where(PathologyServiceMember.is_active.is_(True))
                .limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _safe_unit_name(self, param, rng) -> str | None:
        """Resolve unit name without triggering async lazy-loads."""
        unit_id = None
        if rng is not None and getattr(rng, "unit_id", None):
            unit_id = rng.unit_id
        elif param is not None and getattr(param, "unit_id", None):
            unit_id = param.unit_id
        if not unit_id:
            return None
        unit = await self.session.get(PathologyUnit, unit_id)
        return unit.name if unit else None

    async def _service_id_for_parameter(self, param: PathologyParameter) -> str | None:
        """Each legacy test uses the same code for service and parameter (P{cd})."""
        if not param.code:
            return None
        result = await self.session.execute(
            select(PatientServiceMaster.id)
            .where(PatientServiceMaster.code == param.code)
            .where(PatientServiceMaster.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def _fallback_parameter(self, name: str, code: str) -> PathologyParameter:
        param_code = f"T{code}"[:30]
        existing = await self.param_repo.get_by_code(param_code)
        if existing:
            return existing
        item = PathologyParameter(
            code=param_code,
            name=name[:200],
            data_type="text",
            is_active=True,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_order_by_bill(self, bill_id: str) -> PathologyOrderRead:
        order = await self._load_order(bill_id=bill_id)
        await self._sync_result_sort_orders(order)
        ranges_map = await self._ranges_by_parameter(order)
        return self._order_to_read(order, ranges_map=ranges_map)

    async def _sync_result_sort_orders(self, order: PathologyOrder) -> None:
        """Keep result.sort_order identical to bill-line order (bundle, then member)."""
        dirty = False
        for row in order.results or []:
            if not getattr(row, "is_active", True):
                continue
            line = getattr(row, "bill_line", None)
            if line is None:
                continue
            desired = int(getattr(line, "sort_order", 0) or 0)
            if int(getattr(row, "sort_order", 0) or 0) != desired:
                row.sort_order = desired
                dirty = True
        if dirty:
            await self.session.flush()

    async def _ranges_by_parameter(
        self, order: PathologyOrder
    ) -> dict[str, list[PathologyNormalRange]]:
        """All active reference ranges for every parameter used in the order."""
        param_ids = {r.parameter_id for r in order.results if r.is_active and r.parameter_id}
        if not param_ids:
            return {}
        rows = (
            await self.session.execute(
                select(PathologyNormalRange)
                .options(selectinload(PathologyNormalRange.unit))
                .where(PathologyNormalRange.parameter_id.in_(param_ids))
                .where(PathologyNormalRange.is_active.is_(True))
                .order_by(PathologyNormalRange.parameter_id, PathologyNormalRange.sort_order)
            )
        ).scalars().all()
        ranges_map: dict[str, list[PathologyNormalRange]] = {}
        for row in rows:
            ranges_map.setdefault(row.parameter_id, []).append(row)
        return ranges_map

    async def _load_order(self, *, bill_id: str) -> PathologyOrder:
        result = await self.session.execute(
            select(PathologyOrder)
            .options(
                selectinload(PathologyOrder.bill).selectinload(PathologyBill.lines),
                selectinload(PathologyOrder.patient),
                selectinload(PathologyOrder.pathologist),
                selectinload(PathologyOrder.results)
                .selectinload(PathologyResult.parameter)
                .selectinload(PathologyParameter.unit),
                selectinload(PathologyOrder.results).selectinload(PathologyResult.unit),
                selectinload(PathologyOrder.results).selectinload(PathologyResult.service),
                selectinload(PathologyOrder.results).selectinload(PathologyResult.bill_line),
            )
            .where(PathologyOrder.bill_id == bill_id)
            .where(PathologyOrder.is_active.is_(True))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Pathology order not found")
        return order

    def _result_to_read(
        self,
        row: PathologyResult,
        *,
        ranges_map: dict[str, list[PathologyNormalRange]] | None = None,
    ) -> PathologyResultRead:
        unit = row.unit or (row.parameter.unit if row.parameter else None)
        read = PathologyResultRead.model_validate(row)
        additional_ranges = []
        if ranges_map:
            param_ranges = ranges_map.get(row.parameter_id) or []
            # Only surface the age-group breakdown when there is more than one band;
            # a single all-ages range is already shown in the reference range column.
            if len(param_ranges) > 1:
                additional_ranges = reference_range_rows(
                    param_ranges,
                    fallback_unit_name=unit.name if unit else None,
                )
        line = getattr(row, "bill_line", None)
        panel_service_id = None
        panel_name = None
        bill_line_sort_order = 0
        if line is not None:
            bill_line_sort_order = int(getattr(line, "sort_order", 0) or 0)
            if getattr(line, "is_panel_parent", False):
                panel_service_id = getattr(line, "service_id", None)
                panel_name = getattr(line, "service_name", None)
            else:
                panel_service_id = getattr(line, "panel_service_id", None)
                panel_name = getattr(line, "panel_name", None)
        return read.model_copy(
            update={
                "parameter_code": row.parameter.code if row.parameter else None,
                "parameter_name": row.parameter.name if row.parameter else None,
                "service_code": row.service.code if row.service else None,
                "service_name": row.service.name if row.service else None,
                "unit_name": unit.name if unit else None,
                "method": row.parameter.method if row.parameter else None,
                "additional_ranges": additional_ranges,
                "bill_line_sort_order": bill_line_sort_order,
                "panel_service_id": panel_service_id,
                "panel_name": panel_name,
            }
        )

    def _order_to_read(
        self,
        order: PathologyOrder,
        *,
        ranges_map: dict[str, list[PathologyNormalRange]] | None = None,
    ) -> PathologyOrderRead:
        patient_name = None
        patient_no = None
        if order.patient:
            patient_no = order.patient.patient_no
            parts = [order.patient.first_name, order.patient.middle_name, order.patient.last_name]
            patient_name = " ".join(p for p in parts if p)
        read = PathologyOrderRead.model_validate(order)
        panel_group_order = self._panel_group_order_map(order.bill)
        active_results = self._sorted_results(order.results or [], panel_group_order)
        result_reads = []
        for row in active_results:
            item = self._result_to_read(row, ranges_map=ranges_map)
            panel_id = str(item.panel_service_id) if item.panel_service_id else ""
            if panel_id and panel_id in panel_group_order:
                group_order = panel_group_order[panel_id]
            else:
                group_order = int(item.bill_line_sort_order or item.sort_order or 0)
            result_reads.append(item.model_copy(update={"panel_group_order": int(group_order)}))
        return read.model_copy(
            update={
                "bill_no": order.bill.bill_no if order.bill else None,
                "patient_no": patient_no,
                "patient_name": patient_name,
                "pathologist_name": order.pathologist.full_name if order.pathologist else None,
                "results": result_reads,
            }
        )

    @staticmethod
    def _panel_group_order_map(bill) -> dict[str, int]:
        """Bundle appearance order on the bill (parent line sort_order)."""
        groups: dict[str, int] = {}
        if bill is None:
            return groups
        lines = list(getattr(bill, "lines", None) or [])
        for line in sorted(lines, key=lambda ln: int(getattr(ln, "sort_order", 0) or 0)):
            if not getattr(line, "is_active", True):
                continue
            order = int(getattr(line, "sort_order", 0) or 0)
            if getattr(line, "is_panel_parent", False) and getattr(line, "service_id", None):
                groups[str(line.service_id)] = order
            elif getattr(line, "panel_service_id", None):
                groups.setdefault(str(line.panel_service_id), order)
        return groups

    @staticmethod
    def _sorted_results(results: list, panel_group_order: dict[str, int] | None = None) -> list:
        """Order by bundle (panel group), then member order within the bundle."""
        active = [r for r in results if getattr(r, "is_active", True)]
        groups = panel_group_order or {}

        def _key(row) -> tuple:
            line = getattr(row, "bill_line", None)
            result_order = int(getattr(row, "sort_order", 0) or 0)
            if line is not None:
                line_order = int(getattr(line, "sort_order", 0) or 0)
                if getattr(line, "is_panel_parent", False):
                    panel_id = getattr(line, "service_id", None)
                else:
                    panel_id = getattr(line, "panel_service_id", None)
            else:
                # Fallback when bill_line was not eager-loaded.
                line_order = result_order
                panel_id = None
            panel_key = str(panel_id) if panel_id else ""
            if panel_key and panel_key in groups:
                group_order = groups[panel_key]
            else:
                group_order = line_order
            created = getattr(row, "created_at", None)
            created_ts = created.timestamp() if created is not None else 0.0
            return (
                int(group_order),
                int(line_order),
                int(result_order),
                created_ts,
                str(getattr(row, "id", "")),
            )

        return sorted(active, key=_key)

    async def update_results(self, bill_id: str, data: PathologyResultsUpdate) -> PathologyOrderRead:
        order = await self._load_order(bill_id=bill_id)
        patient = order.patient
        by_id = {entry.id: entry for entry in data.results}
        for row in [r for r in order.results if r.is_active]:
            entry = by_id.get(row.id)
            if not entry:
                continue
            value = (entry.result_value or "").strip()
            row.result_value = value or None
            row.result_numeric = None
            row.is_abnormal = False
            # Keep result sort_order aligned with bill-line order (bundle, then member).
            line = getattr(row, "bill_line", None)
            if line is not None:
                row.sort_order = int(getattr(line, "sort_order", 0) or 0)
            if value:
                rng = await self.range_repo.find_for_patient(row.parameter_id, patient)
                if row.parameter and row.parameter.data_type == "numeric":
                    try:
                        numeric = Decimal(value)
                        row.result_numeric = numeric
                        row.is_abnormal = is_value_abnormal(numeric, rng)
                    except InvalidOperation:
                        pass
                row.status = "entered"
                if not row.reference_range_text or row.reference_range_text == "—":
                    row.reference_range_text = format_range_text(rng)
            else:
                row.status = "pending"
        # Only two statuses exist (Billed, Report Ready); result entry alone
        # never advances the status — that only happens via authorize_order.
        await self.session.flush()
        # Full reload so bill lines + sort order are always present after save.
        return await self.get_order_by_bill(bill_id)

    async def authorize_order(self, bill_id: str) -> PathologyOrderRead:
        order = await self._load_order(bill_id=bill_id)
        pending = [r for r in order.results if r.is_active and not r.result_value]
        if not can_authorize(len(pending)):
            raise HTTPException(status_code=400, detail="Enter all results before authorization")
        order.status = ORDER_STATUS_REPORT_READY
        order.authorized_at = datetime.now(timezone.utc)
        await self.session.flush()
        return await self.get_order_by_bill(bill_id)

    async def work_list(self, bill_date: date | None = None) -> list[PathologyWorkListItem]:
        from app.models.pathology_bill import PathologyBill

        stmt = (
            select(PathologyOrder)
            .join(PathologyBill, PathologyOrder.bill_id == PathologyBill.id)
            .options(
                selectinload(PathologyOrder.bill).selectinload(PathologyBill.lines),
                selectinload(PathologyOrder.patient),
                selectinload(PathologyOrder.results),
            )
            .where(PathologyOrder.is_active.is_(True))
            .where(PathologyBill.is_active.is_(True))
            .order_by(PathologyOrder.created_at.desc())
            .limit(200)
        )
        if bill_date:
            stmt = stmt.where(PathologyBill.bill_date == bill_date)
        result = await self.session.execute(stmt)
        orders = list(result.scalars().unique().all())
        items: list[PathologyWorkListItem] = []
        for order in orders:
            bill = order.bill
            if not bill or not bill.is_active:
                continue
            patient_name = None
            patient_no = None
            if order.patient:
                patient_no = order.patient.patient_no
                parts = [order.patient.first_name, order.patient.middle_name, order.patient.last_name]
                patient_name = " ".join(p for p in parts if p)
            active_results = [r for r in (order.results or []) if r.is_active]
            pending = len(
                [r for r in active_results if (r.status or "") == "pending" or not r.result_value]
            )
            # Count result rows when present; otherwise count billable lines only
            # (exclude bundle header lines that never produce results).
            if active_results:
                test_count = len(active_results)
            else:
                bill_lines = list(bill.lines or [])
                test_count = len(
                    [
                        ln
                        for ln in bill_lines
                        if getattr(ln, "is_active", True)
                        and not getattr(ln, "is_panel_parent", False)
                    ]
                )
            items.append(
                PathologyWorkListItem(
                    bill_id=str(bill.id),
                    bill_no=bill.bill_no,
                    bill_date=bill.bill_date,
                    patient_no=patient_no,
                    patient_name=patient_name,
                    order_id=str(order.id) if order.id else None,
                    order_status=order.status,
                    sample_no=order.sample_no,
                    test_count=test_count,
                    result_pending=pending,
                    net_amount=bill.net_amount if bill.net_amount is not None else 0,
                    referring_doctor=bill.referring_doctor,
                )
            )
        return items
