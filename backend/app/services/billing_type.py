from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_type import BillingType
from app.repositories.billing_type import BillingTypeRepository
from app.schemas.billing_type import BillingTypeCreate, BillingTypeRead, BillingTypeUpdate


class BillingTypeService:
    def __init__(self, session: AsyncSession):
        self.repo = BillingTypeRepository(session)

    async def list_billing_types(self) -> list[BillingTypeRead]:
        items = await self.repo.list_active()
        return [BillingTypeRead.model_validate(item) for item in items]

    async def get_billing_type(self, billing_type_id: str) -> BillingTypeRead:
        item = await self.repo.get_by_id(billing_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing type not found")
        return BillingTypeRead.model_validate(item)

    async def create_billing_type(self, data: BillingTypeCreate) -> BillingTypeRead:
        code = data.code.strip().upper()
        existing = await self.repo.get_by_code(code)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Billing type code already exists",
                )
            existing.name = data.name.strip()
            existing.sort_order = data.sort_order
            existing.is_active = True
            await self.repo.session.flush()
            await self.repo.session.refresh(existing)
            return BillingTypeRead.model_validate(existing)

        item = BillingType(
            code=code,
            name=data.name.strip(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        self.repo.session.add(item)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return BillingTypeRead.model_validate(item)

    async def update_billing_type(
        self, billing_type_id: str, data: BillingTypeUpdate
    ) -> BillingTypeRead:
        item = await self.repo.get_by_id(billing_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing type not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(item, field, value)
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return BillingTypeRead.model_validate(item)

    async def delete_billing_type(self, billing_type_id: str) -> BillingTypeRead:
        item = await self.repo.get_by_id(billing_type_id)
        if not item or not item.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing type not found")
        item.is_active = False
        await self.repo.session.flush()
        await self.repo.session.refresh(item)
        return BillingTypeRead.model_validate(item)
