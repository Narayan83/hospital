"""Build billing service catalogs from login cache (fast) with optional API fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.session import get_session

if TYPE_CHECKING:
    from app.api_client.client import ApiClient

LAB_CATEGORY_CODE = "LAB"


def billing_rate_for_service(svc: dict) -> object:
    if svc.get("is_sharing"):
        return svc.get("rate") or 0
    charge = svc.get("service_charge")
    if charge not in (None, "", 0, "0", "0.0", "0.00"):
        return charge
    return svc.get("rate")


def _lab_category_id() -> str | None:
    cache = get_session().cache
    return next(
        (c.get("id") for c in cache.service_categories if c.get("code") == LAB_CATEGORY_CODE),
        None,
    )


def _service_to_catalog_item(svc: dict) -> dict:
    return {
        "id": svc.get("id"),
        "code": svc.get("code"),
        "name": svc.get("name"),
        "rate": billing_rate_for_service(svc),
        "service_charge": svc.get("service_charge"),
        "is_sharing": bool(svc.get("is_sharing")),
        "doctor_id": svc.get("doctor_id"),
        "doctor_name": svc.get("doctor_name"),
        "category_id": svc.get("category_id"),
        "category_name": svc.get("category_name"),
        "sub_category_id": svc.get("sub_category_id"),
        "sub_category_name": svc.get("sub_category_name"),
        "is_renewal": svc.get("is_renewal"),
        "renewal_days": svc.get("renewal_days"),
    }


def catalog_from_cache(*, lab_only: bool) -> list[dict] | None:
    """Return all active services for OPD/IPD (non-LAB) or pathology (LAB only)."""
    cache = get_session().cache
    if not cache.loaded or not cache.patient_services:
        return None
    lab_id = _lab_category_id()
    items: list[dict] = []
    for svc in cache.patient_services:
        if not svc.get("is_active") or not svc.get("is_service_active"):
            continue
        cat_id = svc.get("category_id")
        if lab_only:
            if not lab_id or cat_id != lab_id:
                continue
        elif lab_id and cat_id == lab_id:
            continue
        items.append(_service_to_catalog_item(svc))
    items.sort(key=lambda row: (row.get("name") or "").casefold())
    return items


def filter_catalog(
    items: list[dict],
    *,
    category_id: str | None = None,
    sub_category_id: str | None = None,
    search: str | None = None,
) -> list[dict]:
    result = items
    if category_id:
        result = [row for row in result if row.get("category_id") == category_id]
    if sub_category_id:
        result = [row for row in result if row.get("sub_category_id") == sub_category_id]
    if search:
        query = search.strip().lower()
        if query:
            result = [
                row
                for row in result
                if query in (row.get("name") or "").lower()
                or query in (row.get("code") or "").lower()
            ]
    return sorted(result, key=lambda row: (row.get("name") or "").casefold())


def load_opd_catalog_from_api(
    api: ApiClient,
    *,
    category_id: str | None = None,
    sub_category_id: str | None = None,
) -> list[dict]:
    params: dict = {}
    if category_id:
        params["category_id"] = category_id
    if sub_category_id:
        params["sub_category_id"] = sub_category_id
    return api.list_billing_catalog_services(**params)


def load_ipd_catalog_from_api(
    api: ApiClient,
    *,
    category_id: str | None = None,
    sub_category_id: str | None = None,
) -> list[dict]:
    params: dict = {}
    if category_id:
        params["category_id"] = category_id
    if sub_category_id:
        params["sub_category_id"] = sub_category_id
    return api.list_ipd_discharge_catalog_services(**params)


def load_pathology_catalog_from_api(
    api: ApiClient,
    *,
    sub_category_id: str | None = None,
) -> list[dict]:
    params: dict = {}
    if sub_category_id:
        params["sub_category_id"] = sub_category_id
    return api.list_pathology_catalog_services(**params)
