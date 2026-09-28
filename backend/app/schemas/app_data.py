from pydantic import BaseModel

from app.schemas.authority import AuthorityRead
from app.schemas.billing_package import BillingPackageRead
from app.schemas.billing_type import BillingTypeRead
from app.schemas.service_category import ServiceCategoryRead
from app.schemas.service_sub_category import ServiceSubCategoryRead
from app.schemas.department import DepartmentRead
from app.schemas.hospital_section import HospitalSectionRead
from app.schemas.billing_structure import BillingStructureRead
from app.schemas.payment_mode import PaymentModeRead
from app.schemas.patient_no_format import PatientNoFormatRead
from app.schemas.patient_service_master import PatientServiceMasterRead
from app.schemas.prefix import PrefixRead
from app.schemas.procedure_type import ProcedureTypeRead
from app.schemas.doctor import DoctorRead
from app.schemas.hospital_profile import HospitalProfileRead
from app.schemas.role import RoleRead
from app.schemas.user_mgmt import UserRead
from app.schemas.user_type import UserTypeRead
from app.schemas.ward import WardRead


class AppDataResponse(BaseModel):
    user_types: list[UserTypeRead]
    departments: list[DepartmentRead]
    billing_types: list[BillingTypeRead]
    procedure_types: list[ProcedureTypeRead]
    billing_structure: list[BillingStructureRead]
    authorities: list[AuthorityRead]
    hospital_sections: list[HospitalSectionRead]
    prefixes: list[PrefixRead]
    payment_modes: list[PaymentModeRead]
    wards: list[WardRead]
    doctors: list[DoctorRead]
    users: list[UserRead]
    roles: list[RoleRead]
    patient_no_formats: list[PatientNoFormatRead]
    patient_services: list[PatientServiceMasterRead]
    service_categories: list[ServiceCategoryRead]
    service_sub_categories: list[ServiceSubCategoryRead]
    billing_packages: list[BillingPackageRead]
    hospital_profile: HospitalProfileRead
