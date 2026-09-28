from pydantic import BaseModel


class DashboardStats(BaseModel):
    patients: int
    doctors: int
    departments: int
    wards: int
    services: int
    staff: int
    billing_types: int
    payment_modes: int
    hospital_sections: int
