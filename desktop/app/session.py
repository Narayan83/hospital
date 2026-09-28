from dataclasses import dataclass, field
import time


@dataclass
class MasterDataCache:
    """Loaded in background after login — screens read from here."""

    user_types: list[dict] = field(default_factory=list)
    departments: list[dict] = field(default_factory=list)
    billing_types: list[dict] = field(default_factory=list)
    procedure_types: list[dict] = field(default_factory=list)
    billing_structure: list[dict] = field(default_factory=list)
    authorities: list[dict] = field(default_factory=list)
    hospital_sections: list[dict] = field(default_factory=list)
    prefixes: list[dict] = field(default_factory=list)
    payment_modes: list[dict] = field(default_factory=list)
    wards: list[dict] = field(default_factory=list)
    doctors: list[dict] = field(default_factory=list)
    users: list[dict] = field(default_factory=list)
    roles: list[dict] = field(default_factory=list)
    patient_no_formats: list[dict] = field(default_factory=list)
    patient_services: list[dict] = field(default_factory=list)
    service_categories: list[dict] = field(default_factory=list)
    service_sub_categories: list[dict] = field(default_factory=list)
    billing_packages: list[dict] = field(default_factory=list)
    hospital_profile: dict = field(default_factory=dict)
    loading: bool = False
    loaded: bool = False
    loaded_at: float = 0.0
    error: str = ""

    def mark_loaded(self) -> None:
        self.loading = False
        self.loaded = True
        self.loaded_at = time.time()
        self.error = ""

    def mark_failed(self, message: str) -> None:
        self.loading = False
        self.loaded = False
        self.error = message


def flatten_menus(nodes: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for node in nodes:
        flat.append({
            "id": node.get("id"),
            "code": node.get("code"),
            "label": node.get("label"),
        })
        flat.extend(flatten_menus(node.get("children") or []))
    return flat


@dataclass
class UserSession:
    access_token: str = ""
    user_id: str = ""
    email: str = ""
    full_name: str = ""
    doctor_id: str | None = None
    maps_to_doctor: bool = False
    user_type_sort_order: int | None = None
    roles: list[str] = field(default_factory=list)
    menus: list[dict] = field(default_factory=list)
    flat_menus: list[dict] = field(default_factory=list)
    cache: MasterDataCache = field(default_factory=MasterDataCache)

    @property
    def is_logged_in(self) -> bool:
        return bool(self.access_token)

    def allowed_menu_codes(self) -> set[str]:
        return set(self.menu_lookup().keys())

    def menu_lookup(self) -> dict[str, dict]:
        lookup: dict[str, dict] = {}

        def walk(nodes: list[dict]) -> None:
            for node in nodes:
                code = node.get("code")
                if code:
                    lookup[code] = node
                walk(node.get("children") or [])

        walk(self.menus)
        return lookup

    def get_menu(self, code: str) -> dict | None:
        return self.menu_lookup().get(code)

    def is_super_admin(self) -> bool:
        return "Super Admin" in self.roles

    def is_admin_user_type(self) -> bool:
        return self.user_type_sort_order == 1


_session = UserSession()


def get_session() -> UserSession:
    return _session


def hospital_display_name() -> str:
    name = (_session.cache.hospital_profile or {}).get("name", "").strip()
    return name or "Hospital Management System"


def set_hospital_profile(profile: dict) -> None:
    _session.cache.hospital_profile = profile or {}


def set_session(
    *,
    access_token: str,
    user: dict,
    menus: list[dict],
) -> None:
    global _session
    _session = UserSession(
        access_token=access_token,
        user_id=user.get("id", ""),
        email=user.get("email", ""),
        full_name=user.get("full_name", ""),
        doctor_id=user.get("doctor_id"),
        maps_to_doctor=bool(user.get("maps_to_doctor")),
        user_type_sort_order=user.get("user_type_sort_order"),
        roles=user.get("roles", []),
        menus=menus,
        flat_menus=flatten_menus(menus),
    )


def clear_session() -> None:
    global _session
    _session = UserSession()
