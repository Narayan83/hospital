import os
from dataclasses import dataclass


def _api_url() -> str:
    base = os.getenv("BASE_URL") or os.getenv("HMS_API_URL")
    if base:
        return base.rstrip("/").replace("://localhost:", "://127.0.0.1:")
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    if host == "localhost":
        host = "127.0.0.1"
    port = os.getenv("BACKEND_PORT", "8010")
    return f"http://{host}:{port}"


@dataclass(frozen=True)
class DesktopConfig:
    api_url: str
    api_prefix: str

    @property
    def api_base(self) -> str:
        return f"{self.api_url}{self.api_prefix}"


def get_config() -> DesktopConfig:
    return DesktopConfig(
        api_url=_api_url(),
        api_prefix=os.getenv("HMS_API_PREFIX", "/api/v1"),
    )
