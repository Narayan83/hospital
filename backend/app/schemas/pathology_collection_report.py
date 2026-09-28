from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PathologyCollectionDetailRow(BaseModel):
    bill_date: date
    bill_no: str
    patient_no: str
    patient_name: str = "—"
    payment_mode: str = "—"
    pathologist_name: str = "—"
    referring_doctor: str = "—"
    service_name: str
    rate: Decimal = Field(..., decimal_places=2)
    amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionDateGroup(BaseModel):
    bill_date: date
    rows: list[PathologyCollectionDetailRow]
    total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionServiceSummaryRow(BaseModel):
    service_name: str
    total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionGroup(BaseModel):
    group_key: str
    group_name: str
    date_groups: list[PathologyCollectionDateGroup]
    service_summary: list[PathologyCollectionServiceSummaryRow]
    grand_total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionReportRead(BaseModel):
    report_type: Literal["normal", "referral_wise"] = "normal"
    from_date: date
    to_date: date
    groups: list[PathologyCollectionGroup]
    overall_total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionServiceColumn(BaseModel):
    service_id: str
    service_name: str


class PathologyCollectionColumnRow(BaseModel):
    bill_date: date
    bill_no: str
    patient_no: str
    patient_name: str
    payment_mode: str = "—"
    amounts: dict[str, Decimal] = Field(default_factory=dict)
    total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionColumnGroup(BaseModel):
    group_key: str
    group_name: str
    rows: list[PathologyCollectionColumnRow]
    column_totals: dict[str, Decimal] = Field(default_factory=dict)
    grand_total_amount: Decimal = Field(..., decimal_places=2)


class PathologyCollectionColumnReportRead(BaseModel):
    report_type: Literal["column_wise"] = "column_wise"
    from_date: date
    to_date: date
    service_columns: list[PathologyCollectionServiceColumn]
    groups: list[PathologyCollectionColumnGroup]
    overall_column_totals: dict[str, Decimal] = Field(default_factory=dict)
    overall_total_amount: Decimal = Field(..., decimal_places=2)
