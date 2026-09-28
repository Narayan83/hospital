from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    legacy_migrate,
    auth,
    authorities,
    bill_identity,
    billing_packages,
    billing_structure,
    billing_types,
    service_categories,
    service_sub_categories,
    short_bills,
    single_service_opd,
    cashbook,
    dashboard,
    dashboard_shortcuts,
    departments,
    procedure_types,
    doctors,
    hospital_profile,
    hospital_sections,
    menus,
    prefixes,
    notifications,
    ipd_admissions,
    ipd_discharge,
    ipd_discharge_summaries,
    lab_tests,
    ledgers,
    letter_templates,
    print_configs,
    opd_bills,
    pathology_bills,
    pathology_masters,
    pharmacy,
    patient_no_formats,
    patient_service_masters,
    patient_documents,
    patients,
    payment_modes,
    reports,
    roles,
    user_roles,
    user_types,
    users,
    wards,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(
    dashboard_shortcuts.router, prefix="/dashboard", tags=["dashboard-shortcuts"]
)
api_router.include_router(menus.router, prefix="/menus", tags=["menus"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(user_types.router, prefix="/user-types", tags=["user-types"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(user_roles.router, prefix="/user-roles", tags=["user-roles"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(
    patient_documents.router, prefix="/patient-documents", tags=["patient-documents"]
)
api_router.include_router(
    patient_no_formats.router, prefix="/patient-no-formats", tags=["patient-no-formats"]
)
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(
    patient_service_masters.router,
    prefix="/patient-services",
    tags=["patient-services"],
)
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(hospital_sections.router, prefix="/hospital-sections", tags=["hospital-sections"])
api_router.include_router(
    hospital_profile.router, prefix="/hospital-profile", tags=["hospital-profile"]
)
api_router.include_router(prefixes.router, prefix="/prefixes", tags=["prefixes"])
api_router.include_router(authorities.router, prefix="/authorities", tags=["authorities"])
api_router.include_router(
    letter_templates.router, prefix="/letter-templates", tags=["letter-templates"]
)
api_router.include_router(
    print_configs.router, prefix="/print-configs", tags=["print-configs"]
)
api_router.include_router(ledgers.router, prefix="/ledgers", tags=["ledgers"])
api_router.include_router(cashbook.router, prefix="/cashbook", tags=["cashbook"])
api_router.include_router(billing_types.router, prefix="/billing-types", tags=["billing-types"])
api_router.include_router(procedure_types.router, prefix="/procedure-types", tags=["procedure-types"])
api_router.include_router(
    billing_structure.router, prefix="/billing-structure", tags=["billing-structure"]
)
api_router.include_router(
    service_categories.router, prefix="/service-categories", tags=["service-categories"]
)
api_router.include_router(
    billing_packages.router, prefix="/billing-packages", tags=["billing-packages"]
)
api_router.include_router(
    service_sub_categories.router,
    prefix="/service-sub-categories",
    tags=["service-sub-categories"],
)
api_router.include_router(opd_bills.router, prefix="/opd-bills", tags=["opd-bills"])
api_router.include_router(
    bill_identity.router, prefix="/bill-identity", tags=["bill-identity"]
)
api_router.include_router(
    pathology_bills.router, prefix="/pathology-bills", tags=["pathology-bills"]
)
api_router.include_router(
    pathology_masters.router, prefix="/pathology", tags=["pathology"]
)
api_router.include_router(lab_tests.router, prefix="/pathology", tags=["pathology"])
api_router.include_router(pharmacy.router, prefix="/pharmacy", tags=["pharmacy"])
api_router.include_router(
    ipd_admissions.router, prefix="/ipd-admissions", tags=["ipd-admissions"]
)
api_router.include_router(
    ipd_discharge.router, prefix="/ipd-discharge", tags=["ipd-discharge"]
)
api_router.include_router(
    ipd_discharge_summaries.router,
    prefix="/ipd-discharge-summaries",
    tags=["ipd-discharge-summaries"],
)
api_router.include_router(wards.router, prefix="/wards", tags=["wards"])
api_router.include_router(payment_modes.router, prefix="/payment-modes", tags=["payment-modes"])
api_router.include_router(short_bills.router, prefix="/short-bills", tags=["short-bills"])
api_router.include_router(
    single_service_opd.router, prefix="/single-service-opd", tags=["single-service-opd"]
)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(
    legacy_migrate.router, prefix="/admin", tags=["admin", "legacy-migrate"]
)
