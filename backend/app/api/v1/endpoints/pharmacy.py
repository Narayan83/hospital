from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.pharmacy import (
    PharmacyCodeMasterCreate,
    PharmacyCodeMasterRead,
    PharmacyCodeMasterUpdate,
    PharmacyGroupMappingCreate,
    PharmacyGroupMappingRead,
    PharmacyIndentCreate,
    PharmacyItemCreate,
    PharmacyItemRead,
    PharmacyItemUpdate,
    PharmacyLastBillInfo,
    PharmacyMedicineSearchResult,
    PharmacyPurchaseBillCreate,
    PharmacyPurchaseBillRead,
    PharmacySalesRegisterRow,
    PharmacySalesSummaryRow,
    PharmacySaleBillCreate,
    PharmacySaleBillRead,
    PharmacyScheduleHRow,
    PharmacyStockLookup,
    PharmacyStockRow,
    PharmacySupplierCreate,
    PharmacySupplierRead,
    PharmacySupplierUpdate,
)
from app.services.pharmacy import PharmacyService
from app.services.pharmacy_bills import PharmacyBillService
router = APIRouter()


@router.get("/code-masters", response_model=list[PharmacyCodeMasterRead])
async def list_code_masters(
    master_type: str = Query(..., min_length=1, max_length=10),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).list_code_masters(master_type)


@router.post("/code-masters", response_model=PharmacyCodeMasterRead, status_code=201)
async def create_code_master(
    data: PharmacyCodeMasterCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).create_code_master(data)


@router.patch("/code-masters/{record_id}", response_model=PharmacyCodeMasterRead)
async def update_code_master(
    record_id: str,
    data: PharmacyCodeMasterUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).update_code_master(record_id, data)


@router.delete("/code-masters/{record_id}", response_model=PharmacyCodeMasterRead)
async def delete_code_master(
    record_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).delete_code_master(record_id)


@router.get("/items", response_model=list[PharmacyItemRead])
async def list_items(
    item_type: str = Query(..., min_length=1, max_length=10),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).list_items(item_type)


@router.get("/items/search", response_model=list[PharmacyMedicineSearchResult])
async def search_items(
    q: str = Query(..., min_length=1, max_length=100),
    item_type: str = Query("MD", min_length=1, max_length=10),
    limit: int = Query(25, ge=1, le=50),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).search_medicines(q, item_type, limit)


@router.post("/items", response_model=PharmacyItemRead, status_code=201)
async def create_item(
    data: PharmacyItemCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).create_item(data)


@router.patch("/items/{record_id}", response_model=PharmacyItemRead)
async def update_item(
    record_id: str,
    data: PharmacyItemUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).update_item(record_id, data)


@router.delete("/items/{record_id}", response_model=PharmacyItemRead)
async def delete_item(
    record_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).delete_item(record_id)


@router.get("/suppliers", response_model=list[PharmacySupplierRead])
async def list_suppliers(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).list_suppliers()


@router.post("/suppliers", response_model=PharmacySupplierRead, status_code=201)
async def create_supplier(
    data: PharmacySupplierCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).create_supplier(data)


@router.patch("/suppliers/{record_id}", response_model=PharmacySupplierRead)
async def update_supplier(
    record_id: str,
    data: PharmacySupplierUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).update_supplier(record_id, data)


@router.delete("/suppliers/{record_id}", response_model=PharmacySupplierRead)
async def delete_supplier(
    record_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).delete_supplier(record_id)


@router.get("/group-mappings", response_model=list[PharmacyGroupMappingRead])
async def list_group_mappings(
    group_id: str = Query(..., min_length=1),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).list_group_mappings(group_id)


@router.post("/group-mappings", response_model=PharmacyGroupMappingRead, status_code=201)
async def create_group_mapping(
    data: PharmacyGroupMappingCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).create_group_mapping(data)


@router.delete("/group-mappings/{mapping_id}", response_model=PharmacyGroupMappingRead)
async def delete_group_mapping(
    mapping_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyService(session).delete_group_mapping(mapping_id)


@router.post("/sale-bills", response_model=PharmacySaleBillRead, status_code=201)
async def create_sale_bill(
    data: PharmacySaleBillCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).create_sale_bill(data)


@router.get("/sale-bills/last-info", response_model=PharmacyLastBillInfo)
async def last_sale_bill_info(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).last_sale_bill_info()


@router.get("/stock-lookup", response_model=PharmacyStockLookup)
async def stock_lookup(
    code: str = Query(..., min_length=1, max_length=30),
    item_type: str = Query("MD", min_length=1, max_length=10),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).stock_lookup(code, item_type)


@router.get("/sale-bills/{bill_id}", response_model=PharmacySaleBillRead)
async def get_sale_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).get_sale_bill(bill_id)


@router.post("/purchase-bills", response_model=PharmacyPurchaseBillRead, status_code=201)
async def create_purchase_bill(
    data: PharmacyPurchaseBillCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).create_purchase_bill(data)


@router.post("/purchase-returns", response_model=PharmacyPurchaseBillRead, status_code=201)
async def create_purchase_return(
    data: PharmacyPurchaseBillCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data.bill_kind = "return"
    return await PharmacyBillService(session).create_purchase_bill(data)


@router.post("/indents", response_model=PharmacySaleBillRead, status_code=201)
async def create_medicine_indent(
    data: PharmacyIndentCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).create_indent(data)


@router.get("/purchase-bills/{bill_id}", response_model=PharmacyPurchaseBillRead)
async def get_purchase_bill(
    bill_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).get_purchase_bill(bill_id)


@router.get("/reports/sales-register", response_model=list[PharmacySalesRegisterRow])
async def sales_register(
    from_date: date = Query(...),
    to_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).sales_register(from_date, to_date)


@router.get("/reports/sales-summary", response_model=list[PharmacySalesSummaryRow])
async def sales_summary(
    from_date: date = Query(...),
    to_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).sales_summary(from_date, to_date)


@router.get("/reports/schedule-h", response_model=list[PharmacyScheduleHRow])
async def schedule_h_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).schedule_h_report(from_date, to_date)


@router.get("/reports/stock", response_model=list[PharmacyStockRow])
async def stock_report(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PharmacyBillService(session).consolidated_stock_report()
