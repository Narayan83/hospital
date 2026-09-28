from app.api_client.client import ApiClient, ApiError


class PatientController:
    """Coordinates UI actions with backend API — no business logic here."""

    def __init__(self, api: ApiClient | None = None):
        self._api = api or ApiClient()
        self._owns_api = api is None

    def close(self) -> None:
        if self._owns_api:
            self._api.close()

    @property
    def api(self) -> ApiClient:
        return self._api

    def check_connection(self) -> tuple[bool, str]:
        try:
            result = self._api.health_check()
            return True, result.get("status", "ok")
        except Exception as exc:
            return False, str(exc)

    def load_patients(self, search: str | None = None) -> tuple[list[dict], str | None]:
        try:
            result = self._api.list_patients(search=search or None)
            return result.get("items", []), None
        except ApiError as exc:
            return [], str(exc)
        except Exception as exc:
            return [], f"Connection error: {exc}"

    def get_patient(self, patient_id: str) -> tuple[dict | None, str | None]:
        try:
            return self._api.get_patient(patient_id), None
        except ApiError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Connection error: {exc}"

    def preview_next_patient_id(
        self, hospital_section_id: str | None = None
    ) -> tuple[dict | None, str | None]:
        try:
            return self._api.preview_next_patient_id(hospital_section_id), None
        except ApiError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Connection error: {exc}"

    def register_patient(self, data: dict) -> tuple[dict | None, str | None]:
        try:
            patient = self._api.create_patient(data)
            return patient, None
        except ApiError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Connection error: {exc}"

    def update_patient(self, patient_id: str, data: dict) -> tuple[dict | None, str | None]:
        try:
            patient = self._api.update_patient(patient_id, data)
            return patient, None
        except ApiError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Connection error: {exc}"

    def upload_aadhar_scan(self, patient_id: str, file_path: str) -> tuple[dict | None, str | None]:
        try:
            patient = self._api.upload_patient_aadhar_scan(patient_id, file_path)
            return patient, None
        except ApiError as exc:
            return None, str(exc)
        except Exception as exc:
            return None, f"Connection error: {exc}"
