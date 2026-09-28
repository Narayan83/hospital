"""Verify all Medical Shop menus resolve to working widgets and API endpoints."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
BACKEND = ROOT / "backend"
sys.path.insert(0, str(DESKTOP))
os.chdir(DESKTOP)

MEDICAL_SHOP_MENUS = [
    "medical_shop",
    "medicine_master",
    "medicine_sale_bill",
    "surgicals_master",
    "disposables_master",
    "consumables_master",
    "implants_master",
    "manufacturer_master",
    "marketing_agency_master",
    "distributors_master",
    "drug_category_master",
    "sales_register",
    "sales_summary",
    "medicine_purchase_bill_109",
    "supplier_master",
    "schedule_h_drug_report",
    "consolidated_stock_report",
    "medicine_group_creation",
    "assign_medicine_to_group",
]


def test_widgets() -> list[str]:
    from PySide6.QtWidgets import QApplication

    from app.api_client.client import ApiClient
    from app.ui.main_window import MainWindow
    from app.ui.widgets.module_placeholder import ModulePlaceholderWidget

    app = QApplication.instance() or QApplication([])
    api = ApiClient()
    window = MainWindow.__new__(MainWindow)
    window.api = api

    failures: list[str] = []
    for menu_code in MEDICAL_SHOP_MENUS:
        widget = window._create_page(menu_code)
        if widget is None:
            failures.append(f"{menu_code}: _create_page returned None")
            continue
        if isinstance(widget, ModulePlaceholderWidget):
            failures.append(f"{menu_code}: still using ModulePlaceholderWidget")
            continue
        print(f"OK widget: {menu_code} -> {type(widget).__name__}")
    api.close()
    return failures


def test_api() -> list[str]:
    import httpx

    base = "http://127.0.0.1:8010/api/v1"
    failures: list[str] = []
    with httpx.Client(base_url=base, timeout=30.0) as client:
        login = client.post("/auth/login", json={"email": "admin@admin.com", "password": "admin123"})
        if login.status_code != 200:
            return [f"login failed: {login.status_code} {login.text}"]
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        checks = [
            ("GET", "/pharmacy/code-masters?master_type=MF", None),
            ("GET", "/pharmacy/items?item_type=MD", None),
            ("GET", "/pharmacy/suppliers", None),
            ("GET", "/pharmacy/reports/stock", None),
            ("GET", "/pharmacy/sale-bills/last-info", None),
            ("GET", "/pharmacy/stock-lookup?code=PCM500", None),
            ("GET", "/pharmacy/items/search?q=para&item_type=MD", None),
        ]
        today = date.today()
        from_day = (today - timedelta(days=30)).isoformat()
        to_day = today.isoformat()
        checks.extend(
            [
                ("GET", f"/pharmacy/reports/sales-register?from_date={from_day}&to_date={to_day}", None),
                ("GET", f"/pharmacy/reports/sales-summary?from_date={from_day}&to_date={to_day}", None),
                ("GET", f"/pharmacy/reports/schedule-h?from_date={from_day}&to_date={to_day}", None),
            ]
        )

        items = client.get("/pharmacy/items?item_type=MD", headers=headers).json()
        if not items:
            failures.append("no sample MD items seeded")
        else:
            sale_payload = {
                "patient_name": "Walk-in Test",
                "is_cash": True,
                "discount_amount": 0,
                "bill_date": to_day,
                "lines": [{"item_id": items[0]["id"], "quantity": 1, "rate": float(items[0].get("sale_rate") or 1)}],
            }
            checks.append(("POST", "/pharmacy/sale-bills", sale_payload))

            purchase_payload = {
                "bill_date": to_day,
                "lines": [{"item_id": items[0]["id"], "quantity": 10, "rate": float(items[0].get("purchase_rate") or 1)}],
            }
            checks.append(("POST", "/pharmacy/purchase-bills", purchase_payload))

        for method, path, payload in checks:
            if method == "GET":
                resp = client.get(path, headers=headers)
            else:
                resp = client.post(path, json=payload, headers=headers)
            if resp.status_code >= 400:
                failures.append(f"{method} {path} -> {resp.status_code}: {resp.text[:200]}")
            else:
                print(f"OK api: {method} {path} -> {resp.status_code}")
    return failures


def main() -> int:
    print("=== Medical Shop widget test ===")
    widget_failures = test_widgets()
    print("\n=== Medical Shop API test ===")
    api_failures = test_api()
    failures = widget_failures + api_failures
    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(f" - {item}")
        return 1
    print("\nAll medical shop menus passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
