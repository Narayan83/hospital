import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.app_data import AppDataResponse
from app.services.authority import AuthorityService
from app.services.billing_package import BillingPackageService
from app.services.billing_structure import BillingStructureService
from app.services.billing_type import BillingTypeService
from app.services.service_category import ServiceCategoryService
from app.services.service_sub_category import ServiceSubCategoryService
from app.services.department import DepartmentService
from app.services.doctor import DoctorService
from app.services.hospital_profile import HospitalProfileService
from app.services.hospital_section import HospitalSectionService
from app.services.patient_no_format import PatientNoFormatService
from app.services.patient_service_master import PatientServiceMasterService
from app.services.payment_mode import PaymentModeService
from app.services.prefix import PrefixService
from app.services.procedure_type import ProcedureTypeService
from app.services.role_mgmt import RoleManagementService
from app.services.user_mgmt import UserManagementService
from app.services.user_type import UserTypeService
from app.services.ward import WardService


class AppDataService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_app_data(self) -> AppDataResponse:
        (
            user_types,
            departments,
            billing_types,
            procedure_types,
            billing_structure,
            authorities,
            hospital_sections,
            prefixes,
            payment_modes,
            wards,
            doctors_page,
            users,
            roles,
            patient_no_formats,
            patient_services,
            service_categories,
            service_sub_categories,
            billing_packages,
            hospital_profile,
        ) = await asyncio.gather(
            UserTypeService(self.session).list_user_types(),
            DepartmentService(self.session).list_departments(),
            BillingTypeService(self.session).list_billing_types(),
            ProcedureTypeService(self.session).list_procedure_types(),
            BillingStructureService(self.session).list_mappings(),
            AuthorityService(self.session).list_authorities(),
            HospitalSectionService(self.session).list_sections(),
            PrefixService(self.session).list_prefixes(),
            PaymentModeService(self.session).list_payment_modes(),
            WardService(self.session).list_wards(),
            DoctorService(self.session).list_doctors_for_cache(),
            UserManagementService(self.session).list_users(),
            RoleManagementService(self.session).list_roles(),
            PatientNoFormatService(self.session).list_formats(),
            PatientServiceMasterService(self.session).list_services(),
            ServiceCategoryService(self.session).list_categories(),
            ServiceSubCategoryService(self.session).list_sub_categories(),
            BillingPackageService(self.session).list_packages(),
            HospitalProfileService(self.session).get_profile(),
        )

        return AppDataResponse(
            user_types=user_types,
            departments=departments,
            billing_types=billing_types,
            procedure_types=procedure_types,
            billing_structure=billing_structure,
            authorities=authorities,
            hospital_sections=hospital_sections,
            prefixes=prefixes,
            payment_modes=payment_modes,
            wards=wards,
            doctors=doctors_page,
            users=users,
            roles=roles,
            patient_no_formats=patient_no_formats,
            patient_services=patient_services,
            service_categories=service_categories,
            service_sub_categories=service_sub_categories,
            billing_packages=billing_packages,
            hospital_profile=hospital_profile,
        )
