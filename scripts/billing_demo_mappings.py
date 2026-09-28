"""Shared demo category / package mappings for billing tests and manual QA."""
from __future__ import annotations

from typing import Any

import httpx

# service_code -> (category_code, sub_category_code)
DEMO_SERVICE_MAPPINGS: dict[str, tuple[str, str]] = {
    "D1": ("LAB", "BLOOD"),
    "D2": ("LAB", "BLOOD"),
    "D3": ("LAB", "BLOOD"),
    "D37": ("LAB", "BLOOD"),
    "D18": ("LAB", "BLOOD"),
    "D20": ("LAB", "BLOOD"),
    "D4": ("LAB", "BLOOD"),
    "D5": ("LAB", "BLOOD"),
    "D6": ("LAB", "BLOOD"),
    "S104": ("LAB", "BLOOD"),
    "S110": ("LAB", "BLOOD"),
    "S111": ("LAB", "BLOOD"),
    "S112": ("LAB", "BLOOD"),
}

DEMO_PACKAGES: list[dict[str, Any]] = [
    {
        "code": "DEMO_BASICLAB",
        "name": "Basic Lab Package (Demo)",
        "package_total": "220.00",
        "description": "Haemoglobin + Blood Group + RBS",
        "sort_order": 1,
        "items": [
            {"service_code": "D1", "quantity": 1},
            {"service_code": "D2", "quantity": 1},
            {"service_code": "D3", "quantity": 1},
        ],
    },
    {
        "code": "DEMO_COMPBLOOD",
        "name": "Complete Blood Package (Demo)",
        "package_total": "500.00",
        "description": "CBC + Haemoglobin + Blood Group + CRP",
        "sort_order": 2,
        "items": [
            {"service_code": "D37", "quantity": 1},
            {"service_code": "D1", "quantity": 1},
            {"service_code": "D2", "quantity": 1},
            {"service_code": "D20", "quantity": 1},
        ],
    },
]


def _index_by_code(items: list[dict], key: str = "code") -> dict[str, dict]:
    return {str(item[key]).upper(): item for item in items}


def apply_demo_mappings(client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
    """Upsert category assignments and demo packages. Returns ids for assertions."""
    categories = _index_by_code(client.get("/service-categories", headers=headers).json())
    sub_categories = client.get("/service-sub-categories", headers=headers).json()
    sub_by_cat_code: dict[tuple[str, str], dict] = {}
    for sub in sub_categories:
        cat_code = (sub.get("category_code") or "").upper()
        sub_by_cat_code[(cat_code, sub.get("code", "").upper())] = sub

    services = _index_by_code(client.get("/patient-services", headers=headers).json())
    mapped = 0
    for service_code, (cat_code, sub_code) in DEMO_SERVICE_MAPPINGS.items():
        service = services.get(service_code.upper())
        if not service:
            continue
        category = categories.get(cat_code)
        sub = sub_by_cat_code.get((cat_code, sub_code))
        if not category or not sub:
            continue
        client.patch(
            f"/patient-services/{service['id']}",
            json={"category_id": category["id"], "sub_category_id": sub["id"]},
            headers=headers,
        )
        mapped += 1

    existing_packages = _index_by_code(client.get("/billing-packages", headers=headers).json())
    package_ids: dict[str, str] = {}
    for pkg_def in DEMO_PACKAGES:
        code = pkg_def["code"]
        payload = {
            "code": code,
            "name": pkg_def["name"],
            "package_total": pkg_def["package_total"],
            "description": pkg_def.get("description"),
            "sort_order": pkg_def.get("sort_order", 0),
        }
        pkg = existing_packages.get(code)
        if pkg:
            client.patch(
                f"/billing-packages/{pkg['id']}",
                json={
                    "name": payload["name"],
                    "package_total": payload["package_total"],
                    "description": payload["description"],
                    "sort_order": payload["sort_order"],
                },
                headers=headers,
            )
            package_id = pkg["id"]
        else:
            created = client.post("/billing-packages", json=payload, headers=headers)
            if created.status_code != 201:
                continue
            package_id = created.json()["id"]
        package_ids[code] = package_id

        item_payload = []
        for index, item_def in enumerate(pkg_def["items"]):
            svc = services.get(item_def["service_code"].upper())
            if not svc:
                continue
            item_payload.append(
                {
                    "service_id": svc["id"],
                    "quantity": item_def.get("quantity", 1),
                    "rate_override": item_def.get("rate_override"),
                    "sort_order": index,
                }
            )
        if item_payload:
            client.put(
                f"/billing-packages/{package_id}/items",
                json={"items": item_payload},
                headers=headers,
            )

    lab = categories.get("LAB")
    blood = sub_by_cat_code.get(("LAB", "BLOOD"))
    return {
        "mapped_services": mapped,
        "lab_category_id": lab["id"] if lab else None,
        "blood_sub_category_id": blood["id"] if blood else None,
        "package_ids": package_ids,
        "service_ids": {code: services[code.upper()]["id"] for code in DEMO_SERVICE_MAPPINGS if code.upper() in services},
    }
