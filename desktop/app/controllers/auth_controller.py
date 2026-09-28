import time

from app.api_client.client import ApiClient, ApiError
from app.perf_log import step
from app.services.master_cache import apply_master_cache, load_master_cache
from app.session import clear_session, set_session


class AuthController:
    def __init__(self, api: ApiClient | None = None):
        self._api = api or ApiClient()
        self._owns_api = api is None

    def close(self) -> None:
        if self._owns_api:
            self._api.close()

    def check_connection(self) -> tuple[bool, str]:
        try:
            result = self._api.health_check()
            return True, result.get("status", "ok")
        except Exception as exc:
            return False, str(exc)

    def login(self, email: str, password: str) -> str | None:
        try:
            t0 = time.perf_counter()
            result = self._api.login(email.strip(), password)
            perf = result.pop("_hms_perf", {})
            step(
                "API POST /auth/login",
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                network_ms=perf.get("network_ms"),
                parse_ms=perf.get("parse_ms"),
                response_kb=perf.get("response_kb"),
                menus=len(result.get("menus") or []),
            )

            t1 = time.perf_counter()
            set_session(
                access_token=result["access_token"],
                user=result["user"],
                menus=result.get("menus", []),
            )
            step("set_session", elapsed_ms=int((time.perf_counter() - t1) * 1000))

            app_data = result.get("app_data")
            if app_data:
                t2 = time.perf_counter()
                apply_master_cache(app_data)
                step(
                    "apply_master_cache",
                    elapsed_ms=int((time.perf_counter() - t2) * 1000),
                    doctors=len(app_data.get("doctors") or []),
                    users=len(app_data.get("users") or []),
                )
                return None
            step("fallback load_master_cache (separate API call)")
            return load_master_cache(self._api)
        except ApiError as exc:
            step("login failed", error=str(exc))
            return str(exc)
        except Exception as exc:
            step("login failed", error=str(exc))
            return f"Connection error: {exc}"

    def logout(self) -> None:
        clear_session()
