from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_package import BillingPackage, BillingPackageItem
from app.repositories.billing_package import BillingPackageRepository
from app.repositories.patient_service_master import PatientServiceMasterRepository
from app.schemas.billing_package import (
    BillingPackageCreate,
    BillingPackageDetailRead,
    BillingPackageItemCreate,
    BillingPackageItemRead,
    BillingPackageItemsReplace,
    BillingPackageRead,
    BillingPackageUpdate,
)


class BillingPackageService:
    def __init__(self, session: AsyncSession):
        self.repo = BillingPackageRepository(session)
        self.service_repo = PatientServiceMasterRepository(session)

    def _item_to_read(self, item: BillingPackageItem) -> BillingPackageItemRead:
        read = BillingPackageItemRead.model_validate(item)
        if item.service:
            read = read.model_copy(
                update={
                    "service_code": item.service.code,
                    "service_name": item.service.name,
                    "service_rate": item.service.rate,
                }
            )
        return read

    def _to_read(self, package: BillingPackage, item_count: int = 0) -> BillingPackageRead:
        read = BillingPackageRead.model_validate(package)
        return read.model_copy(update={"item_count": item_count})

    def _to_detail(self, package: BillingPackage) -> BillingPackageDetailRead:
        active_items = [item for item in package.items if item.is_active]
        base = self._to_read(package, len(active_items))
        return BillingPackageDetailRead(
            **base.model_dump(),
            items=[self._item_to_read(item) for item in active_items],
        )

    async def list_packages(self) -> list[BillingPackageRead]:
        rows = await self.repo.list_active()
        return [self._to_read(package, int(item_count)) for package, item_count in rows]

    async def get_package(self, package_id: str) -> BillingPackageDetailRead:
        package = await self.repo.get_with_items(package_id)
        if not package or not package.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        return self._to_detail(package)

    async def create_package(self, data: BillingPackageCreate) -> BillingPackageRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Package code already exists",
                )
            existing.name = data.name.strip()
            existing.package_total = data.package_total
            existing.description = data.description
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return self._to_read(existing, 0)

        item = BillingPackage(
            code=code,
            name=data.name.strip(),
            package_total=data.package_total,
            description=data.description,
            sort_order=data.sort_order,
            is_active=True,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return self._to_read(item, 0)

    async def update_package(
        self, package_id: str, data: BillingPackageUpdate
    ) -> BillingPackageRead:
        package = await self.repo.get_with_items(package_id)
        if not package or not package.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(package, field, value)
        await self.repo.session.flush()
        refreshed = await self.repo.get_with_items(package_id)
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        active_count = sum(1 for item in refreshed.items if item.is_active)
        return self._to_read(refreshed, active_count)

    async def delete_package(self, package_id: str) -> BillingPackageRead:
        package = await self.repo.get_by_id(package_id)
        if not package or not package.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        package.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(package)
        return self._to_read(package, 0)

    async def _validate_service_ids(self, items: list[BillingPackageItemCreate]) -> None:
        seen: set[str] = set()
        for entry in items:
            if entry.service_id in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate service in package items",
                )
            seen.add(entry.service_id)
            service = await self.service_repo.get_by_id(entry.service_id)
            if not service or not service.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service not found: {entry.service_id}",
                )

    async def replace_items(
        self, package_id: str, data: BillingPackageItemsReplace
    ) -> BillingPackageDetailRead:
        package = await self.repo.get_with_items(package_id)
        if not package or not package.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        await self._validate_service_ids(data.items)

        for item in package.items:
            item.is_active = False

        for index, entry in enumerate(data.items):
            existing = next(
                (row for row in package.items if row.service_id == entry.service_id),
                None,
            )
            if existing:
                existing.quantity = entry.quantity
                existing.rate_override = entry.rate_override
                existing.sort_order = entry.sort_order if entry.sort_order else index
                existing.is_active = True
            else:
                package.items.append(
                    BillingPackageItem(
                        package_id=package.id,
                        service_id=entry.service_id,
                        quantity=entry.quantity,
                        rate_override=entry.rate_override,
                        sort_order=entry.sort_order if entry.sort_order else index,
                        is_active=True,
                    )
                )

        await self.repo.session.flush()
        refreshed = await self.repo.get_with_items(package_id)
        return self._to_detail(refreshed)  # type: ignore[arg-type]

    async def add_item(
        self, package_id: str, data: BillingPackageItemCreate
    ) -> BillingPackageDetailRead:
        return await self.replace_items(
            package_id,
            BillingPackageItemsReplace(
                items=[
                    *(await self._current_items_payload(package_id)),
                    data,
                ]
            ),
        )

    async def _current_items_payload(self, package_id: str) -> list[BillingPackageItemCreate]:
        package = await self.repo.get_with_items(package_id)
        if not package:
            return []
        return [
            BillingPackageItemCreate(
                service_id=item.service_id,
                quantity=item.quantity,
                rate_override=Decimal(str(item.rate_override)) if item.rate_override is not None else None,
                sort_order=item.sort_order,
            )
            for item in package.items
            if item.is_active
        ]

    async def remove_item(self, package_id: str, item_id: str) -> BillingPackageDetailRead:
        package = await self.repo.get_with_items(package_id)
        if not package or not package.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
        target = next((row for row in package.items if row.id == item_id), None)
        if not target or not target.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package item not found")
        target.is_active = False
        await self.repo.session.flush()
        refreshed = await self.repo.get_with_items(package_id)
        return self._to_detail(refreshed)  # type: ignore[arg-type]
