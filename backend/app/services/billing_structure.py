from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_structure import BillingStructureMapping
from app.repositories.billing_structure import BillingStructureRepository
from app.schemas.billing_structure import (
    BillingStructureCreate,
    BillingStructureDepartmentNode,
    BillingStructureRead,
    BillingStructureTreeNode,
    BillingStructureUpdate,
)
from app.schemas.billing_type import BillingTypeRead
from app.schemas.department import DepartmentRead
from app.schemas.procedure_type import ProcedureTypeRead


class BillingStructureService:
    def __init__(self, session: AsyncSession):
        self.repo = BillingStructureRepository(session)

    def _to_read_from_maps(
        self,
        mapping: BillingStructureMapping,
        billing_types: dict,
        departments: dict,
        procedure_types: dict,
    ) -> BillingStructureRead:
        bt = billing_types.get(mapping.billing_type_id)
        dept = departments.get(mapping.department_id)
        proc = procedure_types.get(mapping.procedure_type_id)
        return BillingStructureRead(
            id=mapping.id,
            billing_type_id=mapping.billing_type_id,
            department_id=mapping.department_id,
            procedure_type_id=mapping.procedure_type_id,
            billing_type_code=bt.code if bt else None,
            billing_type_name=bt.name if bt else None,
            department_code=dept.code if dept else None,
            department_name=dept.name if dept else None,
            procedure_type_code=proc.code if proc else None,
            procedure_type_name=proc.name if proc else None,
            sort_order=mapping.sort_order,
            is_active=mapping.is_active,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
        )

    async def _to_read(self, mapping: BillingStructureMapping) -> BillingStructureRead:
        bt = await self.repo.get_billing_type(mapping.billing_type_id)
        dept = await self.repo.get_department(mapping.department_id)
        proc = await self.repo.get_procedure_type(mapping.procedure_type_id)
        return BillingStructureRead(
            id=mapping.id,
            billing_type_id=mapping.billing_type_id,
            department_id=mapping.department_id,
            procedure_type_id=mapping.procedure_type_id,
            billing_type_code=bt.code if bt else None,
            billing_type_name=bt.name if bt else None,
            department_code=dept.code if dept else None,
            department_name=dept.name if dept else None,
            procedure_type_code=proc.code if proc else None,
            procedure_type_name=proc.name if proc else None,
            sort_order=mapping.sort_order,
            is_active=mapping.is_active,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
        )

    async def list_mappings(self) -> list[BillingStructureRead]:
        items = await self.repo.list_active()
        if not items:
            return []
        billing_types, departments, procedure_types = await self.repo.lookup_master_maps()
        return [
            self._to_read_from_maps(item, billing_types, departments, procedure_types)
            for item in items
        ]

    async def get_tree(self) -> list[BillingStructureTreeNode]:
        mappings = await self.repo.list_active()
        if not mappings:
            return []
        billing_types, departments, procedure_types = await self.repo.lookup_master_maps()
        tree: dict[str, dict] = {}

        for mapping in mappings:
            bt = billing_types.get(mapping.billing_type_id)
            dept = departments.get(mapping.department_id)
            proc = procedure_types.get(mapping.procedure_type_id)
            if not bt or not dept or not proc:
                continue

            bt_entry = tree.setdefault(
                bt.id,
                {"billing_type": BillingTypeRead.model_validate(bt), "departments": {}},
            )
            dept_entry = bt_entry["departments"].setdefault(
                dept.id,
                {"department": DepartmentRead.model_validate(dept), "procedure_types": []},
            )
            proc_read = ProcedureTypeRead.model_validate(proc)
            existing_ids = {p.id for p in dept_entry["procedure_types"]}
            if proc_read.id not in existing_ids:
                dept_entry["procedure_types"].append(proc_read)

        result: list[BillingStructureTreeNode] = []
        for entry in tree.values():
            departments = [
                BillingStructureDepartmentNode(
                    department=dept_data["department"],
                    procedure_types=sorted(
                        dept_data["procedure_types"], key=lambda p: (p.sort_order, p.name)
                    ),
                )
                for dept_data in entry["departments"].values()
            ]
            departments.sort(key=lambda d: (d.department.sort_order, d.department.name))
            result.append(
                BillingStructureTreeNode(
                    billing_type=entry["billing_type"],
                    departments=departments,
                )
            )
        result.sort(key=lambda n: (n.billing_type.sort_order, n.billing_type.name))
        return result

    async def create_mapping(self, data: BillingStructureCreate) -> BillingStructureRead:
        bt = await self.repo.get_billing_type(data.billing_type_id)
        dept = await self.repo.get_department(data.department_id)
        proc = await self.repo.get_procedure_type(data.procedure_type_id)
        if not bt or not bt.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid billing type")
        if not dept or not dept.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department")
        if not proc or not proc.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid procedure type")

        existing = await self.repo.get_combo(
            data.billing_type_id, data.department_id, data.procedure_type_id
        )
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This billing structure mapping already exists",
                )
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return await self._to_read(existing)

        item = BillingStructureMapping(
            billing_type_id=data.billing_type_id,
            department_id=data.department_id,
            procedure_type_id=data.procedure_type_id,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return await self._to_read(item)

    async def update_mapping(
        self, mapping_id: str, data: BillingStructureUpdate
    ) -> BillingStructureRead:
        item = await self.repo.get_by_id(mapping_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return await self._to_read(item)

    async def delete_mapping(self, mapping_id: str) -> BillingStructureRead:
        item = await self.repo.get_by_id(mapping_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return await self._to_read(item)
