from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.hms_env import resolve_env_files, resolve_storage_root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=resolve_env_files() or ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Hospital Management System"
    app_env: str = "development"
    debug: bool = True
    sql_echo: bool = False
    seed_on_startup: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database — accepts postgresql:// or postgresql+asyncpg://
    database_url: str = "postgresql+asyncpg://postgres:postpass@127.0.0.1:5432/hms"

    # Server
    backend_host: str = "localhost"
    backend_port: int = 8010
    base_url: str = "http://127.0.0.1:8010"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Redis (optional — for future caching/sessions)
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    # Mail (optional — for future notifications)
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@hms.local"
    mail_server: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_tls: bool = True
    mail_ssl: bool = False

    # Reports
    reports_output_dir: Path = Path("./storage/reports")
    doctors_storage_dir: Path = Path("./storage/doctors")
    patients_storage_dir: Path = Path("./storage/patients")
    patient_documents_storage_dir: Path = Path("./storage/patient-documents")

    @model_validator(mode="after")
    def resolve_install_paths(self) -> "Settings":
        storage_root = resolve_storage_root()
        if storage_root != Path("./storage"):
            self.reports_output_dir = storage_root / "reports"
            self.doctors_storage_dir = storage_root / "doctors"
            self.patients_storage_dir = storage_root / "patients"
            self.patient_documents_storage_dir = storage_root / "patient-documents"
        return self

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Windows: use 127.0.0.1 (localhost can break asyncpg)
        value = value.replace("@localhost:", "@127.0.0.1:")
        if "127.0.0.1" in value and "ssl=" not in value:
            sep = "&" if "?" in value else "?"
            value = f"{value}{sep}ssl=disable"
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
