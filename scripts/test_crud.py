"""End-to-end CRUD smoke test for core master APIs and patient/doctor flows."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billing_demo_mappings import DEMO_PACKAGES, DEMO_SERVICE_MAPPINGS, apply_demo_mappings

BASE = f"http://127.0.0.1:{os.getenv('BACKEND_PORT', '8010')}/api/v1"
PASS = 0
FAIL = 0


def ok(name: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  PASS  {name}{suffix}")


def fail(name: str, detail: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}: {detail}")


def check(name: str, cond: bool, detail: str = "") -> bool:
    if cond:
        ok(name, detail)
        return True
    fail(name, detail or "assertion failed")
    return False


def cash_payment(client: httpx.Client, headers: dict, amount: str) -> list[dict]:
    modes = client.get("/payment-modes", headers=headers).json()
    cash = next(m for m in modes if m.get("code") == "CASH")
    return [{"payment_mode_id": cash["id"], "amount": amount}]


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE, timeout=30.0)

    # --- Login ---
    print("\n=== AUTH ===")
    r = client.post("/auth/login", json={"email": "admin@admin.com", "password": "admin123"})
    if not check("login", r.status_code == 200, f"status={r.status_code} {r.text[:200]}"):
        return 1
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    login_body = r.json()
    check("login returns menus", isinstance(login_body.get("menus"), list) and len(login_body["menus"]) > 0)
    app_data = login_body.get("app_data") or {}
    check(
        "login returns app_data",
        bool(app_data),
        f"keys={','.join(sorted(app_data.keys())[:8])}..." if app_data else "missing",
    )
    check(
        "app_data patient_no_formats seeded",
        len(app_data.get("patient_no_formats") or []) >= 1,
        f"count={len(app_data.get('patient_no_formats') or [])}",
    )
    selected_formats = [f for f in (app_data.get("patient_no_formats") or []) if f.get("is_selected")]
    check("app_data has one selected patient format", len(selected_formats) == 1, selected_formats[0].get("code", "") if selected_formats else "")
    check(
        "app_data service_categories seeded",
        len(app_data.get("service_categories") or []) >= 1,
        f"count={len(app_data.get('service_categories') or [])}",
    )
    check(
        "app_data billing_packages key",
        "billing_packages" in app_data,
        f"count={len(app_data.get('billing_packages') or [])}",
    )

    r = client.get("/auth/app-data", headers=headers)
    check("auth app-data endpoint", r.status_code == 200 and "doctors" in r.json(), f"status={r.status_code}")

    r = client.get("/patients/next-id-preview", headers=headers)
    check(
        "patient next-id-preview",
        r.status_code == 200 and bool(r.json().get("patient_no")),
        r.json().get("patient_no", "") if r.status_code == 200 else r.text[:120],
    )

    # --- Doctor CRUD ---
    print("\n=== DOCTOR MASTER ===")
    create_doc = {
        "title": "Dr",
        "first_name": f"TestDoc{suffix}",
        "second_name": "Auto",
        "sex": "M",
        "date_of_birth": "1985-06-15",
        "mobile": "9876500001",
        "is_reference_doctor": False,
        "is_pathology_doctor": False,
    }
    r = client.post("/doctors", json=create_doc, headers=headers)
    if not check("doctor create", r.status_code == 201, r.text[:300]):
        doctor_id = None
    else:
        doc = r.json()
        doctor_id = doc["id"]
        check("doctor id generated", bool(doc.get("doctor_code")), doc.get("doctor_code", ""))

    if doctor_id:
        r = client.get(f"/doctors/{doctor_id}", headers=headers)
        check(
            "doctor retrieve",
            r.status_code == 200 and r.json().get("first_name") == create_doc["first_name"],
            r.json().get("doctor_code", ""),
        )

        r = client.patch(
            f"/doctors/{doctor_id}",
            json={"mobile": "9876500099", "qualification": "MBBS"},
            headers=headers,
        )
        check(
            "doctor update",
            r.status_code == 200 and r.json().get("mobile") == "9876500099",
            r.text[:200],
        )

        r = client.get("/doctors", params={"search": create_doc["first_name"]}, headers=headers)
        items = r.json().get("items", []) if r.status_code == 200 else []
        check("doctor list/search", any(i["id"] == doctor_id for i in items), f"found={len(items)}")

        r = client.delete(f"/doctors/{doctor_id}", headers=headers)
        check(
            "doctor delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Patient CRUD ---
    print("\n=== PATIENT MASTER ===")
    create_pat = {
        "first_name": f"TestPat{suffix}",
        "middle_name": "K",
        "last_name": "Smoke",
        "gender": "M",
        "date_of_birth": "1990-03-20",
        "mobile": "9123400001",
        "blood_group": "O+",
    }
    r = client.post("/patients", json=create_pat)
    if not check("patient create", r.status_code == 201, r.text[:300]):
        patient_id = None
    else:
        pat = r.json()
        patient_id = pat["id"]
        check("patient no generated", bool(pat.get("patient_no")), pat.get("patient_no", ""))
        r = client.get("/patients/next-id-preview", headers=headers)
        preview_no = r.json().get("patient_no", "") if r.status_code == 200 else ""
        check(
            "patient no matches active format preview",
            bool(preview_no) and pat.get("patient_no") != preview_no,
            f"created={pat.get('patient_no', '')} next={preview_no}",
        )

    if patient_id:
        r = client.get(f"/patients/{patient_id}")
        check(
            "patient retrieve",
            r.status_code == 200 and r.json().get("first_name") == create_pat["first_name"],
            r.json().get("patient_no", ""),
        )

        r = client.patch(
            f"/patients/{patient_id}",
            json={"mobile": "9123400099", "remarks": "Updated by smoke test"},
        )
        check(
            "patient update",
            r.status_code == 200 and r.json().get("mobile") == "9123400099",
            r.text[:200],
        )

        r = client.get("/patients", params={"search": create_pat["first_name"]})
        items = r.json().get("items", []) if r.status_code == 200 else []
        check("patient list/search", any(i["id"] == patient_id for i in items), f"found={len(items)}")

        tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = client.post(
            f"/patients/{patient_id}/aadhar-scan",
            headers=headers,
            files={"file": ("aadhar.png", tiny_png, "image/png")},
        )
        if check("patient aadhar scan upload", r.status_code == 200, r.text[:200]):
            check(
                "patient aadhar scan path saved",
                bool(r.json().get("aadhar_scan_path")),
                r.json().get("aadhar_scan_path", ""),
            )
            r = client.get(f"/patients/{patient_id}/aadhar-scan", headers=headers)
            check("patient aadhar scan download", r.status_code == 200, f"bytes={len(r.content)}")

        r = client.patch(f"/patients/{patient_id}", json={"is_active": False})
        check(
            "patient delete (deactivate via is_active)",
            r.status_code == 200 and r.json().get("is_active") is False,
            "soft delete via PATCH is_active=false",
        )

    # --- User CRUD ---
    print("\n=== USER ADDITION / MODIFICATION ===")
    r = client.get("/user-types", headers=headers)
    user_types = r.json() if r.status_code == 200 else []
    user_type = next((t for t in user_types if t.get("code") == "user"), user_types[0] if user_types else None)
    if not check("fetch user types", user_type is not None, f"count={len(user_types)}"):
        user_type_id = None
    else:
        user_type_id = user_type["id"]

    test_email = f"testuser.{suffix}@example.com"
    user_id = None
    if user_type_id:
        create_user = {
            "email": test_email,
            "password": "testpass123",
            "full_name": f"Test User {suffix}",
            "phone": "9000001234",
            "user_type_id": user_type_id,
            "is_active": True,
        }
        r = client.post("/users", json=create_user, headers=headers)
        if not check("user create", r.status_code == 201, r.text[:300]):
            pass
        else:
            user = r.json()
            user_id = user["id"]
            check("user id assigned", bool(user_id), user_id)

    if user_id:
        r = client.get("/users", headers=headers)
        users = r.json() if r.status_code == 200 else []
        check("user list/retrieve", any(u["id"] == user_id for u in users), f"total={len(users)}")

        r = client.patch(
            f"/users/{user_id}",
            json={"full_name": f"Updated User {suffix}", "phone": "9000009999"},
            headers=headers,
        )
        check(
            "user update",
            r.status_code == 200 and r.json().get("full_name") == f"Updated User {suffix}",
            r.text[:200],
        )

        r = client.delete(f"/users/{user_id}", headers=headers)
        check(
            "user delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Billing Type CRUD ---
    print("\n=== BILL TYPES CREATION ===")
    test_code = f"T{suffix[:6].upper()}"
    create_bt = {
        "code": test_code,
        "name": f"Test Billing {suffix}",
        "sort_order": 99,
    }
    r = client.post("/billing-types", json=create_bt, headers=headers)
    if not check("billing type create", r.status_code == 201, r.text[:300]):
        billing_type_id = None
    else:
        bt = r.json()
        billing_type_id = bt["id"]
        check("billing type code stored", bt.get("code") == test_code, bt.get("code", ""))

    if billing_type_id:
        r = client.get(f"/billing-types/{billing_type_id}", headers=headers)
        check(
            "billing type retrieve",
            r.status_code == 200 and r.json().get("name") == create_bt["name"],
            r.json().get("code", ""),
        )

        r = client.patch(
            f"/billing-types/{billing_type_id}",
            json={"name": f"Updated Billing {suffix}"},
            headers=headers,
        )
        check(
            "billing type update",
            r.status_code == 200 and r.json().get("name") == f"Updated Billing {suffix}",
            r.text[:200],
        )

        r = client.get("/billing-types", headers=headers)
        items = r.json() if r.status_code == 200 else []
        check("billing type list", any(i["id"] == billing_type_id for i in items), f"total={len(items)}")

        seeded = [i for i in items if i.get("code") in ("OPD", "IPD", "LAB")]
        check("billing type seeds OPD/IPD/LAB", len(seeded) >= 3, f"found={','.join(i['code'] for i in seeded)}")

        r = client.delete(f"/billing-types/{billing_type_id}", headers=headers)
        check(
            "billing type delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Authority CRUD ---
    print("\n=== AUTHORITY CREATION MASTER ===")
    test_auth_code = f"A{suffix[:5].upper()}"
    create_auth = {
        "code": test_auth_code,
        "name": f"Test Authority {suffix}",
        "sort_order": 99,
    }
    r = client.post("/authorities", json=create_auth, headers=headers)
    if not check("authority create", r.status_code == 201, r.text[:300]):
        authority_id = None
    else:
        auth_item = r.json()
        authority_id = auth_item["id"]
        check("authority code stored", auth_item.get("code") == test_auth_code, auth_item.get("code", ""))

    if authority_id:
        r = client.get(f"/authorities/{authority_id}", headers=headers)
        check(
            "authority retrieve",
            r.status_code == 200 and r.json().get("name") == create_auth["name"],
            r.json().get("code", ""),
        )

        r = client.patch(
            f"/authorities/{authority_id}",
            json={"name": f"Updated Authority {suffix}"},
            headers=headers,
        )
        check(
            "authority update",
            r.status_code == 200 and r.json().get("name") == f"Updated Authority {suffix}",
            r.text[:200],
        )

        r = client.get("/authorities", headers=headers)
        items = r.json() if r.status_code == 200 else []
        check("authority list", any(i["id"] == authority_id for i in items), f"total={len(items)}")

        manager = next((i for i in items if i.get("name") == "Manager"), None)
        check(
            "authority seed Manager",
            manager is not None and manager.get("code") == "MANAGER",
            manager.get("code", "") if manager else "not found",
        )

        r = client.delete(f"/authorities/{authority_id}", headers=headers)
        check(
            "authority delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Hospital Section CRUD ---
    print("\n=== HOSPITAL SECTIONS ===")
    section_code = f"HS{suffix[:4].upper()}"
    r = client.post(
        "/hospital-sections",
        json={"code": section_code, "name": f"Test Section {suffix}", "sort_order": 1},
        headers=headers,
    )
    if not check("hospital section create", r.status_code == 201, r.text[:300]):
        section_id = None
    else:
        section = r.json()
        section_id = section["id"]

    if section_id:
        r = client.get(f"/hospital-sections/{section_id}", headers=headers)
        check("hospital section retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(
            f"/hospital-sections/{section_id}",
            json={"name": f"Updated Section {suffix}"},
            headers=headers,
        )
        check("hospital section update", r.status_code == 200, r.text[:200])
        r = client.post(
            "/patients",
            json={
                "first_name": f"SecPat{suffix}",
                "gender": "M",
                "hospital_section_id": section_id,
            },
        )
        if r.status_code == 201:
            sec_pat = r.json()
            check(
                "patient with hospital section",
                sec_pat.get("hospital_section_id") == section_id,
                sec_pat.get("hospital_section_name", ""),
            )
            client.patch(f"/patients/{sec_pat['id']}", json={"is_active": False})
        else:
            check("patient with hospital section", False, r.text[:200])
        r = client.delete(f"/hospital-sections/{section_id}", headers=headers)
        check(
            "hospital section delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Prefix CRUD ---
    print("\n=== PREFIX CREATION ===")
    prefix_code = f"PX{suffix[:4].upper()}"
    r = client.post(
        "/prefixes",
        json={
            "code": prefix_code,
            "name": f"Test Prefix {suffix}",
            "prefix_value": "TX",
            "sort_order": 99,
        },
        headers=headers,
    )
    if not check("prefix create", r.status_code == 201, r.text[:300]):
        prefix_id = None
    else:
        prefix_id = r.json()["id"]

    if prefix_id:
        r = client.get(f"/prefixes/{prefix_id}", headers=headers)
        check("prefix retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(
            f"/prefixes/{prefix_id}",
            json={"prefix_value": "TY"},
            headers=headers,
        )
        check(
            "prefix update",
            r.status_code == 200 and r.json().get("prefix_value") == "TY",
            r.text[:200],
        )
        r = client.get("/prefixes", headers=headers)
        items = r.json() if r.status_code == 200 else []
        seeded = {i.get("code"): i.get("prefix_value") for i in items}
        check(
            "prefix seeds PATIENT/OPD/IPD",
            seeded.get("PATIENT") == "P" and seeded.get("OPD") == "OPD" and seeded.get("IPD") == "IPD",
            f"PATIENT={seeded.get('PATIENT')}, OPD={seeded.get('OPD')}, IPD={seeded.get('IPD')}",
        )
        r = client.delete(f"/prefixes/{prefix_id}", headers=headers)
        check(
            "prefix delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Payment Mode CRUD ---
    print("\n=== PAYMENT MODE CREATION ===")
    pm_code = f"PM{suffix[:4].upper()}"
    r = client.post(
        "/payment-modes",
        json={"code": pm_code, "name": f"Test Mode {suffix}", "is_cash": False, "sort_order": 99},
        headers=headers,
    )
    if not check("payment mode create", r.status_code == 201, r.text[:300]):
        payment_mode_id = None
    else:
        payment_mode_id = r.json()["id"]

    if payment_mode_id:
        r = client.get(f"/payment-modes/{payment_mode_id}", headers=headers)
        check("payment mode retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(
            f"/payment-modes/{payment_mode_id}",
            json={"name": f"Updated Mode {suffix}", "is_cash": True},
            headers=headers,
        )
        check(
            "payment mode update",
            r.status_code == 200 and r.json().get("is_cash") is True,
            r.text[:200],
        )
        r = client.get("/payment-modes", headers=headers)
        items = r.json() if r.status_code == 200 else []
        by_code = {i.get("code"): i for i in items}
        check(
            "payment mode seeds CASH/CREDIT/ONLINE/SWIPE",
            all(code in by_code for code in ("CASH", "CREDIT", "ONLINE", "SWIPE")),
            ",".join(sorted(by_code.keys())),
        )
        check(
            "payment mode cash flag on CASH only",
            by_code.get("CASH", {}).get("is_cash") is True
            and not by_code.get("CREDIT", {}).get("is_cash")
            and not by_code.get("ONLINE", {}).get("is_cash")
            and not by_code.get("SWIPE", {}).get("is_cash"),
            f"CASH={by_code.get('CASH', {}).get('is_cash')}",
        )
        r = client.delete(f"/payment-modes/{payment_mode_id}", headers=headers)
        check(
            "payment mode delete (deactivate)",
            r.status_code == 200 and r.json().get("is_active") is False,
            r.text[:200],
        )

    # --- Department CRUD ---
    print("\n=== DEPARTMENT MASTER ===")
    dept_code = f"D{suffix[:5].upper()}"
    r = client.post(
        "/departments",
        json={"code": dept_code, "name": f"Test Dept {suffix}", "sort_order": 99},
        headers=headers,
    )
    dept_id = r.json()["id"] if check("department create", r.status_code == 201, r.text[:200]) else None
    if dept_id:
        r = client.get(f"/departments/{dept_id}", headers=headers)
        check("department retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(f"/departments/{dept_id}", json={"name": f"Updated Dept {suffix}"}, headers=headers)
        check("department update", r.status_code == 200, r.text[:200])
        r = client.get("/departments", headers=headers)
        check("department list GYN/CAR seeds", all(c in {i.get("code") for i in r.json()} for c in ("GYN", "CAR")))
        r = client.delete(f"/departments/{dept_id}", headers=headers)
        check("department delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Procedure Type CRUD ---
    print("\n=== PROCEDURE TYPE MASTER ===")
    proc_code = f"PR{suffix[:4].upper()}"
    r = client.post(
        "/procedure-types",
        json={"code": proc_code, "name": f"Test Proc {suffix}", "sort_order": 99},
        headers=headers,
    )
    proc_id = r.json()["id"] if check("procedure type create", r.status_code == 201, r.text[:200]) else None
    if proc_id:
        r = client.get(f"/procedure-types/{proc_id}", headers=headers)
        check("procedure type retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(f"/procedure-types/{proc_id}", json={"name": f"Updated Proc {suffix}"}, headers=headers)
        check("procedure type update", r.status_code == 200, r.text[:200])
        r = client.get("/procedure-types", headers=headers)
        codes = {i.get("code") for i in r.json()}
        check(
            "procedure type seeds SURGERY/CONSULTATION/ENDOSCOPY",
            {"SURGERY", "CONSULTATION", "ENDOSCOPY"}.issubset(codes),
            ",".join(sorted(codes & {"SURGERY", "CONSULTATION", "ENDOSCOPY"})),
        )
        r = client.delete(f"/procedure-types/{proc_id}", headers=headers)
        check("procedure type delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Billing Structure Mapping ---
    print("\n=== BILLING STRUCTURE MAPPING ===")
    r = client.get("/billing-types", headers=headers)
    bt_opd = next((i for i in r.json() if i.get("code") == "OPD"), None)
    r = client.get("/departments", headers=headers)
    dept_gyn = next((i for i in r.json() if i.get("code") == "GYN"), None)
    r = client.get("/procedure-types", headers=headers)
    proc_surg = next((i for i in r.json() if i.get("code") == "SURGERY"), None)
    mapping_id = None
    if bt_opd and dept_gyn and proc_surg:
        r = client.post(
            "/billing-structure",
            json={
                "billing_type_id": bt_opd["id"],
                "department_id": dept_gyn["id"],
                "procedure_type_id": proc_surg["id"],
            },
            headers=headers,
        )
        if r.status_code == 201:
            mapping_id = r.json()["id"]
            check("billing structure create", True, f"{r.json().get('billing_type_name')} / {r.json().get('department_name')}")
        elif r.status_code == 400 and "already exists" in r.text:
            r = client.get("/billing-structure", headers=headers)
            existing = next(
                (
                    m for m in r.json()
                    if m.get("billing_type_code") == "OPD"
                    and m.get("department_code") == "GYN"
                    and m.get("procedure_type_code") == "SURGERY"
                ),
                None,
            )
            mapping_id = existing.get("id") if existing else None
            check("billing structure create (seed exists)", mapping_id is not None, "OPD/GYN/SURGERY")
        else:
            check("billing structure create", False, r.text[:200])

        r = client.get("/billing-structure/tree", headers=headers)
        tree_ok = False
        if r.status_code == 200:
            for node in r.json():
                if node.get("billing_type", {}).get("code") != "OPD":
                    continue
                for dept_node in node.get("departments", []):
                    if dept_node.get("department", {}).get("code") != "GYN":
                        continue
                    proc_codes = {p.get("code") for p in dept_node.get("procedure_types", [])}
                    tree_ok = "SURGERY" in proc_codes
        check("billing structure tree OPD->GYN->SURGERY", tree_ok, "hierarchy verified")

        if mapping_id and proc_id:
            r = client.delete(f"/billing-structure/{mapping_id}", headers=headers)
            if r.status_code == 200:
                check("billing structure delete", r.json().get("is_active") is False)
                client.post(
                    "/billing-structure",
                    json={
                        "billing_type_id": bt_opd["id"],
                        "department_id": dept_gyn["id"],
                        "procedure_type_id": proc_surg["id"],
                    },
                    headers=headers,
                )
            else:
                check("billing structure delete", False, r.text[:200])
    else:
        check("billing structure prerequisites", False, "missing OPD/GYN/SURGERY masters")

    # --- Ward CRUD ---
    print("\n=== WARD MASTER ===")
    ward_code = f"W{suffix[:5].upper()}"
    r = client.post(
        "/wards",
        json={"code": ward_code, "name": f"Test Ward {suffix}", "sort_order": 99},
        headers=headers,
    )
    ward_id = r.json()["id"] if check("ward create", r.status_code == 201, r.text[:200]) else None
    if ward_id:
        r = client.get(f"/wards/{ward_id}", headers=headers)
        check("ward retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(f"/wards/{ward_id}", json={"name": f"Updated Ward {suffix}"}, headers=headers)
        check("ward update", r.status_code == 200, r.text[:200])
        r = client.get("/wards", headers=headers)
        check("ward list", any(i["id"] == ward_id for i in r.json()), f"total={len(r.json())}")
        r = client.delete(f"/wards/{ward_id}", headers=headers)
        check("ward delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Patient ID Format CRUD ---
    print("\n=== PATIENT ID FORMAT ===")
    fmt_code = f"TF{suffix[:4].upper()}"
    r = client.post(
        "/patient-no-formats",
        json={
            "code": fmt_code,
            "name": f"Test Format {suffix}",
            "pattern": "T{SEQ:4}",
            "sample_output": "T0001",
            "seq_pad_width": 4,
            "sort_order": 99,
        },
        headers=headers,
    )
    format_id = r.json()["id"] if check("patient format create", r.status_code == 201, r.text[:200]) else None
    if format_id:
        r = client.get(f"/patient-no-formats/{format_id}", headers=headers)
        check("patient format retrieve", r.status_code == 200, r.json().get("pattern", ""))
        r = client.patch(
            f"/patient-no-formats/{format_id}",
            json={"name": f"Updated Format {suffix}", "is_selected": True},
            headers=headers,
        )
        check(
            "patient format update/select",
            r.status_code == 200 and r.json().get("is_selected") is True,
            r.json().get("code", ""),
        )
        r = client.get("/patient-no-formats", headers=headers)
        selected = [f for f in r.json() if f.get("is_selected")]
        check("patient format single selected", len(selected) == 1 and selected[0]["id"] == format_id)
        seed = next((f for f in r.json() if f.get("code") == "SECTION_DAILY"), None)
        if seed:
            client.patch(
                f"/patient-no-formats/{seed['id']}",
                json={"is_selected": True},
                headers=headers,
            )
        r = client.delete(f"/patient-no-formats/{format_id}", headers=headers)
        check("patient format delete", r.status_code == 200 and r.json().get("is_active") is False)
        seeded = next((f for f in client.get("/patient-no-formats", headers=headers).json() if f.get("is_selected")), None)
        check("patient format seed re-selected", seeded is not None, seeded.get("code", "") if seeded else "")

    # --- Service Category CRUD ---
    print("\n=== SERVICE CATEGORY MASTER ===")
    cat_code = f"TC{suffix[:4].upper()}"
    r = client.post(
        "/service-categories",
        json={"code": cat_code, "name": f"Test Category {suffix}", "sort_order": 99},
        headers=headers,
    )
    category_id = r.json()["id"] if check("service category create", r.status_code == 201, r.text[:200]) else None
    if category_id:
        r = client.get(f"/service-categories/{category_id}", headers=headers)
        check("service category retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(
            f"/service-categories/{category_id}",
            json={"name": f"Updated Category {suffix}"},
            headers=headers,
        )
        check("service category update", r.status_code == 200, r.text[:200])
        r = client.get("/service-categories", headers=headers)
        check(
            "service category list",
            any(i["id"] == category_id for i in r.json()),
            f"total={len(r.json())}",
        )
        seeded = next((c for c in r.json() if c.get("code") == "GYN"), None)
        check("service category seed GYN", seeded is not None, seeded.get("name", "") if seeded else "")

    # --- Billing Package CRUD ---
    print("\n=== BILLING PACKAGE MASTER ===")
    pkg_code = f"PK{suffix[:4].upper()}"
    r = client.post(
        "/billing-packages",
        json={
            "code": pkg_code,
            "name": f"Test Package {suffix}",
            "package_total": "50000.00",
            "description": "Test delivery package",
            "sort_order": 99,
        },
        headers=headers,
    )
    package_id = r.json()["id"] if check("billing package create", r.status_code == 201, r.text[:200]) else None
    if package_id:
        r = client.get(f"/billing-packages/{package_id}", headers=headers)
        check(
            "billing package retrieve",
            r.status_code == 200 and r.json().get("code") == pkg_code,
            r.json().get("name", "") if r.status_code == 200 else r.text[:200],
        )
        r = client.patch(
            f"/billing-packages/{package_id}",
            json={"name": f"Updated Package {suffix}", "package_total": "55000.00"},
            headers=headers,
        )
        check("billing package update", r.status_code == 200, r.text[:200])

    # --- Package service mapping (needs a service) ---
    print("\n=== PACKAGE SERVICE MAPPING ===")
    svc_code_pkg = f"PS{suffix[:4].upper()}"
    r = client.post(
        "/patient-services",
        json={
            "code": svc_code_pkg,
            "name": f"Package Line {suffix}",
            "service_charge": "1000.00",
            "rate": "1000.00",
            "category_id": category_id,
        },
        headers=headers,
    )
    pkg_service_id = r.json()["id"] if check("package mapping service create", r.status_code == 201, r.text[:200]) else None
    if package_id and pkg_service_id:
        r = client.put(
            f"/billing-packages/{package_id}/items",
            json={
                "items": [
                    {
                        "service_id": pkg_service_id,
                        "quantity": 2,
                        "rate_override": "900.00",
                        "sort_order": 1,
                    }
                ]
            },
            headers=headers,
        )
        mapped = r.json() if r.status_code == 200 else {}
        items = mapped.get("items") or []
        check(
            "billing package replace items",
            r.status_code == 200 and len(items) == 1,
            f"items={len(items)}",
        )
        check(
            "package item service linked",
            items and items[0].get("service_code") == svc_code_pkg,
            items[0].get("service_name", "") if items else "",
        )
        r = client.get(f"/billing-packages/{package_id}", headers=headers)
        check(
            "billing package detail item_count",
            r.status_code == 200 and r.json().get("item_count", len(r.json().get("items", []))) >= 1,
            f"count={len(r.json().get('items', []))}" if r.status_code == 200 else r.text[:200],
        )
        r = client.get("/billing-packages", headers=headers)
        check(
            "billing package list",
            any(i["id"] == package_id for i in r.json()),
            f"total={len(r.json())}",
        )
        if items:
            item_id = items[0].get("id")
            r = client.delete(f"/billing-packages/{package_id}/items/{item_id}", headers=headers)
            check(
                "billing package remove item",
                r.status_code == 200 and len(r.json().get("items", [])) == 0,
                f"remaining={len(r.json().get('items', []))}" if r.status_code == 200 else r.text[:200],
            )
        r = client.delete(f"/billing-packages/{package_id}", headers=headers)
        check("billing package delete", r.status_code == 200 and r.json().get("is_active") is False)
    if pkg_service_id:
        client.delete(f"/patient-services/{pkg_service_id}", headers=headers)
    if category_id:
        r = client.delete(f"/service-categories/{category_id}", headers=headers)
        check("service category delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Service Sub Category CRUD ---
    print("\n=== SERVICE SUB CATEGORY MASTER ===")
    gyn_cat = next((c for c in client.get("/service-categories", headers=headers).json() if c.get("code") == "GYN"), None)
    sub_code = f"SC{suffix[:4].upper()}"
    sub_id = None
    if gyn_cat:
        r = client.post(
            "/service-sub-categories",
            json={
                "category_id": gyn_cat["id"],
                "code": sub_code,
                "name": f"Test SubCat {suffix}",
                "sort_order": 99,
            },
            headers=headers,
        )
        sub_id = r.json()["id"] if check("service sub category create", r.status_code == 201, r.text[:200]) else None
        if sub_id:
            r = client.get(f"/service-sub-categories/{sub_id}", headers=headers)
            check("service sub category retrieve", r.status_code == 200, r.json().get("code", ""))
            r = client.patch(
                f"/service-sub-categories/{sub_id}",
                json={"name": f"Updated SubCat {suffix}"},
                headers=headers,
            )
            check("service sub category update", r.status_code == 200, r.text[:200])
            r = client.get("/service-sub-categories", params={"category_id": gyn_cat["id"]}, headers=headers)
            check(
                "service sub category list by category",
                any(i["id"] == sub_id for i in r.json()),
                f"total={len(r.json())}",
            )
            seeded = next((s for s in r.json() if s.get("code") == "CONSULT"), None)
            check("service sub category seed CONSULT", seeded is not None, seeded.get("name", "") if seeded else "")
    else:
        check("service sub category prerequisites", False, "GYN category missing")

    # --- OPD Bill ---
    print("\n=== OPD BILL ===")
    bill_patient_id = None
    r = client.post(
        "/patients",
        json={"first_name": f"BillPat{suffix[:6]}", "gender": "M"},
        headers=headers,
    )
    if r.status_code == 201:
        bill_patient_id = r.json()["id"]
    bill_service_id = None
    if gyn_cat and sub_id:
        r = client.post(
            "/patient-services",
            json={
                "code": f"BL{suffix[:4].upper()}",
                "name": f"Bill Service {suffix}",
                "service_charge": "500.00",
                "rate": "500.00",
                "category_id": gyn_cat["id"],
                "sub_category_id": sub_id,
            },
            headers=headers,
        )
        bill_service_id = r.json()["id"] if r.status_code == 201 else None

    if bill_patient_id and bill_service_id:
        r = client.get(
            "/opd-bills/catalog/services",
            params={"category_id": gyn_cat["id"], "sub_category_id": sub_id},
            headers=headers,
        )
        catalog = r.json() if r.status_code == 200 else []
        check(
            "billing catalog filter category+subcategory",
            r.status_code == 200 and any(i["id"] == bill_service_id for i in catalog),
            f"found={len(catalog)}",
        )
        r = client.post(
            "/opd-bills",
            json={
                "patient_id": bill_patient_id,
                "is_cash": True,
                "admin_charges": "50.00",
                "lines": [{"service_id": bill_service_id, "quantity": 2, "rate": "500.00"}],
                "payments": cash_payment(client, headers, "1050.00"),
            },
            headers=headers,
        )
        bill_id = None
        if check("opd bill create", r.status_code == 201, r.text[:200]):
            body = r.json()
            bill_id = body.get("id")
            bill_no = body.get("bill_no", "")
            check("opd bill number generated", bool(bill_no), bill_no)
            check(
                "opd bill yearly format",
                bill_no.startswith("OPD") and len(bill_no) >= 12 and bill_no[3:7].isdigit(),
                bill_no,
            )
            check(
                "opd bill net amount",
                str(body.get("net_amount")) in ("1050.00", "1050", "1050.0"),
                str(body.get("net_amount")),
            )
            check("opd bill lines saved", len(body.get("lines") or []) == 1, f"lines={len(body.get('lines') or [])}")
        if bill_id:
            r = client.get(f"/opd-bills/{bill_id}", headers=headers)
            check("opd bill retrieve", r.status_code == 200, r.json().get("bill_no", ""))
            if bill_no:
                r = client.get(f"/opd-bills/by-no/{bill_no}", headers=headers)
                check("opd bill retrieve by no", r.status_code == 200, bill_no)

        print("\n=== IPD ADMISSION ===")
        ward_id = None
        r = client.get("/wards", headers=headers)
        wards = r.json() if r.status_code == 200 else []
        if wards:
            ward_id = wards[0]["id"]
        else:
            r = client.post(
                "/wards",
                json={"code": f"WD{suffix[:4].upper()}", "name": f"Test Ward {suffix}"},
                headers=headers,
            )
            ward_id = r.json()["id"] if r.status_code == 201 else None
        r = client.post(
            "/ipd-admissions",
            json={
                "patient_id": bill_patient_id,
                "ward_id": ward_id,
                "bed_no": "B1",
                "advance_amount": "1000.00",
                "diagnosis": "Test admission",
            },
            headers=headers,
        )
        admission_id = None
        admission_no = ""
        if check("ipd admission create", r.status_code == 201, r.text[:200]):
            body = r.json()
            admission_id = body.get("id")
            admission_no = body.get("admission_no", "")
            check("ipd admission number generated", bool(admission_no), admission_no)
            check("ipd admission status admitted", body.get("status") == "admitted", body.get("status", ""))
        if admission_id:
            r = client.get(f"/ipd-admissions/{admission_id}", headers=headers)
            check("ipd admission retrieve", r.status_code == 200, r.json().get("admission_no", ""))
            if admission_no:
                r = client.get(f"/ipd-admissions/by-no/{admission_no}", headers=headers)
                check("ipd admission retrieve by no", r.status_code == 200, admission_no)
        r = client.get("/ipd-admissions", params={"status": "admitted"}, headers=headers)
        check(
            "ipd admission list admitted",
            r.status_code == 200 and any(a.get("id") == admission_id for a in r.json()),
            f"count={len(r.json()) if r.status_code == 200 else 0}",
        )

        print("\n=== IPD DISCHARGE ===")
        discharge_bill_id = None
        discharge_bill_no = ""
        if admission_id and bill_service_id:
            r = client.post(
                "/ipd-discharge",
                json={
                    "patient_id": bill_patient_id,
                    "admission_id": admission_id,
                    "discharge_date": date.today().isoformat(),
                    "adjust_advance": "500.00",
                    "lines": [{"service_id": bill_service_id, "quantity": 2, "rate": "500.00"}],
                    "payments": cash_payment(client, headers, "500.00"),
                },
                headers=headers,
            )
            if check("ipd discharge create", r.status_code == 201, r.text[:200]):
                body = r.json()
                discharge_bill_id = body.get("id")
                discharge_bill_no = body.get("bill_no", "")
                check("ipd bill number generated", bool(discharge_bill_no), discharge_bill_no)
                check(
                    "ipd bill yearly series prefix",
                    discharge_bill_no.startswith("IPDB") and len(discharge_bill_no) >= 12,
                    discharge_bill_no,
                )
                check("ipd discharge stay days", body.get("stay_days", 0) >= 1, str(body.get("stay_days")))
                check(
                    "ipd discharge net amount",
                    str(body.get("net_amount")) in ("500.00", "500", "500.0"),
                    str(body.get("net_amount")),
                )
                check(
                    "ipd discharge lines saved",
                    len(body.get("lines") or []) == 1,
                    f"lines={len(body.get('lines') or [])}",
                )
                check("ipd admission status discharged", body.get("status") == "discharged", body.get("status", ""))
            if discharge_bill_id:
                r = client.get(f"/ipd-discharge/{discharge_bill_id}", headers=headers)
                check("ipd discharge retrieve", r.status_code == 200, r.json().get("bill_no", ""))
            if discharge_bill_no:
                r = client.get(f"/ipd-discharge/by-no/{discharge_bill_no}", headers=headers)
                check("ipd discharge retrieve by no", r.status_code == 200, discharge_bill_no)
            if admission_id:
                r = client.get(f"/ipd-admissions/{admission_id}", headers=headers)
                check(
                    "ipd admission marked discharged",
                    r.status_code == 200 and r.json().get("status") == "discharged",
                    r.json().get("status", "") if r.status_code == 200 else r.text[:100],
                )

        client.patch(f"/patients/{bill_patient_id}", json={"is_active": False}, headers=headers)
        client.delete(f"/patient-services/{bill_service_id}", headers=headers)
    else:
        check("opd bill prerequisites", False, "patient or service missing")

    if sub_id:
        r = client.delete(f"/service-sub-categories/{sub_id}", headers=headers)
        check("service sub category delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Patient Service CRUD ---
    print("\n=== PATIENT SERVICE MASTER ===")
    svc_code = f"SV{suffix[:4].upper()}"
    r = client.post(
        "/patient-services",
        json={
            "code": svc_code,
            "name": f"Test Service {suffix}",
            "service_charge": "100.00",
            "rate": "150.00",
            "discount_apply": True,
            "is_renewal": True,
            "renewal_days": 30,
        },
        headers=headers,
    )
    service_id = r.json()["id"] if check("patient service create", r.status_code == 201, r.text[:200]) else None
    if service_id:
        r = client.get(f"/patient-services/{service_id}", headers=headers)
        check("patient service retrieve", r.status_code == 200, r.json().get("code", ""))
        r = client.patch(
            f"/patient-services/{service_id}",
            json={"name": f"Updated Service {suffix}", "rate": "175.00"},
            headers=headers,
        )
        check(
            "patient service update",
            r.status_code == 200 and str(r.json().get("rate")) in ("175.00", "175", "175.0"),
            r.text[:200],
        )
        r = client.get("/patient-services", headers=headers)
        check("patient service list", any(i["id"] == service_id for i in r.json()), f"total={len(r.json())}")
        r = client.delete(f"/patient-services/{service_id}", headers=headers)
        check("patient service delete", r.status_code == 200 and r.json().get("is_active") is False)

    # --- Billing demo mappings (legacy services + packages for QA) ---
    print("\n=== BILLING DEMO MAPPINGS ===")
    demo = apply_demo_mappings(client, headers)
    check(
        "demo service mappings applied",
        demo["mapped_services"] >= 5,
        f"mapped={demo['mapped_services']}/{len(DEMO_SERVICE_MAPPINGS)}",
    )
    check(
        "demo LAB category available",
        bool(demo.get("lab_category_id")),
        demo.get("lab_category_id", ""),
    )
    check(
        "demo BLOOD sub-category available",
        bool(demo.get("blood_sub_category_id")),
        demo.get("blood_sub_category_id", ""),
    )

    d1 = demo.get("service_ids", {}).get("D1")
    if d1 and demo.get("lab_category_id") and demo.get("blood_sub_category_id"):
        r = client.get(
            "/opd-bills/catalog/services",
            params={
                "category_id": demo["lab_category_id"],
                "sub_category_id": demo["blood_sub_category_id"],
            },
            headers=headers,
        )
        catalog = r.json() if r.status_code == 200 else []
        check(
            "demo catalog filter LAB+BLOOD includes D1",
            any(i.get("id") == d1 for i in catalog),
            f"catalog_size={len(catalog)}",
        )
        r = client.get(f"/patient-services/{d1}", headers=headers)
        body = r.json() if r.status_code == 200 else {}
        check(
            "demo D1 has LAB+BLOOD assigned",
            body.get("category_name") == "Laboratory" and body.get("sub_category_name") == "Blood Tests",
            f"{body.get('category_name')}/{body.get('sub_category_name')}",
        )
    else:
        check("demo catalog prerequisites", False, "D1 or LAB/BLOOD ids missing")

    basic_pkg_id = demo.get("package_ids", {}).get("DEMO_BASICLAB")
    if basic_pkg_id:
        r = client.get(f"/billing-packages/{basic_pkg_id}", headers=headers)
        pkg = r.json() if r.status_code == 200 else {}
        items = pkg.get("items") or []
        item_codes = {i.get("service_code") for i in items}
        check(
            "demo BASICLAB package has 3 services",
            len(items) == 3,
            f"items={len(items)}",
        )
        check(
            "demo BASICLAB includes D1,D2,D3",
            {"D1", "D2", "D3"}.issubset(item_codes),
            ",".join(sorted(item_codes)),
        )
        check(
            "demo BASICLAB package total",
            str(pkg.get("package_total")) in ("220.00", "220", "220.0"),
            str(pkg.get("package_total")),
        )
    else:
        check("demo BASICLAB package", False, "package not created")

    comp_pkg_id = demo.get("package_ids", {}).get("DEMO_COMPBLOOD")
    if comp_pkg_id:
        r = client.get(f"/billing-packages/{comp_pkg_id}", headers=headers)
        pkg = r.json() if r.status_code == 200 else {}
        check(
            "demo COMPBLOOD package has 4 services",
            len(pkg.get("items") or []) == 4,
            f"items={len(pkg.get('items') or [])}",
        )
    else:
        check("demo COMPBLOOD package", False, "package not created")

    if basic_pkg_id and d1:
        r = client.post(
            "/patients",
            json={"first_name": f"DemoBill{suffix[:4]}", "gender": "F"},
            headers=headers,
        )
        demo_patient_id = r.json().get("id") if r.status_code == 201 else None
        if demo_patient_id:
            lines = []
            pr = client.get(f"/billing-packages/{basic_pkg_id}", headers=headers)
            for item in (pr.json().get("items") if pr.status_code == 200 else []):
                rate = item.get("rate_override") or item.get("service_rate") or 0
                lines.append(
                    {
                        "service_id": item.get("service_id"),
                        "quantity": item.get("quantity", 1),
                        "rate": str(rate),
                        "line_source": "package",
                        "package_id": basic_pkg_id,
                    }
                )
            demo_net = sum(
                float(item.get("rate_override") or item.get("service_rate") or 0)
                * int(item.get("quantity", 1))
                for item in (pr.json().get("items") if pr.status_code == 200 else [])
            )
            r = client.post(
                "/opd-bills",
                json={
                    "patient_id": demo_patient_id,
                    "is_cash": True,
                    "lines": lines,
                    "payments": cash_payment(client, headers, f"{demo_net:.2f}"),
                },
                headers=headers,
            )
            if check("demo opd bill from BASICLAB package", r.status_code == 201, r.text[:200]):
                bill = r.json()
                check(
                    "demo package bill line count",
                    len(bill.get("lines") or []) == 3,
                    f"lines={len(bill.get('lines') or [])}",
                )
                gross = sum(float(ln.get("amount", 0)) for ln in bill.get("lines") or [])
                check(
                    "demo package bill gross ~220",
                    200 <= gross <= 240,
                    f"gross={gross}",
                )
            client.patch(f"/patients/{demo_patient_id}", json={"is_active": False}, headers=headers)

    check(
        "demo packages persist for manual QA",
        "DEMO_BASICLAB" in demo.get("package_ids", {}),
        "DEMO_BASICLAB",
    )

    # --- Summary ---
    print(f"\n=== RESULT: {PASS} passed, {FAIL} failed ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to backend at {BASE} — start with .\\scripts\\dev.ps1")
        sys.exit(1)
