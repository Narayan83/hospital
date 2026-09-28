from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class DoctorCollectionDetailRow(BaseModel):
    bill_date: date
    bill_type: str
    bill_no: str
    patient_no: str
    payment_mode: str = "—"
    service_name: str
    original_rate: Decimal = Field(..., decimal_places=2)
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionDateGroup(BaseModel):
    bill_date: date
    rows: list[DoctorCollectionDetailRow] = Field(default_factory=list)
    total_amount: Decimal = Field(..., decimal_places=2)
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionServiceSummaryRow(BaseModel):
    service_name: str
    total_amount: Decimal = Field(..., decimal_places=2)
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionDoctorGroup(BaseModel):
    doctor_id: str
    doctor_name: str
    date_groups: list[DoctorCollectionDateGroup]
    service_summary: list[DoctorCollectionServiceSummaryRow] = Field(default_factory=list)
    grand_total_amount: Decimal = Field(..., decimal_places=2)
    grand_hospital_amount: Decimal = Field(..., decimal_places=2)
    grand_doctor_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionReportRead(BaseModel):
    report_type: Literal["normal", "sharing", "day_wise_summary"] = "sharing"
    from_date: date
    to_date: date
    doctors: list[DoctorCollectionDoctorGroup]
    overall_total_amount: Decimal = Field(..., decimal_places=2)
    overall_hospital_amount: Decimal = Field(..., decimal_places=2)
    overall_doctor_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionPaymentModeDoctorRow(BaseModel):
    doctor_id: str
    doctor_name: str
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionPaymentModeGroup(BaseModel):
    payment_mode: str
    doctors: list[DoctorCollectionPaymentModeDoctorRow]
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionPaymentModeReportRead(BaseModel):
    report_type: Literal["payment_mode_summary"] = "payment_mode_summary"
    from_date: date
    to_date: date
    payment_modes: list[DoctorCollectionPaymentModeGroup]
    overall_total_amount: Decimal = Field(..., decimal_places=2)
    overall_hospital_amount: Decimal = Field(..., decimal_places=2)
    overall_doctor_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionServiceColumn(BaseModel):
    service_id: str
    service_name: str


class DoctorCollectionColumnRow(BaseModel):
    """One patient/bill row — amounts keyed by mapped service_id (ledger columns)."""

    bill_date: date
    bill_type: str
    bill_no: str
    patient_no: str
    patient_name: str
    payment_mode: str = "—"
    amounts: dict[str, Decimal] = Field(default_factory=dict)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionColumnDoctorGroup(BaseModel):
    doctor_id: str
    doctor_name: str
    rows: list[DoctorCollectionColumnRow]
    column_totals: dict[str, Decimal] = Field(default_factory=dict)
    grand_total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionColumnReportRead(BaseModel):
    report_type: Literal["column_wise"] = "column_wise"
    from_date: date
    to_date: date
    service_columns: list[DoctorCollectionServiceColumn]
    doctors: list[DoctorCollectionColumnDoctorGroup]
    overall_column_totals: dict[str, Decimal] = Field(default_factory=dict)
    overall_total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionDateServiceRow(BaseModel):
    """One service total (summary) or service header with optional bill lines (details)."""

    service_name: str
    rows: list[DoctorCollectionDetailRow] = Field(default_factory=list)
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionDateServiceGroup(BaseModel):
    bill_date: date
    services: list[DoctorCollectionDateServiceRow] = Field(default_factory=list)
    hospital_amount: Decimal = Field(..., decimal_places=2)
    doctor_amount: Decimal = Field(..., decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)


class DoctorCollectionDateServiceReportRead(BaseModel):
    report_type: Literal["date_service_summary", "date_service_details"]
    from_date: date
    to_date: date
    date_groups: list[DoctorCollectionDateServiceGroup]
    overall_total_amount: Decimal = Field(..., decimal_places=2)
    overall_hospital_amount: Decimal = Field(..., decimal_places=2)
    overall_doctor_amount: Decimal = Field(..., decimal_places=2)
