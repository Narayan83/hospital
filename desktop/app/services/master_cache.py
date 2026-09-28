import time

from app.api_client.client import ApiClient, ApiError
from app.session import get_session


def apply_master_cache(data: dict) -> None:
    session = get_session()
    session.cache.user_types = data.get("user_types", [])
    session.cache.departments = data.get("departments", [])
    session.cache.billing_types = data.get("billing_types", [])
    session.cache.procedure_types = data.get("procedure_types", [])
    session.cache.billing_structure = data.get("billing_structure", [])
    session.cache.authorities = data.get("authorities", [])
    session.cache.hospital_sections = data.get("hospital_sections", [])
    session.cache.prefixes = data.get("prefixes", [])
    session.cache.payment_modes = data.get("payment_modes", [])
    session.cache.wards = data.get("wards", [])
    session.cache.doctors = data.get("doctors", [])
    session.cache.users = data.get("users", [])
    session.cache.roles = data.get("roles", [])
    session.cache.patient_no_formats = data.get("patient_no_formats", [])
    session.cache.patient_services = data.get("patient_services", [])
    session.cache.service_categories = data.get("service_categories", [])
    session.cache.service_sub_categories = data.get("service_sub_categories", [])
    session.cache.billing_packages = data.get("billing_packages", [])
    profile = data.get("hospital_profile") or {}
    session.cache.hospital_profile = profile
    session.cache.mark_loaded()


def load_master_cache(api: ApiClient) -> str | None:
    """Fallback when login response has no app_data."""
    session = get_session()
    session.cache.loading = True
    session.cache.error = ""
    try:
        apply_master_cache(api.get_app_data())
        return None
    except ApiError as exc:
        session.cache.mark_failed(str(exc))
        return str(exc)
    except Exception as exc:
        session.cache.mark_failed(str(exc))
        return f"Failed to load application data: {exc}"


def refresh_users_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.users = api.list_users()


def refresh_doctors_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.doctors = api.list_doctors(page_size=100).get("items", [])
    session.cache.loaded_at = time.time()


def refresh_billing_types_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.billing_types = api.list_billing_types()


def refresh_departments_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.departments = api.list_departments()


def refresh_procedure_types_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.procedure_types = api.list_procedure_types()


def refresh_billing_structure_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.billing_structure = api.list_billing_structure()


def refresh_authorities_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.authorities = api.list_authorities()


def refresh_hospital_sections_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.hospital_sections = api.list_hospital_sections()


def refresh_prefixes_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.prefixes = api.list_prefixes()


def refresh_payment_modes_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.payment_modes = api.list_payment_modes()


def refresh_wards_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.wards = api.list_wards()


def refresh_patient_services_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.patient_services = api.list_patient_services()
    session.cache.loaded_at = time.time()


def refresh_patient_no_formats_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.patient_no_formats = api.list_patient_no_formats()


def refresh_service_categories_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.service_categories = api.list_service_categories()
    session.cache.loaded_at = time.time()


def refresh_billing_packages_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.billing_packages = api.list_billing_packages()
    session.cache.loaded_at = time.time()


def refresh_service_sub_categories_cache(api: ApiClient) -> None:
    session = get_session()
    session.cache.service_sub_categories = api.list_service_sub_categories()
    session.cache.loaded_at = time.time()
