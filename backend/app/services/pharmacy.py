from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pharmacy import PharmacyCodeMaster, PharmacyGroupMapping, PharmacyItem, PharmacySupplier
from app.repositories.pharmacy import (
    PharmacyCodeMasterRepository,
    PharmacyGroupMappingRepository,
    PharmacyItemRepository,
    PharmacySupplierRepository,
)
from app.schemas.pharmacy import (
    PharmacyCodeMasterCreate,
    PharmacyCodeMasterRead,
    PharmacyCodeMasterUpdate,
    PharmacyGroupMappingCreate,
    PharmacyGroupMappingRead,
    PharmacyItemCreate,
    PharmacyItemRead,
    PharmacyItemUpdate,
    PharmacyMedicineSearchResult,
    PharmacySupplierCreate,
    PharmacySupplierRead,
    PharmacySupplierUpdate,
)


class PharmacyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.code_repo = PharmacyCodeMasterRepository(session)
        self.item_repo = PharmacyItemRepository(session)
        self.supplier_repo = PharmacySupplierRepository(session)
        self.group_repo = PharmacyGroupMappingRepository(session)

    async def list_code_masters(self, master_type: str) -> list[PharmacyCodeMasterRead]:
        items = await self.code_repo.list_active(master_type.upper())
        return [PharmacyCodeMasterRead.model_validate(item) for item in items]

    async def create_code_master(self, data: PharmacyCodeMasterCreate) -> PharmacyCodeMasterRead:
        master_type = data.master_type.strip().upper()
        code = data.code.strip().upper()
        existing = await self.code_repo.get_by_code(master_type, code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Code already exists for this master type",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.session.flush()
            await self.session.refresh(existing)
            return PharmacyCodeMasterRead.model_validate(existing)

        item = PharmacyCodeMaster(
            master_type=master_type,
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyCodeMasterRead.model_validate(item)

    async def update_code_master(
        self, record_id: str, data: PharmacyCodeMasterUpdate
    ) -> PharmacyCodeMasterRead:
        item = await self.code_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyCodeMasterRead.model_validate(item)

    async def delete_code_master(self, record_id: str) -> PharmacyCodeMasterRead:
        item = await self.code_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        item.is_active = False
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyCodeMasterRead.model_validate(item)

    async def list_items(self, item_type: str) -> list[PharmacyItemRead]:
        items = await self.item_repo.list_active(item_type.upper())
        return [PharmacyItemRead.model_validate(item) for item in items]

    async def search_medicines(
        self, query: str, item_type: str = "MD", limit: int = 25
    ) -> list[PharmacyMedicineSearchResult]:
        from app.repositories.pharmacy_bills import purchased_qty_by_item, sold_qty_by_item

        items = await self.item_repo.search(item_type.upper(), query, limit)
        if not items:
            return []
        purchased = await purchased_qty_by_item(self.session)
        sold = await sold_qty_by_item(self.session)
        results: list[PharmacyMedicineSearchResult] = []
        for item in items:
            stock_qty = purchased.get(item.id, 0) - sold.get(item.id, 0)
            results.append(
                PharmacyMedicineSearchResult(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    generic_name=item.generic_name,
                    unit=item.unit,
                    sale_rate=item.sale_rate,
                    mrp=item.mrp,
                    schedule=item.schedule,
                    stock_qty=stock_qty,
                )
            )
        return results

    async def create_item(self, data: PharmacyItemCreate) -> PharmacyItemRead:
        item_type = data.item_type.strip().upper()
        code = data.code.strip().upper()
        existing = await self.item_repo.get_by_code(item_type, code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Item code already exists for this type",
                )
            self._apply_item_fields(existing, data)
            existing.is_active = True
            await self.session.flush()
            await self.session.refresh(existing)
            return PharmacyItemRead.model_validate(existing)

        item = PharmacyItem(item_type=item_type, code=code, name=data.name.strip())
        self._apply_item_fields(item, data)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyItemRead.model_validate(item)

    async def update_item(self, record_id: str, data: PharmacyItemUpdate) -> PharmacyItemRead:
        item = await self.item_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            elif field == "generic_name" and value is not None:
                value = value.strip() or None
            setattr(item, field, value)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyItemRead.model_validate(item)

    async def delete_item(self, record_id: str) -> PharmacyItemRead:
        item = await self.item_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        item.is_active = False
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacyItemRead.model_validate(item)

    async def list_suppliers(self) -> list[PharmacySupplierRead]:
        items = await self.supplier_repo.list_active()
        return [PharmacySupplierRead.model_validate(item) for item in items]

    async def create_supplier(self, data: PharmacySupplierCreate) -> PharmacySupplierRead:
        code = data.code.strip().upper()
        existing = await self.supplier_repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Supplier code already exists",
                )
            self._apply_supplier_fields(existing, data)
            existing.is_active = True
            await self.session.flush()
            await self.session.refresh(existing)
            return PharmacySupplierRead.model_validate(existing)

        item = PharmacySupplier(code=code, name=data.name.strip())
        self._apply_supplier_fields(item, data)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacySupplierRead.model_validate(item)

    async def update_supplier(self, record_id: str, data: PharmacySupplierUpdate) -> PharmacySupplierRead:
        item = await self.supplier_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacySupplierRead.model_validate(item)

    async def delete_supplier(self, record_id: str) -> PharmacySupplierRead:
        item = await self.supplier_repo.get_by_id(record_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        item.is_active = False
        await self.session.flush()
        await self.session.refresh(item)
        return PharmacySupplierRead.model_validate(item)

    async def list_group_mappings(self, group_id: str) -> list[PharmacyGroupMappingRead]:
        items = await self.group_repo.list_by_group(group_id)
        return [PharmacyGroupMappingRead.model_validate(item) for item in items]

    async def create_group_mapping(self, data: PharmacyGroupMappingCreate) -> PharmacyGroupMappingRead:
        group = await self.code_repo.get_by_id(data.group_id)
        if not group or not group.is_active or group.master_type != "MG":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid medicine group")
        item = await self.item_repo.get_by_id(data.item_id)
        if not item or not item.is_active or item.item_type != "MD":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid medicine item")
        existing = await self.group_repo.get_mapping(data.group_id, data.item_id)
        if existing:
            return PharmacyGroupMappingRead.model_validate(existing)
        mapping = PharmacyGroupMapping(group_id=data.group_id, item_id=data.item_id)
        self.session.add(mapping)
        await self.session.flush()
        await self.session.refresh(mapping)
        return PharmacyGroupMappingRead.model_validate(mapping)

    async def delete_group_mapping(self, mapping_id: str) -> PharmacyGroupMappingRead:
        mapping = await self.group_repo.get_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
        await self.session.delete(mapping)
        await self.session.flush()
        return PharmacyGroupMappingRead.model_validate(mapping)

    @staticmethod
    def _apply_item_fields(item: PharmacyItem, data: PharmacyItemCreate) -> None:
        item.name = data.name.strip()
        item.generic_name = (data.generic_name or "").strip() or None
        item.unit = (data.unit or "").strip() or None
        item.mrp = data.mrp
        item.purchase_rate = data.purchase_rate
        item.sale_rate = data.sale_rate
        item.manufacturer_id = data.manufacturer_id
        item.category_id = data.category_id
        item.schedule = (data.schedule or "").strip() or None
        item.reorder_level = data.reorder_level
        item.sort_order = data.sort_order

    @staticmethod
    def _apply_supplier_fields(item: PharmacySupplier, data: PharmacySupplierCreate) -> None:
        item.name = data.name.strip()
        item.contact_person = (data.contact_person or "").strip() or None
        item.phone = (data.phone or "").strip() or None
        item.email = (data.email or "").strip() or None
        item.address = (data.address or "").strip() or None
        item.gst_number = (data.gst_number or "").strip() or None
        item.sort_order = data.sort_order
