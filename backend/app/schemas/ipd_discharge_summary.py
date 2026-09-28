from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class IpdDischargeSummaryCreate(BaseModel):
    patient_id: str
    doctor_id: str = Field(..., min_length=1)
    admission_id: str | None = None
    include_admission_details: bool = False
    summary_date: date | None = None
    admission_date: date
    discharge_date: date
    chief_complaint: str | None = None
    history_of_illness: str | None = None
    diagnosis_on_admission: str | None = Field(None, max_length=500)
    final_diagnosis: str | None = Field(None, max_length=500)
    investigation: str | None = None
    treatment_given: str | None = None
    procedures: str | None = None
    condition_on_discharge: str | None = Field(None, max_length=100)
    medications_on_discharge: str | None = None
    advice_follow_up: str | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "IpdDischargeSummaryCreate":
        if self.discharge_date < self.admission_date:
            raise ValueError("Discharge date cannot be before admission date")
        if self.include_admission_details and not self.admission_id:
            raise ValueError("Select an admission when admission details are enabled")
        fields = (
            self.chief_complaint,
            self.history_of_illness,
            self.diagnosis_on_admission,
            self.final_diagnosis,
            self.investigation,
            self.treatment_given,
            self.procedures,
            self.condition_on_discharge,
            self.medications_on_discharge,
            self.advice_follow_up,
        )
        if not any(field and str(field).strip() for field in fields):
            raise ValueError("Enter at least one clinical detail for the discharge summary")
        return self


class IpdDischargeSummaryUpdate(BaseModel):
    doctor_id: str | None = Field(None, min_length=1)
    admission_id: str | None = None
    include_admission_details: bool | None = None
    summary_date: date | None = None
    admission_date: date | None = None
    discharge_date: date | None = None
    chief_complaint: str | None = None
    history_of_illness: str | None = None
    diagnosis_on_admission: str | None = Field(None, max_length=500)
    final_diagnosis: str | None = Field(None, max_length=500)
    investigation: str | None = None
    treatment_given: str | None = None
    procedures: str | None = None
    condition_on_discharge: str | None = Field(None, max_length=100)
    medications_on_discharge: str | None = None
    advice_follow_up: str | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "IpdDischargeSummaryUpdate":
        if self.admission_date and self.discharge_date and self.discharge_date < self.admission_date:
            raise ValueError("Discharge date cannot be before admission date")
        return self


class IpdDischargeSummaryRead(ORMModel):
    id: str
    summary_no: str
    summary_date: date
    admission_id: str | None = None
    admission_no: str | None = None
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    patient_gender: str | None = None
    ward_name: str | None = None
    bed_no: str | None = None
    department_name: str | None = None
    admission_date: date | None = None
    discharge_date: date | None = None
    stay_days: int | None = None
    doctor_id: str | None
    doctor_name: str | None = None
    include_admission_details: bool = False
    chief_complaint: str | None
    history_of_illness: str | None
    diagnosis_on_admission: str | None
    final_diagnosis: str | None
    investigation: str | None
    treatment_given: str | None
    procedures: str | None
    condition_on_discharge: str | None
    medications_on_discharge: str | None
    advice_follow_up: str | None
    remarks: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IpdDischargeSummaryListRead(BaseModel):
    id: str
    summary_no: str
    summary_date: date
    admission_no: str | None = None
    patient_no: str | None = None
    patient_name: str | None = None
    doctor_name: str | None = None
    final_diagnosis: str | None = None
    discharge_date: date | None = None
    created_at: datetime
