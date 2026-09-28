import json
from collections.abc import Iterator
from typing import Any

import httpx
import time

from app.config import get_config
from app.session import get_session


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _format_detail(detail: Any) -> str:
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(part) for part in item.get("loc", []))
                msg = item.get("msg", "")
                parts.append(f"{loc}: {msg}" if loc else msg)
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(detail)


class ApiClient:
    def __init__(self, timeout: float = 30.0):
        self.config = get_config()
        self._client = httpx.Client(
            base_url=self.config.api_base,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._warmup_connection()

    def close(self) -> None:
        self._client.close()

    def _warmup_connection(self) -> None:
        """Open TCP to backend early so first login is not delayed by connect/DNS."""
        try:
            health_url = f"{self.config.api_url.rstrip('/')}/health"
            self._client.get(health_url, timeout=2.0)
        except Exception:
            pass

    def _headers(self) -> dict[str, str]:
        token = get_session().access_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.is_success:
            if response.status_code == 204:
                return None
            return response.json()
        detail = "Request failed"
        try:
            body = response.json()
            detail = _format_detail(body.get("detail", detail))
        except Exception:
            detail = response.text or detail
        if response.status_code == 401:
            detail = "Your session has expired. Please log out and log in again."
        raise ApiError(detail, status_code=response.status_code)

    def health_check(self) -> dict:
        response = self._client.get(f"{self.config.api_url.rstrip('/')}/health")
        return self._handle_response(response)

    def login(self, email: str, password: str) -> dict:
        t0 = time.perf_counter()
        response = self._client.post("/auth/login", json={"email": email, "password": password})
        network_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        result = self._handle_response(response)
        parse_ms = (time.perf_counter() - t1) * 1000
        if isinstance(result, dict):
            result["_hms_perf"] = {
                "network_ms": round(network_ms, 1),
                "parse_ms": round(parse_ms, 1),
                "response_kb": round(len(response.content) / 1024, 1),
            }
        return result

    def get_my_menus(self) -> list:
        response = self._client.get("/auth/my-menus", headers=self._headers())
        return self._handle_response(response)

    def get_app_data(self) -> dict:
        response = self._client.get("/auth/app-data", headers=self._headers())
        return self._handle_response(response)

    def get_dashboard_stats(self) -> dict:
        response = self._client.get("/dashboard/stats", headers=self._headers())
        return self._handle_response(response)

    def list_dashboard_shortcuts(self, active_only: bool = True, host_code: str = "dashboard") -> list:
        response = self._client.get(
            "/dashboard/shortcuts",
            params={"active_only": active_only, "host_code": host_code},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_dashboard_shortcut_menus(self, host_code: str = "dashboard") -> list:
        response = self._client.get(
            "/dashboard/shortcut-menus",
            params={"host_code": host_code},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def save_dashboard_shortcuts(self, payload: dict) -> list:
        response = self._client.put(
            "/dashboard/shortcuts",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_dashboard_shortcut(self, payload: dict) -> dict:
        response = self._client.post(
            "/dashboard/shortcuts",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def delete_dashboard_shortcut(self, shortcut_id: str) -> None:
        response = self._client.delete(
            f"/dashboard/shortcuts/{shortcut_id}",
            headers=self._headers(),
        )
        if response.status_code == 204:
            return None
        return self._handle_response(response)

    def list_users(self) -> list:
        response = self._client.get("/users", headers=self._headers())
        return self._handle_response(response)

    def create_user(self, payload: dict) -> dict:
        response = self._client.post("/users", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_user(self, user_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/users/{user_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_user(self, user_id: str) -> dict:
        response = self._client.delete(f"/users/{user_id}", headers=self._headers())
        return self._handle_response(response)

    def list_user_types(self) -> list:
        response = self._client.get("/user-types", headers=self._headers())
        return self._handle_response(response)

    def create_user_type(self, payload: dict) -> dict:
        response = self._client.post("/user-types", json=payload, headers=self._headers())
        return self._handle_response(response)

    def list_departments(self) -> list:
        response = self._client.get("/departments", headers=self._headers())
        return self._handle_response(response)

    def get_department(self, department_id: str) -> dict:
        response = self._client.get(f"/departments/{department_id}", headers=self._headers())
        return self._handle_response(response)

    def create_department(self, payload: dict) -> dict:
        response = self._client.post("/departments", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_department(self, department_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/departments/{department_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_department(self, department_id: str) -> dict:
        response = self._client.delete(f"/departments/{department_id}", headers=self._headers())
        return self._handle_response(response)

    def list_billing_types(self) -> list:
        response = self._client.get("/billing-types", headers=self._headers())
        return self._handle_response(response)

    def list_procedure_types(self) -> list:
        response = self._client.get("/procedure-types", headers=self._headers())
        return self._handle_response(response)

    def get_procedure_type(self, procedure_type_id: str) -> dict:
        response = self._client.get(f"/procedure-types/{procedure_type_id}", headers=self._headers())
        return self._handle_response(response)

    def create_procedure_type(self, payload: dict) -> dict:
        response = self._client.post("/procedure-types", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_procedure_type(self, procedure_type_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/procedure-types/{procedure_type_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_procedure_type(self, procedure_type_id: str) -> dict:
        response = self._client.delete(f"/procedure-types/{procedure_type_id}", headers=self._headers())
        return self._handle_response(response)

    def list_billing_structure(self) -> list:
        response = self._client.get("/billing-structure", headers=self._headers())
        return self._handle_response(response)

    def get_billing_structure_tree(self) -> list:
        response = self._client.get("/billing-structure/tree", headers=self._headers())
        return self._handle_response(response)

    def create_billing_structure(self, payload: dict) -> dict:
        response = self._client.post("/billing-structure", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_billing_structure(self, mapping_id: str) -> dict:
        response = self._client.delete(f"/billing-structure/{mapping_id}", headers=self._headers())
        return self._handle_response(response)

    def get_billing_type(self, billing_type_id: str) -> dict:
        response = self._client.get(f"/billing-types/{billing_type_id}", headers=self._headers())
        return self._handle_response(response)

    def create_billing_type(self, payload: dict) -> dict:
        response = self._client.post("/billing-types", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_billing_type(self, billing_type_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/billing-types/{billing_type_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_billing_type(self, billing_type_id: str) -> dict:
        response = self._client.delete(f"/billing-types/{billing_type_id}", headers=self._headers())
        return self._handle_response(response)

    def list_authorities(self) -> list:
        response = self._client.get("/authorities", headers=self._headers())
        return self._handle_response(response)

    def get_authority(self, authority_id: str) -> dict:
        response = self._client.get(f"/authorities/{authority_id}", headers=self._headers())
        return self._handle_response(response)

    def create_authority(self, payload: dict) -> dict:
        response = self._client.post("/authorities", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_authority(self, authority_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/authorities/{authority_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_authority(self, authority_id: str) -> dict:
        response = self._client.delete(f"/authorities/{authority_id}", headers=self._headers())
        return self._handle_response(response)

    def list_letter_templates(self) -> list:
        response = self._client.get("/letter-templates", headers=self._headers())
        return self._handle_response(response)

    def get_letter_template(self, letter_id: str) -> dict:
        response = self._client.get(f"/letter-templates/{letter_id}", headers=self._headers())
        return self._handle_response(response)

    def create_letter_template(self, payload: dict) -> dict:
        response = self._client.post("/letter-templates", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_letter_template(self, letter_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/letter-templates/{letter_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_letter_template(self, letter_id: str) -> dict:
        response = self._client.delete(f"/letter-templates/{letter_id}", headers=self._headers())
        return self._handle_response(response)

    def list_print_configs(self) -> list:
        response = self._client.get("/print-configs", headers=self._headers())
        return self._handle_response(response)

    def get_print_config(self, config_id: str) -> dict:
        response = self._client.get(f"/print-configs/{config_id}", headers=self._headers())
        return self._handle_response(response)

    def get_print_config_by_code(self, code: str) -> dict:
        response = self._client.get(f"/print-configs/by-code/{code}", headers=self._headers())
        return self._handle_response(response)

    def get_print_layout(self, code: str) -> dict:
        response = self._client.get(f"/print-configs/layouts/by-code/{code}", headers=self._headers())
        return self._handle_response(response)

    def get_print_layout_catalog(self) -> dict:
        response = self._client.get("/print-configs/layouts/catalog", headers=self._headers())
        return self._handle_response(response)

    def save_print_layout(self, code: str, payload: dict) -> dict:
        response = self._client.put(
            f"/print-configs/layouts/by-code/{code}",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def reset_print_layout(self, code: str) -> dict:
        response = self._client.post(
            f"/print-configs/layouts/by-code/{code}/reset",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def preview_print_layout(self, payload: dict) -> dict:
        response = self._client.post(
            "/print-configs/layouts/preview",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_print_config(self, config_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/print-configs/{config_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def list_ledgers(self) -> list:
        response = self._client.get("/ledgers", headers=self._headers())
        return self._handle_response(response)

    def get_ledger(self, ledger_id: str) -> dict:
        response = self._client.get(f"/ledgers/{ledger_id}", headers=self._headers())
        return self._handle_response(response)

    def create_ledger(self, payload: dict) -> dict:
        response = self._client.post("/ledgers", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_ledger(self, ledger_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/ledgers/{ledger_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_ledger(self, ledger_id: str) -> dict:
        response = self._client.delete(f"/ledgers/{ledger_id}", headers=self._headers())
        return self._handle_response(response)

    def get_cashbook_ledger_statement(
        self,
        ledger_id: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get(
            f"/cashbook/ledger/{ledger_id}",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_cashbook_patient_account(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        params: dict = {}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get(
            "/cashbook/patient-account",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_patient_deposit_balance(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> dict:
        params: dict = {}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        response = self._client.get(
            "/cashbook/patient-deposit",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def collect_advance(self, payload: dict) -> dict:
        response = self._client.post("/cashbook/advance", json=payload, headers=self._headers())
        return self._handle_response(response)

    def list_advances(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
        voucher_no: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 200,
    ) -> list:
        params: dict = {"limit": limit}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        if voucher_no:
            params["voucher_no"] = voucher_no
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get("/cashbook/advance", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_advance(self, voucher_id: str) -> dict:
        response = self._client.get(f"/cashbook/advance/{voucher_id}", headers=self._headers())
        return self._handle_response(response)

    def get_advance_by_no(self, voucher_no: str) -> dict:
        response = self._client.get(
            f"/cashbook/advance/by-no/{voucher_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_advance(self, voucher_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/cashbook/advance/{voucher_id}",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def delete_advance(self, voucher_id: str) -> None:
        response = self._client.delete(
            f"/cashbook/advance/{voucher_id}",
            headers=self._headers(),
        )
        if response.status_code not in (200, 204):
            self._handle_response(response)

    def create_payment_voucher(self, payload: dict) -> dict:
        response = self._client.post("/cashbook/payment", json=payload, headers=self._headers())
        return self._handle_response(response)

    def create_contra_entry(self, payload: dict) -> dict:
        response = self._client.post("/cashbook/contra", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_daybook(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get("/cashbook/daybook", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_cash_book(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get("/cashbook/cash-book", params=params, headers=self._headers())
        return self._handle_response(response)

    def list_hospital_sections(self) -> list:
        response = self._client.get("/hospital-sections", headers=self._headers())
        return self._handle_response(response)

    def get_hospital_section(self, section_id: str) -> dict:
        response = self._client.get(f"/hospital-sections/{section_id}", headers=self._headers())
        return self._handle_response(response)

    def create_hospital_section(self, payload: dict) -> dict:
        response = self._client.post("/hospital-sections", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_hospital_section(self, section_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/hospital-sections/{section_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_hospital_section(self, section_id: str) -> dict:
        response = self._client.delete(f"/hospital-sections/{section_id}", headers=self._headers())
        return self._handle_response(response)

    def get_hospital_profile(self) -> dict:
        response = self._client.get("/hospital-profile", headers=self._headers())
        return self._handle_response(response)

    def update_hospital_profile(self, payload: dict) -> dict:
        response = self._client.put("/hospital-profile", json=payload, headers=self._headers())
        return self._handle_response(response)

    def list_prefixes(self) -> list:
        response = self._client.get("/prefixes", headers=self._headers())
        return self._handle_response(response)

    def get_prefix(self, prefix_id: str) -> dict:
        response = self._client.get(f"/prefixes/{prefix_id}", headers=self._headers())
        return self._handle_response(response)

    def create_prefix(self, payload: dict) -> dict:
        response = self._client.post("/prefixes", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_prefix(self, prefix_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/prefixes/{prefix_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_prefix(self, prefix_id: str) -> dict:
        response = self._client.delete(f"/prefixes/{prefix_id}", headers=self._headers())
        return self._handle_response(response)

    def list_patient_no_formats(self) -> list:
        response = self._client.get("/patient-no-formats", headers=self._headers())
        return self._handle_response(response)

    def get_patient_no_format(self, format_id: str) -> dict:
        response = self._client.get(f"/patient-no-formats/{format_id}", headers=self._headers())
        return self._handle_response(response)

    def create_patient_no_format(self, payload: dict) -> dict:
        response = self._client.post("/patient-no-formats", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_patient_no_format(self, format_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/patient-no-formats/{format_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_patient_no_format(self, format_id: str) -> dict:
        response = self._client.delete(f"/patient-no-formats/{format_id}", headers=self._headers())
        return self._handle_response(response)

    def list_payment_modes(self) -> list:
        response = self._client.get("/payment-modes", headers=self._headers())
        return self._handle_response(response)

    def get_payment_mode(self, payment_mode_id: str) -> dict:
        response = self._client.get(f"/payment-modes/{payment_mode_id}", headers=self._headers())
        return self._handle_response(response)

    def create_payment_mode(self, payload: dict) -> dict:
        response = self._client.post("/payment-modes", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_payment_mode(self, payment_mode_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/payment-modes/{payment_mode_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_payment_mode(self, payment_mode_id: str) -> dict:
        response = self._client.delete(f"/payment-modes/{payment_mode_id}", headers=self._headers())
        return self._handle_response(response)

    def list_wards(self) -> list:
        response = self._client.get("/wards", headers=self._headers())
        return self._handle_response(response)

    def get_ward(self, ward_id: str) -> dict:
        response = self._client.get(f"/wards/{ward_id}", headers=self._headers())
        return self._handle_response(response)

    def create_ward(self, payload: dict) -> dict:
        response = self._client.post("/wards", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_ward(self, ward_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/wards/{ward_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_ward(self, ward_id: str) -> dict:
        response = self._client.delete(f"/wards/{ward_id}", headers=self._headers())
        return self._handle_response(response)

    def list_doctors(self, *, page: int = 1, page_size: int = 100, search: str | None = None) -> dict:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        response = self._client.get("/doctors", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_doctor(self, doctor_id: str) -> dict:
        response = self._client.get(f"/doctors/{doctor_id}", headers=self._headers())
        return self._handle_response(response)

    def create_doctor(self, payload: dict) -> dict:
        response = self._client.post("/doctors", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_doctor(self, doctor_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/doctors/{doctor_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_doctor(self, doctor_id: str) -> dict:
        response = self._client.delete(f"/doctors/{doctor_id}", headers=self._headers())
        return self._handle_response(response)

    def upload_doctor_photo(self, doctor_id: str, file_path: str) -> dict:
        with open(file_path, "rb") as handle:
            response = self._client.post(
                f"/doctors/{doctor_id}/photo",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle, "application/octet-stream")},
                headers=self._headers(),
            )
        return self._handle_response(response)

    def upload_doctor_certificate(self, doctor_id: str, file_path: str) -> dict:
        with open(file_path, "rb") as handle:
            response = self._client.post(
                f"/doctors/{doctor_id}/certificate",
                files={"file": (file_path.split("\\")[-1].split("/")[-1], handle, "application/octet-stream")},
                headers=self._headers(),
            )
        return self._handle_response(response)

    def doctor_photo_url(self, doctor_id: str) -> str:
        return f"{self.config.api_base}/doctors/{doctor_id}/photo"

    def list_roles(self) -> list:
        response = self._client.get("/roles", headers=self._headers())
        return self._handle_response(response)

    def list_menus(self) -> list:
        response = self._client.get("/menus", headers=self._headers())
        return self._handle_response(response)

    def create_role(self, payload: dict) -> dict:
        response = self._client.post("/roles", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_role_permissions(self, role_id: str) -> list:
        response = self._client.get(f"/roles/{role_id}/permissions", headers=self._headers())
        return self._handle_response(response)

    def set_role_permissions(self, role_id: str, permissions: list[dict]) -> dict:
        response = self._client.put(
            f"/roles/{role_id}/permissions",
            json={"permissions": permissions},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_user_roles(self, user_id: str) -> list:
        response = self._client.get(f"/user-roles?user_id={user_id}", headers=self._headers())
        return self._handle_response(response)

    def assign_user_role(self, payload: dict) -> dict:
        response = self._client.post("/user-roles", json=payload, headers=self._headers())
        return self._handle_response(response)

    def remove_user_role(self, mapping_id: str) -> None:
        response = self._client.delete(f"/user-roles/{mapping_id}", headers=self._headers())
        self._handle_response(response)

    def get_notification_setup(self, event_code: str) -> dict:
        response = self._client.get(
            f"/notifications/setup?event_code={event_code}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def save_notification_setup(self, payload: dict) -> dict:
        response = self._client.put("/notifications/setup", json=payload, headers=self._headers())
        return self._handle_response(response)

    def list_patient_services(self) -> list:
        response = self._client.get("/patient-services", headers=self._headers())
        return self._handle_response(response)

    def get_patient_service(self, service_id: str) -> dict:
        response = self._client.get(f"/patient-services/{service_id}", headers=self._headers())
        return self._handle_response(response)

    def create_patient_service(self, payload: dict) -> dict:
        response = self._client.post("/patient-services", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_patient_service(self, service_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/patient-services/{service_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_patient_service(self, service_id: str) -> dict:
        response = self._client.delete(f"/patient-services/{service_id}", headers=self._headers())
        return self._handle_response(response)

    def list_service_categories(self) -> list:
        response = self._client.get("/service-categories", headers=self._headers())
        return self._handle_response(response)

    def get_service_category(self, category_id: str) -> dict:
        response = self._client.get(f"/service-categories/{category_id}", headers=self._headers())
        return self._handle_response(response)

    def create_service_category(self, payload: dict) -> dict:
        response = self._client.post("/service-categories", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_service_category(self, category_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/service-categories/{category_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_service_category(self, category_id: str) -> dict:
        response = self._client.delete(f"/service-categories/{category_id}", headers=self._headers())
        return self._handle_response(response)

    def list_billing_packages(self) -> list:
        response = self._client.get("/billing-packages", headers=self._headers())
        return self._handle_response(response)

    def get_billing_package(self, package_id: str) -> dict:
        response = self._client.get(f"/billing-packages/{package_id}", headers=self._headers())
        return self._handle_response(response)

    def create_billing_package(self, payload: dict) -> dict:
        response = self._client.post("/billing-packages", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_billing_package(self, package_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/billing-packages/{package_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_billing_package(self, package_id: str) -> dict:
        response = self._client.delete(f"/billing-packages/{package_id}", headers=self._headers())
        return self._handle_response(response)

    def replace_billing_package_items(self, package_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/billing-packages/{package_id}/items", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def list_service_sub_categories(self, category_id: str | None = None) -> list:
        params: dict[str, Any] = {}
        if category_id:
            params["category_id"] = category_id
        response = self._client.get("/service-sub-categories", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_service_sub_category(self, sub_category_id: str) -> dict:
        response = self._client.get(f"/service-sub-categories/{sub_category_id}", headers=self._headers())
        return self._handle_response(response)

    def create_service_sub_category(self, payload: dict) -> dict:
        response = self._client.post("/service-sub-categories", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_service_sub_category(self, sub_category_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/service-sub-categories/{sub_category_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_service_sub_category(self, sub_category_id: str) -> dict:
        response = self._client.delete(
            f"/service-sub-categories/{sub_category_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_billing_catalog_services(
        self,
        *,
        category_id: str | None = None,
        sub_category_id: str | None = None,
        search: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if category_id:
            params["category_id"] = category_id
        if sub_category_id:
            params["sub_category_id"] = sub_category_id
        if search:
            params["search"] = search
        response = self._client.get("/opd-bills/catalog/services", params=params, headers=self._headers())
        return self._handle_response(response)

    def create_opd_bill(self, payload: dict) -> dict:
        response = self._client.post("/opd-bills", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_opd_bill(self, bill_id: str) -> dict:
        response = self._client.get(f"/opd-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def get_opd_bill_by_no(self, bill_no: str) -> dict:
        response = self._client.get(
            f"/opd-bills/by-no/{bill_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_opd_bill(self, bill_id: str, payload: dict) -> dict:
        response = self._client.put(f"/opd-bills/{bill_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def cancel_opd_bill(self, bill_id: str, reason: str) -> dict:
        response = self._client.post(
            f"/opd-bills/{bill_id}/cancel",
            json={"reason": reason},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_opd_bills_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        response = self._client.get("/opd-bills/by-patient", params=params, headers=self._headers())
        return self._handle_response(response)

    def list_opd_tokens(
        self,
        *,
        doctor_id: str | None = None,
        token_date: str | None = None,
        token_session: str | None = None,
        visit_category: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if doctor_id:
            params["doctor_id"] = doctor_id
        if token_date:
            params["token_date"] = token_date
        if token_session:
            params["token_session"] = token_session
        if visit_category:
            params["visit_category"] = visit_category
        response = self._client.get("/opd-bills/tokens", params=params, headers=self._headers())
        return self._handle_response(response)

    def list_ipd_admissions(
        self, *, status: str | None = None, search: str | None = None, patient_id: str | None = None
    ) -> list:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if patient_id:
            params["patient_id"] = patient_id
        response = self._client.get("/ipd-admissions", params=params, headers=self._headers())
        return self._handle_response(response)

    def create_ipd_admission(self, payload: dict) -> dict:
        response = self._client.post("/ipd-admissions", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_ipd_admission(self, admission_id: str) -> dict:
        response = self._client.get(f"/ipd-admissions/{admission_id}", headers=self._headers())
        return self._handle_response(response)

    def get_ipd_admission_by_no(self, admission_no: str) -> dict:
        response = self._client.get(
            f"/ipd-admissions/by-no/{admission_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_ipd_discharge_catalog_services(
        self,
        *,
        category_id: str | None = None,
        sub_category_id: str | None = None,
        search: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if category_id:
            params["category_id"] = category_id
        if sub_category_id:
            params["sub_category_id"] = sub_category_id
        if search:
            params["search"] = search
        response = self._client.get(
            "/ipd-discharge/catalog/services", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def create_ipd_discharge(self, payload: dict) -> dict:
        response = self._client.post("/ipd-discharge", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_ipd_discharge(self, bill_id: str) -> dict:
        response = self._client.get(f"/ipd-discharge/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def get_ipd_discharge_by_no(self, bill_no: str) -> dict:
        response = self._client.get(
            f"/ipd-discharge/by-no/{bill_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_ipd_discharge(self, bill_id: str, payload: dict) -> dict:
        response = self._client.put(f"/ipd-discharge/{bill_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def cancel_ipd_discharge(self, bill_id: str, reason: str) -> dict:
        response = self._client.post(
            f"/ipd-discharge/{bill_id}/cancel",
            json={"reason": reason},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_ipd_discharges_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        response = self._client.get("/ipd-discharge/by-patient", params=params, headers=self._headers())
        return self._handle_response(response)

    def list_discharge_summaries(
        self,
        *,
        search: str | None = None,
        patient_id: str | None = None,
        patient_no: str | None = None,
        admission_id: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if search:
            params["search"] = search
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        if admission_id:
            params["admission_id"] = admission_id
        response = self._client.get(
            "/ipd-discharge-summaries", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def create_discharge_summary(self, payload: dict) -> dict:
        response = self._client.post(
            "/ipd-discharge-summaries", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def get_discharge_summary(self, summary_id: str) -> dict:
        response = self._client.get(
            f"/ipd-discharge-summaries/{summary_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def get_discharge_summary_by_no(self, summary_no: str) -> dict:
        response = self._client.get(
            f"/ipd-discharge-summaries/by-no/{summary_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_discharge_summary_by_admission(self, admission_id: str) -> dict:
        response = self._client.get(
            f"/ipd-discharge-summaries/by-admission/{admission_id}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_discharge_summary(self, summary_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/ipd-discharge-summaries/{summary_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def expand_pathology_service(
        self, service_code: str, *, patient_id: str | None = None
    ) -> list:
        params: dict[str, Any] = {}
        if patient_id:
            params["patient_id"] = patient_id
        response = self._client.get(
            f"/pathology-bills/expand/{service_code.strip()}",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_pathology_catalog_services(
        self,
        *,
        sub_category_id: str | None = None,
        search: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if sub_category_id:
            params["sub_category_id"] = sub_category_id
        if search:
            params["search"] = search
        response = self._client.get(
            "/pathology-bills/catalog/services", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def list_pathology_bills(
        self,
        *,
        bill_date: str | None = None,
        search: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if bill_date:
            params["bill_date"] = bill_date
        if search:
            params["search"] = search
        response = self._client.get("/pathology-bills", params=params, headers=self._headers())
        return self._handle_response(response)

    def create_pathology_bill(self, payload: dict) -> dict:
        response = self._client.post("/pathology-bills", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_pathology_bill(self, bill_id: str) -> dict:
        response = self._client.get(f"/pathology-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def get_pathology_bill_by_no(self, bill_no: str) -> dict:
        response = self._client.get(
            f"/pathology-bills/by-no/{bill_no.strip()}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_pathology_bills_by_patient(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if patient_id:
            params["patient_id"] = patient_id
        if patient_no:
            params["patient_no"] = patient_no
        response = self._client.get(
            "/pathology-bills/by-patient", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def update_pathology_bill(self, bill_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/pathology-bills/{bill_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def cancel_pathology_bill(self, bill_id: str, reason: str) -> dict:
        response = self._client.post(
            f"/pathology-bills/{bill_id}/cancel",
            json={"reason": reason},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def download_report_file(self, endpoint: str) -> bytes:
        response = self._client.get(endpoint, headers=self._headers())
        if response.is_success:
            return response.content
        detail = "Request failed"
        try:
            body = response.json()
            detail = _format_detail(body.get("detail", detail))
        except Exception:
            detail = response.text or detail
        raise ApiError(detail, status_code=response.status_code)

    def export_html_to_excel(self, *, html: str, title: str = "Report") -> bytes:
        response = self._client.post(
            "/reports/excel-from-html",
            json={"html": html, "title": title},
            headers=self._headers(),
        )
        if response.is_success:
            return response.content
        detail = "Request failed"
        try:
            body = response.json()
            detail = _format_detail(body.get("detail", detail))
        except Exception:
            detail = response.text or detail
        raise ApiError(detail, status_code=response.status_code)

    def get_form_3c_report(
        self,
        *,
        billing_type_id: str,
        from_date: str,
        to_date: str,
    ) -> dict:
        params = {
            "billing_type_id": billing_type_id,
            "from_date": from_date,
            "to_date": to_date,
        }
        response = self._client.get(
            "/reports/form-3c",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def form_3c_report_endpoint(
        self,
        *,
        billing_type_id: str,
        from_date: str,
        to_date: str,
    ) -> str:
        params = [
            f"billing_type_id={billing_type_id}",
            f"from_date={from_date}",
            f"to_date={to_date}",
        ]
        return f"/reports/form-3c?{'&'.join(params)}"

    def get_cancellation_bill_report(
        self,
        *,
        from_date: str,
        to_date: str,
        bill_type: str = "all",
    ) -> dict:
        params = {
            "from_date": from_date,
            "to_date": to_date,
            "bill_type": bill_type,
        }
        response = self._client.get(
            "/reports/cancellation-bills",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def cancellation_bill_report_endpoint(
        self,
        *,
        from_date: str,
        to_date: str,
        bill_type: str = "all",
    ) -> str:
        params = [
            f"from_date={from_date}",
            f"to_date={to_date}",
            f"bill_type={bill_type}",
        ]
        return f"/reports/cancellation-bills?{'&'.join(params)}"

    def get_modification_bill_report(
        self,
        *,
        from_date: str,
        to_date: str,
        bill_type: str = "all",
    ) -> dict:
        params = {
            "from_date": from_date,
            "to_date": to_date,
            "bill_type": bill_type,
        }
        response = self._client.get(
            "/reports/modification-bills",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def modification_bill_report_endpoint(
        self,
        *,
        from_date: str,
        to_date: str,
        bill_type: str = "all",
    ) -> str:
        params = [
            f"from_date={from_date}",
            f"to_date={to_date}",
            f"bill_type={bill_type}",
        ]
        return f"/reports/modification-bills?{'&'.join(params)}"

    def list_short_bill_types(self) -> list:
        response = self._client.get("/short-bills/types", headers=self._headers())
        return self._handle_response(response)

    def get_short_bill_type_by_menu(self, menu_code: str) -> dict:
        response = self._client.get(
            f"/short-bills/types/by-menu/{menu_code}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_short_bill_type(self, payload: dict) -> dict:
        response = self._client.post("/short-bills/types", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_short_bill_type(self, type_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/short-bills/types/{type_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_short_bill_type(self, type_id: str) -> dict:
        response = self._client.delete(
            f"/short-bills/types/{type_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def create_short_bill(self, payload: dict) -> dict:
        response = self._client.post("/short-bills", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_short_bill(self, bill_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/short-bills/{bill_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_short_bill(self, bill_id: str) -> dict:
        response = self._client.delete(f"/short-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def get_short_bill(self, bill_id: str) -> dict:
        response = self._client.get(f"/short-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def search_short_bills(self, *, short_bill_type_id: str, query: str) -> list:
        response = self._client.get(
            "/short-bills/search",
            params={"short_bill_type_id": short_bill_type_id, "q": query},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def short_bill_print_endpoint(self, bill_id: str) -> str:
        return f"/reports/short-bill/{bill_id}"

    def get_short_bill_report(
        self,
        *,
        short_bill_type_id: str,
        from_date: str,
        to_date: str,
    ) -> dict:
        response = self._client.get(
            "/short-bills/report",
            params={
                "short_bill_type_id": short_bill_type_id,
                "from_date": from_date,
                "to_date": to_date,
            },
            headers=self._headers(),
        )
        return self._handle_response(response)

    def short_bill_report_endpoint(
        self,
        *,
        short_bill_type_id: str,
        from_date: str,
        to_date: str,
    ) -> str:
        params = [
            f"short_bill_type_id={short_bill_type_id}",
            f"from_date={from_date}",
            f"to_date={to_date}",
        ]
        return f"/reports/short-bill?{'&'.join(params)}"

    def list_single_service_opd_options(self) -> list:
        response = self._client.get("/single-service-opd/options", headers=self._headers())
        return self._handle_response(response)

    def get_single_service_opd_option_by_menu(self, menu_code: str) -> dict:
        response = self._client.get(
            f"/single-service-opd/options/by-menu/{menu_code}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_single_service_opd_option(self, payload: dict) -> dict:
        response = self._client.post(
            "/single-service-opd/options", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def update_single_service_opd_option(self, option_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/single-service-opd/options/{option_id}",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_single_service_opd_bill(self, payload: dict) -> dict:
        response = self._client.post(
            "/single-service-opd/bills", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def list_single_service_opd_bills(self, *, option_id: str, bill_date: str) -> list:
        response = self._client.get(
            "/single-service-opd/bills",
            params={"option_id": option_id, "bill_date": bill_date},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def cancel_single_service_opd_bill(self, bill_id: str) -> dict:
        response = self._client.delete(
            f"/single-service-opd/bills/{bill_id}",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_user_cash_transaction_report(
        self,
        *,
        user_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        report_type: str = "detail",
        payment_mode_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"report_type": report_type}
        if user_id:
            params["user_id"] = user_id
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if payment_mode_id:
            params["payment_mode_id"] = payment_mode_id
        response = self._client.get(
            "/reports/user-cash-transaction",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def user_cash_transaction_report_endpoint(
        self,
        *,
        user_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        report_type: str = "detail",
        payment_mode_id: str | None = None,
    ) -> str:
        from urllib.parse import urlencode

        params: list[tuple[str, str]] = [("report_type", report_type)]
        if user_id:
            params.append(("user_id", user_id))
        if from_date:
            params.append(("from_date", from_date))
        if to_date:
            params.append(("to_date", to_date))
        if payment_mode_id:
            params.append(("payment_mode_id", payment_mode_id))
        return f"/reports/user-cash-transaction?{urlencode(params)}"

    def get_doctor_collection_report(
        self,
        *,
        from_date: str,
        to_date: str,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
        report_type: str = "sharing",
    ) -> dict:
        params: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "report_type": report_type,
        }
        if doctor_ids:
            params["doctor_ids"] = doctor_ids
        if service_ids:
            params["service_ids"] = service_ids
        if payment_modes:
            params["payment_modes"] = payment_modes
        response = self._client.get(
            "/reports/doctor-collection",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def doctor_collection_report_endpoint(
        self,
        *,
        from_date: str,
        to_date: str,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
        report_type: str = "sharing",
    ) -> str:
        from urllib.parse import urlencode

        params: list[tuple[str, str]] = [
            ("from_date", from_date),
            ("to_date", to_date),
            ("report_type", report_type),
        ]
        if doctor_ids:
            params.extend(("doctor_ids", doctor_id) for doctor_id in doctor_ids)
        if service_ids:
            params.extend(("service_ids", service_id) for service_id in service_ids)
        if payment_modes:
            params.extend(("payment_modes", mode) for mode in payment_modes)
        return f"/reports/doctor-collection?{urlencode(params)}"

    def lookup_bill_identity(self, *, bill_type: str, bill_no: str) -> dict:
        response = self._client.get(
            "/bill-identity/lookup",
            params={"bill_type": bill_type, "bill_no": bill_no},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def update_bill_identity(self, payload: dict) -> dict:
        response = self._client.post(
            "/bill-identity",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_pathology_collection_report(
        self,
        *,
        from_date: str,
        to_date: str,
        doctor_ids: list[str] | None = None,
        referral_names: list[str] | None = None,
        report_type: str = "normal",
    ) -> dict:
        params: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "report_type": report_type,
        }
        if doctor_ids:
            params["doctor_ids"] = doctor_ids
        if referral_names:
            params["referral_names"] = referral_names
        response = self._client.get(
            "/reports/pathology-collection",
            params=params,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_pathology_referring_doctors(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[str]:
        params: dict[str, Any] = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        response = self._client.get(
            "/reports/pathology-collection/referring-doctors",
            params=params or None,
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return list(data.get("items") or [])

    def pathology_collection_report_endpoint(
        self,
        *,
        from_date: str,
        to_date: str,
        doctor_ids: list[str] | None = None,
        referral_names: list[str] | None = None,
        report_type: str = "normal",
    ) -> str:
        from urllib.parse import urlencode

        params: list[tuple[str, str]] = [
            ("from_date", from_date),
            ("to_date", to_date),
            ("report_type", report_type),
        ]
        if doctor_ids:
            params.extend(("doctor_ids", doctor_id) for doctor_id in doctor_ids)
        if referral_names:
            params.extend(("referral_names", name) for name in referral_names)
        return f"/reports/pathology-collection?{urlencode(params)}"

    def download_report_pdf(self, endpoint: str) -> bytes:
        return self.download_report_file(endpoint)

    def download_report_html(self, endpoint: str) -> str:
        response = self._client.get(endpoint, headers=self._headers())
        if response.is_success:
            return response.text
        detail = "Request failed"
        try:
            body = response.json()
            detail = _format_detail(body.get("detail", detail))
        except Exception:
            detail = response.text or detail
        raise ApiError(detail, status_code=response.status_code)

    def report_url(self, endpoint: str) -> str:
        return f"{self.config.api_base}{endpoint}"

    def list_pathology_units(self) -> list:
        response = self._client.get("/pathology/units", headers=self._headers())
        return self._handle_response(response)

    def create_pathology_unit(self, payload: dict) -> dict:
        response = self._client.post("/pathology/units", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pathology_unit(self, unit_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/pathology/units/{unit_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_pathology_unit(self, unit_id: str) -> dict:
        response = self._client.delete(f"/pathology/units/{unit_id}", headers=self._headers())
        return self._handle_response(response)

    def list_pathology_parameters(self) -> list:
        response = self._client.get("/pathology/parameters", headers=self._headers())
        return self._handle_response(response)

    def create_pathology_parameter(self, payload: dict) -> dict:
        response = self._client.post("/pathology/parameters", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pathology_parameter(self, parameter_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pathology/parameters/{parameter_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pathology_parameter(self, parameter_id: str) -> dict:
        response = self._client.delete(
            f"/pathology/parameters/{parameter_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_pathology_service_parameters(self, *, service_id: str | None = None) -> list:
        params: dict[str, Any] = {}
        if service_id:
            params["service_id"] = service_id
        response = self._client.get(
            "/pathology/service-parameters", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def create_pathology_service_parameter(self, payload: dict) -> dict:
        response = self._client.post(
            "/pathology/service-parameters", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pathology_service_parameter(self, mapping_id: str) -> dict:
        response = self._client.delete(
            f"/pathology/service-parameters/{mapping_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_pathology_normal_ranges(self, *, parameter_id: str | None = None) -> list:
        params: dict[str, Any] = {}
        if parameter_id:
            params["parameter_id"] = parameter_id
        response = self._client.get(
            "/pathology/normal-ranges", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def create_pathology_normal_range(self, payload: dict) -> dict:
        response = self._client.post("/pathology/normal-ranges", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pathology_normal_range(self, range_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pathology/normal-ranges/{range_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pathology_normal_range(self, range_id: str) -> dict:
        response = self._client.delete(
            f"/pathology/normal-ranges/{range_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_service_notes(self) -> list:
        response = self._client.get("/pathology/notes", headers=self._headers())
        return self._handle_response(response)

    def create_service_note(self, payload: dict) -> dict:
        response = self._client.post("/pathology/notes", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_service_note(self, note_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pathology/notes/{note_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_service_note(self, note_id: str) -> dict:
        response = self._client.delete(
            f"/pathology/notes/{note_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_pathology_lab_services(self) -> list:
        response = self._client.get("/pathology/lab-services", headers=self._headers())
        return self._handle_response(response)

    # ----- lab tests (unified test + ranges) ------------------------------
    def list_lab_tests(self) -> list:
        response = self._client.get("/pathology/lab-tests", headers=self._headers())
        return self._handle_response(response)

    def create_lab_test(self, payload: dict) -> dict:
        response = self._client.post(
            "/pathology/lab-tests", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def update_lab_test(self, test_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/pathology/lab-tests/{test_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_lab_test(self, test_id: str) -> None:
        response = self._client.delete(
            f"/pathology/lab-tests/{test_id}", headers=self._headers()
        )
        self._handle_response(response)

    # ----- test profiles / panels -----------------------------------------
    def list_lab_profiles(self) -> list:
        response = self._client.get("/pathology/profiles", headers=self._headers())
        return self._handle_response(response)

    def create_lab_profile(self, payload: dict) -> dict:
        response = self._client.post(
            "/pathology/profiles", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def update_lab_profile(self, profile_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/pathology/profiles/{profile_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_lab_profile(self, profile_id: str) -> None:
        response = self._client.delete(
            f"/pathology/profiles/{profile_id}", headers=self._headers()
        )
        self._handle_response(response)

    def create_pathology_lab_service(self, payload: dict) -> dict:
        response = self._client.post("/pathology/lab-services", json=payload, headers=self._headers())
        return self._handle_response(response)

    def list_pathology_result_templates(
        self,
        *,
        parameter_id: str | None = None,
        service_id: str | None = None,
    ) -> list:
        params: dict[str, Any] = {}
        if parameter_id:
            params["parameter_id"] = parameter_id
        if service_id:
            params["service_id"] = service_id
        response = self._client.get("/pathology/result-templates", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_pathology_result_template(self, template_id: str) -> dict:
        response = self._client.get(
            f"/pathology/result-templates/{template_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def create_pathology_result_template(self, payload: dict) -> dict:
        response = self._client.post(
            "/pathology/result-templates", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def update_pathology_result_template(self, template_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pathology/result-templates/{template_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pathology_result_template(self, template_id: str) -> dict:
        response = self._client.delete(
            f"/pathology/result-templates/{template_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def list_pathology_work_list(self, *, bill_date: str | None = None) -> list:
        params: dict[str, Any] = {}
        if bill_date:
            params["bill_date"] = bill_date
        response = self._client.get("/pathology/work-list", params=params, headers=self._headers())
        return self._handle_response(response)

    def get_pathology_order(self, bill_id: str) -> dict:
        response = self._client.get(
            f"/pathology/orders/by-bill/{bill_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def update_pathology_results(self, bill_id: str, payload: dict) -> dict:
        response = self._client.put(
            f"/pathology/orders/by-bill/{bill_id}/results",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(response)

    def authorize_pathology_order(self, bill_id: str) -> dict:
        response = self._client.post(
            f"/pathology/orders/by-bill/{bill_id}/authorize", headers=self._headers()
        )
        return self._handle_response(response)

    def preview_next_patient_id(self, hospital_section_id: str | None = None) -> dict:
        params: dict[str, Any] = {}
        if hospital_section_id:
            params["hospital_section_id"] = hospital_section_id
        response = self._client.get(
            "/patients/next-id-preview", params=params, headers=self._headers()
        )
        return self._handle_response(response)

    def list_patients(self, *, page: int = 1, page_size: int = 50, search: str | None = None) -> dict:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        response = self._client.get("/patients", params=params, headers=self._headers())
        return self._handle_response(response)

    def search_patients(
        self,
        *,
        patient_no: str | None = None,
        first_name: str | None = None,
        middle_name: str | None = None,
        last_name: str | None = None,
        village: str | None = None,
        post: str | None = None,
        taluk: str | None = None,
        district: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        mobile2: str | None = None,
        pin_code: str | None = None,
        old_id: str | None = None,
        aadhar_no: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        for key, value in (
            ("patient_no", patient_no),
            ("first_name", first_name),
            ("middle_name", middle_name),
            ("last_name", last_name),
            ("village", village),
            ("post", post),
            ("taluk", taluk),
            ("district", district),
            ("phone", phone),
            ("mobile", mobile),
            ("mobile2", mobile2),
            ("pin_code", pin_code),
            ("old_id", old_id),
            ("aadhar_no", aadhar_no),
        ):
            if value:
                params[key] = value
        response = self._client.get("/patients/search", params=params, headers=self._headers())
        return self._handle_response(response)

    def create_patient(self, payload: dict) -> dict:
        response = self._client.post("/patients", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_patient(self, patient_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/patients/{patient_id}", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_patient(self, patient_id: str) -> dict:
        response = self._client.get(f"/patients/{patient_id}", headers=self._headers())
        return self._handle_response(response)

    def upload_patient_aadhar_scan(self, patient_id: str, file_path: str) -> dict:
        filename = file_path.split("\\")[-1].split("/")[-1]
        with open(file_path, "rb") as handle:
            response = self._client.post(
                f"/patients/{patient_id}/aadhar-scan",
                files={"file": (filename, handle, "application/octet-stream")},
                headers=self._headers(),
            )
        return self._handle_response(response)

    def patient_aadhar_scan_url(self, patient_id: str) -> str:
        return f"{self.config.api_base}/patients/{patient_id}/aadhar-scan"

    def list_patient_documents(self, *, patient_id: str) -> list:
        response = self._client.get(
            "/patient-documents",
            params={"patient_id": patient_id},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def upload_patient_document(
        self,
        *,
        patient_id: str,
        file_path: str,
        page_count: int = 1,
        scanner_name: str | None = None,
        document_date: str | None = None,
        remarks: str | None = None,
        original_name: str | None = None,
    ) -> dict:
        filename = original_name or file_path.split("\\")[-1].split("/")[-1]
        data: dict[str, Any] = {
            "patient_id": patient_id,
            "page_count": str(page_count),
        }
        if scanner_name:
            data["scanner_name"] = scanner_name
        if document_date:
            data["document_date"] = document_date
        if remarks:
            data["remarks"] = remarks
        if original_name:
            data["original_name"] = original_name
        with open(file_path, "rb") as handle:
            response = self._client.post(
                "/patient-documents",
                data=data,
                files={"file": (filename, handle, "application/pdf")},
                headers=self._headers(),
                timeout=120.0,
            )
        return self._handle_response(response)

    def download_patient_document_file(self, document_id: str) -> bytes:
        response = self._client.get(
            f"/patient-documents/{document_id}/file",
            headers=self._headers(),
            timeout=120.0,
        )
        if response.is_success:
            return response.content
        detail = "Request failed"
        try:
            body = response.json()
            detail = _format_detail(body.get("detail", detail))
        except Exception:
            detail = response.text or detail
        raise ApiError(detail, status_code=response.status_code)

    def mark_patient_document_viewed(self, document_id: str) -> dict:
        response = self._client.post(
            f"/patient-documents/{document_id}/view",
            headers=self._headers(),
        )
        return self._handle_response(response)

    def list_pharmacy_code_masters(self, master_type: str) -> list:
        response = self._client.get(
            "/pharmacy/code-masters",
            params={"master_type": master_type},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_pharmacy_code_master(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/code-masters", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pharmacy_code_master(self, record_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pharmacy/code-masters/{record_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pharmacy_code_master(self, record_id: str) -> dict:
        response = self._client.delete(f"/pharmacy/code-masters/{record_id}", headers=self._headers())
        return self._handle_response(response)

    def list_pharmacy_items(self, item_type: str) -> list:
        response = self._client.get(
            "/pharmacy/items",
            params={"item_type": item_type},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def search_pharmacy_medicines(self, query: str, item_type: str = "MD", limit: int = 25) -> list:
        response = self._client.get(
            "/pharmacy/items/search",
            params={"q": query, "item_type": item_type, "limit": limit},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_pharmacy_item(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/items", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pharmacy_item(self, record_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pharmacy/items/{record_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pharmacy_item(self, record_id: str) -> dict:
        response = self._client.delete(f"/pharmacy/items/{record_id}", headers=self._headers())
        return self._handle_response(response)

    def list_pharmacy_suppliers(self) -> list:
        response = self._client.get("/pharmacy/suppliers", headers=self._headers())
        return self._handle_response(response)

    def create_pharmacy_supplier(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/suppliers", json=payload, headers=self._headers())
        return self._handle_response(response)

    def update_pharmacy_supplier(self, record_id: str, payload: dict) -> dict:
        response = self._client.patch(
            f"/pharmacy/suppliers/{record_id}", json=payload, headers=self._headers()
        )
        return self._handle_response(response)

    def delete_pharmacy_supplier(self, record_id: str) -> dict:
        response = self._client.delete(f"/pharmacy/suppliers/{record_id}", headers=self._headers())
        return self._handle_response(response)

    def list_pharmacy_group_mappings(self, group_id: str) -> list:
        response = self._client.get(
            "/pharmacy/group-mappings",
            params={"group_id": group_id},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def create_pharmacy_group_mapping(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/group-mappings", json=payload, headers=self._headers())
        return self._handle_response(response)

    def delete_pharmacy_group_mapping(self, mapping_id: str) -> dict:
        response = self._client.delete(
            f"/pharmacy/group-mappings/{mapping_id}", headers=self._headers()
        )
        return self._handle_response(response)

    def create_pharmacy_sale_bill(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/sale-bills", json=payload, headers=self._headers())
        return self._handle_response(response)

    def pharmacy_last_sale_bill_info(self) -> dict:
        response = self._client.get("/pharmacy/sale-bills/last-info", headers=self._headers())
        return self._handle_response(response)

    def pharmacy_stock_lookup(self, code: str, item_type: str = "MD") -> dict:
        response = self._client.get(
            "/pharmacy/stock-lookup",
            params={"code": code, "item_type": item_type},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def get_pharmacy_sale_bill(self, bill_id: str) -> dict:
        response = self._client.get(f"/pharmacy/sale-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def create_pharmacy_purchase_bill(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/purchase-bills", json=payload, headers=self._headers())
        return self._handle_response(response)

    def create_pharmacy_purchase_return(self, payload: dict) -> dict:
        body = {**payload, "bill_kind": "return"}
        response = self._client.post("/pharmacy/purchase-returns", json=body, headers=self._headers())
        return self._handle_response(response)

    def create_pharmacy_indent(self, payload: dict) -> dict:
        response = self._client.post("/pharmacy/indents", json=payload, headers=self._headers())
        return self._handle_response(response)

    def get_pharmacy_purchase_bill(self, bill_id: str) -> dict:
        response = self._client.get(f"/pharmacy/purchase-bills/{bill_id}", headers=self._headers())
        return self._handle_response(response)

    def pharmacy_sales_register(self, from_date: str, to_date: str) -> list:
        response = self._client.get(
            "/pharmacy/reports/sales-register",
            params={"from_date": from_date, "to_date": to_date},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def pharmacy_sales_summary(self, from_date: str, to_date: str) -> list:
        response = self._client.get(
            "/pharmacy/reports/sales-summary",
            params={"from_date": from_date, "to_date": to_date},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def pharmacy_schedule_h_report(self, from_date: str, to_date: str) -> list:
        response = self._client.get(
            "/pharmacy/reports/schedule-h",
            params={"from_date": from_date, "to_date": to_date},
            headers=self._headers(),
        )
        return self._handle_response(response)

    def pharmacy_stock_report(self) -> list:
        response = self._client.get("/pharmacy/reports/stock", headers=self._headers())
        return self._handle_response(response)

    # ----- admin / database maintenance -----------------------------------
    def list_db_tables(self) -> list:
        response = self._client.get("/admin/db-tables", headers=self._headers())
        return self._handle_response(response)

    def clear_db_tables(self, *, password: str, tables: list[str]) -> dict:
        response = self._client.post(
            "/admin/clear-tables",
            json={"password": password, "tables": tables},
            headers=self._headers(),
            timeout=120.0,
        )
        return self._handle_response(response)

    # ----- admin / legacy MySQL → PostgreSQL migration --------------------
    def legacy_migrate_defaults(self) -> dict:
        response = self._client.get("/admin/legacy-migrate/defaults", headers=self._headers())
        return self._handle_response(response)

    def legacy_migrate_test_mysql(self, mysql_connection_string: str) -> dict:
        response = self._client.post(
            "/admin/legacy-migrate/test-mysql",
            json={"mysql_connection_string": mysql_connection_string},
            headers=self._headers(),
            timeout=30.0,
        )
        return self._handle_response(response)

    def legacy_migrate_test_postgres(self, postgres_connection_string: str) -> dict:
        response = self._client.post(
            "/admin/legacy-migrate/test-postgres",
            json={"postgres_connection_string": postgres_connection_string},
            headers=self._headers(),
            timeout=30.0,
        )
        return self._handle_response(response)

    def legacy_migrate_preview(self, *, mysql_connection_string: str, mappings: list) -> dict:
        response = self._client.post(
            "/admin/legacy-migrate/preview",
            json={"mysql_connection_string": mysql_connection_string, "mappings": mappings},
            headers=self._headers(),
            timeout=60.0,
        )
        return self._handle_response(response)

    def legacy_migrate_run(
        self,
        *,
        password: str,
        mysql_connection_string: str,
        postgres_connection_string: str,
        selected_keys: list[str],
        mappings: list,
        replace_existing: bool = False,
        dry_run: bool = False,
    ) -> dict:
        response = self._client.post(
            "/admin/legacy-migrate/run",
            json={
                "password": password,
                "mysql_connection_string": mysql_connection_string,
                "postgres_connection_string": postgres_connection_string,
                "selected_keys": selected_keys,
                "mappings": mappings,
                "replace_existing": replace_existing,
                "dry_run": dry_run,
            },
            headers=self._headers(),
            timeout=600.0,
        )
        return self._handle_response(response)

    def legacy_migrate_run_stream(
        self,
        *,
        password: str,
        mysql_connection_string: str,
        postgres_connection_string: str,
        selected_keys: list[str],
        mappings: list,
        replace_existing: bool = False,
        dry_run: bool = False,
    ) -> Iterator[dict]:
        """Yield progress events until the migration finishes."""
        timeout = httpx.Timeout(30.0, read=None)
        with self._client.stream(
            "POST",
            "/admin/legacy-migrate/run-stream",
            json={
                "password": password,
                "mysql_connection_string": mysql_connection_string,
                "postgres_connection_string": postgres_connection_string,
                "selected_keys": selected_keys,
                "mappings": mappings,
                "replace_existing": replace_existing,
                "dry_run": dry_run,
            },
            headers={**self._headers(), "Accept": "application/x-ndjson"},
            timeout=timeout,
        ) as response:
            if not response.is_success:
                response.read()
                self._handle_response(response)
                return
            for line in response.iter_lines():
                text = (line or "").strip()
                if not text:
                    continue
                yield json.loads(text)
