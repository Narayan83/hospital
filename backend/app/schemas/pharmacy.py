from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PharmacyCodeMasterRead(ORMModel):
    id: str
    master_type: str
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PharmacyCodeMasterCreate(BaseModel):
    master_type: str = Field(..., min_length=1, max_length=10)
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=150)
    sort_order: int = 0
    is_active: bool = True


class PharmacyCodeMasterUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    sort_order: int | None = None
    is_active: bool | None = None


class PharmacyItemRead(ORMModel):
    id: str
    item_type: str
    code: str
    name: str
    generic_name: str | None
    unit: str | None
    mrp: Decimal | None
    purchase_rate: Decimal | None
    sale_rate: Decimal | None
    manufacturer_id: str | None
    category_id: str | None
    schedule: str | None
    reorder_level: int | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PharmacyItemCreate(BaseModel):
    item_type: str = Field(..., min_length=1, max_length=10)
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=200)
    generic_name: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=30)
    mrp: Decimal | None = None
    purchase_rate: Decimal | None = None
    sale_rate: Decimal | None = None
    manufacturer_id: str | None = None
    category_id: str | None = None
    schedule: str | None = Field(None, max_length=10)
    reorder_level: int | None = None
    sort_order: int = 0
    is_active: bool = True


class PharmacyItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    generic_name: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=30)
    mrp: Decimal | None = None
    purchase_rate: Decimal | None = None
    sale_rate: Decimal | None = None
    manufacturer_id: str | None = None
    category_id: str | None = None
    schedule: str | None = Field(None, max_length=10)
    reorder_level: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class PharmacySupplierRead(ORMModel):
    id: str
    code: str
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    gst_number: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PharmacySupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=150)
    contact_person: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=300)
    gst_number: str | None = Field(None, max_length=20)
    sort_order: int = 0
    is_active: bool = True


class PharmacySupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    contact_person: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=300)
    gst_number: str | None = Field(None, max_length=20)
    sort_order: int | None = None
    is_active: bool | None = None


class PharmacyGroupMappingRead(ORMModel):
    id: str
    group_id: str
    item_id: str
    created_at: datetime
    updated_at: datetime


class PharmacyGroupMappingCreate(BaseModel):
    group_id: str
    item_id: str


class PharmacyBillLineCreate(BaseModel):
    item_id: str
    quantity: int = Field(default=1, ge=1)
    rate: Decimal | None = Field(None, ge=0)
    batch_no: str | None = Field(None, max_length=50)
    expiry_date: date | None = None
    nos: int = Field(default=1, ge=1)
    factor: Decimal = Field(default=Decimal("1"), ge=0)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal | None = Field(None, ge=0)
    line_discount_percent: Decimal = Field(default=Decimal("0"), ge=0)
    line_discount_amount: Decimal | None = Field(None, ge=0)
    line_net: Decimal | None = Field(None, ge=0)
    user1: str | None = Field(None, max_length=50)


class PharmacySaleBillCreate(BaseModel):
    patient_id: str | None = None
    patient_name: str | None = Field(None, max_length=200)
    doctor_id: str | None = None
    doctor_name: str | None = Field(None, max_length=150)
    scheme: str | None = Field(None, max_length=100)
    payment_mode_id: str | None = None
    is_cash: bool = True
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    round_off: Decimal = Field(default=Decimal("0"))
    address1: str | None = Field(None, max_length=200)
    address2: str | None = Field(None, max_length=200)
    address3: str | None = Field(None, max_length=200)
    remarks: str | None = None
    bill_date: date | None = None
    lines: list[PharmacyBillLineCreate] = Field(default_factory=list)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[PharmacyBillLineCreate]) -> list[PharmacyBillLineCreate]:
        if not value:
            raise ValueError("At least one item line is required")
        return value


class PharmacyPurchaseBillCreate(BaseModel):
    supplier_id: str | None = None
    invoice_no: str | None = Field(None, max_length=50)
    remarks: str | None = None
    bill_date: date | None = None
    bill_kind: str = Field(default="purchase", pattern="^(purchase|return)$")
    lines: list[PharmacyBillLineCreate] = Field(default_factory=list)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[PharmacyBillLineCreate]) -> list[PharmacyBillLineCreate]:
        if not value:
            raise ValueError("At least one item line is required")
        return value


class PharmacyIndentCreate(BaseModel):
    ward_name: str = Field(..., min_length=1, max_length=150)
    remarks: str | None = None
    bill_date: date | None = None
    lines: list[PharmacyBillLineCreate] = Field(default_factory=list)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[PharmacyBillLineCreate]) -> list[PharmacyBillLineCreate]:
        if not value:
            raise ValueError("At least one item line is required")
        return value


class PharmacySaleBillLineRead(ORMModel):
    id: str
    item_id: str
    item_code: str
    item_name: str
    unit: str | None
    schedule: str | None
    nos: int
    factor: Decimal
    batch_no: str | None
    expiry_date: date | None
    rate: Decimal
    quantity: int
    tax_percent: Decimal
    tax_amount: Decimal
    amount: Decimal
    line_discount_percent: Decimal
    line_discount_amount: Decimal
    line_net: Decimal
    user1: str | None
    sort_order: int


class PharmacySaleBillRead(ORMModel):
    id: str
    bill_no: str
    bill_date: date
    patient_id: str | None
    patient_name: str | None
    doctor_id: str | None
    doctor_name: str | None
    scheme: str | None
    payment_mode_id: str | None
    is_cash: bool
    gross_amount: Decimal
    discount_amount: Decimal
    round_off: Decimal
    net_amount: Decimal
    address1: str | None
    address2: str | None
    address3: str | None
    remarks: str | None
    status: str
    lines: list[PharmacySaleBillLineRead]
    created_at: datetime
    updated_at: datetime


class PharmacyStockLookup(BaseModel):
    item_id: str
    item_code: str
    item_name: str
    stock_qty: int
    rate: Decimal | None


class PharmacyMedicineSearchResult(BaseModel):
    id: str
    code: str
    name: str
    generic_name: str | None
    unit: str | None
    sale_rate: Decimal | None
    mrp: Decimal | None
    schedule: str | None
    stock_qty: int


class PharmacyLastBillInfo(BaseModel):
    last_bill_no: str | None
    next_preview: str


class PharmacyPurchaseBillLineRead(ORMModel):
    id: str
    item_id: str
    item_code: str
    item_name: str
    unit: str | None
    rate: Decimal
    quantity: int
    amount: Decimal
    batch_no: str | None
    expiry_date: date | None
    sort_order: int


class PharmacyPurchaseBillRead(ORMModel):
    id: str
    bill_no: str
    bill_date: date
    supplier_id: str | None
    invoice_no: str | None
    gross_amount: Decimal
    net_amount: Decimal
    remarks: str | None
    status: str
    bill_kind: str = "purchase"
    lines: list[PharmacyPurchaseBillLineRead]
    created_at: datetime
    updated_at: datetime


class PharmacySalesRegisterRow(BaseModel):
    bill_no: str
    bill_date: date
    patient_name: str | None
    item_count: int
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal


class PharmacySalesSummaryRow(BaseModel):
    item_code: str
    item_name: str
    total_qty: int
    total_amount: Decimal


class PharmacyScheduleHRow(BaseModel):
    bill_no: str
    bill_date: date
    patient_name: str | None
    item_code: str
    item_name: str
    schedule: str
    quantity: int
    amount: Decimal


class PharmacyStockRow(BaseModel):
    item_type: str
    item_code: str
    item_name: str
    unit: str | None
    purchased_qty: int
    sold_qty: int
    balance_qty: int
    reorder_level: int | None
