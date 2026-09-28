"""End-to-end API test for accounting module features."""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal

import httpx

BASE = "http://127.0.0.1:8010/api/v1"
PASS = 0
FAIL = 0


def ok(name: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))


def bad(name: str, detail: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name} — {detail}")


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=30.0)

    print("\n=== 1) Login ===")
    r = client.post("/auth/login", json={"email": "admin@admin.com", "password": "admin123"})
    if r.status_code != 200:
        # try username field variants
        r = client.post("/auth/login", data={"username": "admin@admin.com", "password": "admin123"})
    if r.status_code != 200:
        bad("login", f"{r.status_code} {r.text[:300]}")
        return 1
    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        bad("login", f"no token in {r.json()}")
        return 1
    client.headers["Authorization"] = f"Bearer {token}"
    ok("login")

    print("\n=== 2) Ledger Master (type / flags / opening) ===")
    r = client.get("/ledgers")
    if r.status_code != 200:
        bad("list_ledgers", f"{r.status_code} {r.text[:200]}")
        return 1
    ledgers = r.json()
    ok("list_ledgers", f"{len(ledgers)} ledgers")
    sample = next((x for x in ledgers if x.get("code") == "CASH"), ledgers[0] if ledgers else None)
    if not sample:
        bad("seeded_cash", "no ledgers")
        return 1
    for field in ("ledger_type", "opening_balance", "is_cash", "is_bank", "is_patient_deposit"):
        if field not in sample:
            bad("ledger_fields", f"missing {field} in {list(sample.keys())}")
            break
    else:
        ok("ledger_fields", f"CASH type={sample.get('ledger_type')} is_cash={sample.get('is_cash')}")

    cash = next((x for x in ledgers if x.get("is_cash")), None)
    bank = next((x for x in ledgers if x.get("is_bank")), None)
    deposit = next((x for x in ledgers if x.get("is_patient_deposit") or x.get("code") == "PAT-DEPOSIT"), None)
    if cash:
        ok("cash_flag", cash.get("code"))
    else:
        bad("cash_flag", "no is_cash ledger")
    if bank:
        ok("bank_flag", bank.get("code"))
    else:
        bad("bank_flag", "no is_bank ledger")
    if deposit:
        ok("deposit_flag", deposit.get("code"))
    else:
        bad("deposit_flag", "no patient deposit ledger")

    # create test ledger
    code = f"TST{date.today().strftime('%m%d%H%M')}"
    r = client.post(
        "/ledgers",
        json={
            "code": code,
            "name": "Test Expense Ledger",
            "ledger_type": "EXPENSE",
            "opening_balance": "100.50",
            "is_cash": False,
            "is_bank": False,
            "is_patient_deposit": False,
        },
    )
    if r.status_code in (200, 201):
        created = r.json()
        ok("create_ledger", f"{created.get('code')} type={created.get('ledger_type')}")
        lid = created["id"]
        r2 = client.patch(
            f"/ledgers/{lid}",
            json={"name": "Test Expense Ledger Updated", "opening_balance": "200.00"},
        )
        if r2.status_code == 200 and float(r2.json().get("opening_balance", 0)) == 200.0:
            ok("update_ledger", "opening_balance=200")
        else:
            bad("update_ledger", f"{r2.status_code} {r2.text[:200]}")
        # both cash+bank should fail
        r3 = client.patch(f"/ledgers/{lid}", json={"is_cash": True, "is_bank": True})
        if r3.status_code >= 400:
            ok("reject_cash_and_bank", str(r3.status_code))
        else:
            bad("reject_cash_and_bank", "accepted invalid flags")
    else:
        bad("create_ledger", f"{r.status_code} {r.text[:300]}")

    print("\n=== 3) Resolve patient + payment mode ===")
    r = client.get("/patients", params={"page": 1, "page_size": 5})
    if r.status_code != 200:
        # try search
        r = client.get("/patients/search", params={"page": 1, "page_size": 5})
    patients = []
    if r.status_code == 200:
        body = r.json()
        patients = body.get("items") or body if isinstance(body, list) else body.get("items", [])
    if not patients:
        # create a patient
        r = client.post(
            "/patients",
            json={
                "first_name": "Acct",
                "last_name": "Test",
                "gender": "M",
                "mobile": "9999990001",
            },
        )
        if r.status_code in (200, 201):
            patients = [r.json()]
            ok("create_patient", patients[0].get("patient_no"))
        else:
            bad("create_patient", f"{r.status_code} {r.text[:300]}")
            return 1
    else:
        ok("find_patient", patients[0].get("patient_no"))
    patient = patients[0]
    patient_id = patient["id"]

    r = client.get("/payment-modes")
    if r.status_code != 200:
        bad("list_payment_modes", f"{r.status_code} {r.text[:200]}")
        return 1
    modes = r.json()
    cash_mode = next((m for m in modes if m.get("is_cash")), modes[0] if modes else None)
    if not cash_mode:
        bad("payment_mode", "none configured")
        return 1
    if not cash_mode.get("ledger_id"):
        bad("payment_mode_ledger", f"{cash_mode.get('name')} has no ledger_id")
    else:
        ok("payment_mode", f"{cash_mode.get('code')} ledger={cash_mode.get('ledger_id')[:8]}...")

    print("\n=== 4) Advance Collection ===")
    r = client.get("/cashbook/patient-deposit", params={"patient_id": patient_id})
    if r.status_code != 200:
        bad("deposit_balance_before", f"{r.status_code} {r.text[:200]}")
        bal_before = Decimal("0")
    else:
        bal_before = Decimal(str(r.json().get("balance", 0)))
        ok("deposit_balance_before", str(bal_before))

    r = client.post(
        "/cashbook/advance",
        json={
            "patient_id": patient_id,
            "voucher_date": date.today().isoformat(),
            "payment_mode_id": cash_mode["id"],
            "amount": "500.00",
            "narration": "E2E advance test",
        },
    )
    if r.status_code in (200, 201):
        adv = r.json()
        ok("collect_advance", adv.get("voucher_no"))
    else:
        bad("collect_advance", f"{r.status_code} {r.text[:400]}")
        adv = None

    r = client.get("/cashbook/patient-deposit", params={"patient_id": patient_id})
    if r.status_code == 200:
        bal_after = Decimal(str(r.json().get("balance", 0)))
        if adv and bal_after == bal_before + Decimal("500"):
            ok("deposit_increased", str(bal_after))
        elif adv:
            bad("deposit_increased", f"before={bal_before} after={bal_after}")
        else:
            ok("deposit_balance_after", str(bal_after))
    else:
        bad("deposit_balance_after", f"{r.status_code} {r.text[:200]}")

    print("\n=== 5) Payment / Adjustment Voucher ===")
    if not deposit or not cash:
        bad("payment_voucher_prereq", "missing deposit/cash ledger")
    else:
        r = client.post(
            "/cashbook/payment",
            json={
                "voucher_date": date.today().isoformat(),
                "ledger_id": deposit["id"],
                "counter_ledger_id": cash["id"],
                "patient_id": patient_id,
                "amount": "50.00",
                "entry_type": "receipt",
                "narration": "E2E payment voucher receipt to deposit",
            },
        )
        if r.status_code in (200, 201):
            ok("payment_voucher_receipt", r.json().get("voucher_no"))
        else:
            bad("payment_voucher_receipt", f"{r.status_code} {r.text[:400]}")

        r = client.get("/cashbook/patient-deposit", params={"patient_id": patient_id})
        bal_mid = Decimal(str(r.json().get("balance", 0))) if r.status_code == 200 else Decimal("0")

        r = client.post(
            "/cashbook/payment",
            json={
                "voucher_date": date.today().isoformat(),
                "ledger_id": deposit["id"],
                "counter_ledger_id": cash["id"],
                "patient_id": patient_id,
                "amount": "25.00",
                "entry_type": "payment",
                "narration": "E2E payment voucher reduce deposit",
            },
        )
        if r.status_code in (200, 201):
            ok("payment_voucher_payment", r.json().get("voucher_no"))
            r2 = client.get("/cashbook/patient-deposit", params={"patient_id": patient_id})
            bal_pay = Decimal(str(r2.json().get("balance", 0)))
            if bal_pay == bal_mid - Decimal("25"):
                ok("deposit_reduced_by_payment", str(bal_pay))
            else:
                bad("deposit_reduced_by_payment", f"mid={bal_mid} after={bal_pay}")
        else:
            bad("payment_voucher_payment", f"{r.status_code} {r.text[:400]}")

    print("\n=== 6) Contra Entry ===")
    if cash and bank:
        r = client.post(
            "/cashbook/contra",
            json={
                "voucher_date": date.today().isoformat(),
                "from_ledger_id": cash["id"],
                "to_ledger_id": bank["id"],
                "amount": "100.00",
                "narration": "E2E cash to bank",
            },
        )
        if r.status_code in (200, 201):
            ok("contra_entry", r.json().get("voucher_no"))
        else:
            bad("contra_entry", f"{r.status_code} {r.text[:400]}")
        r = client.post(
            "/cashbook/contra",
            json={
                "voucher_date": date.today().isoformat(),
                "from_ledger_id": cash["id"],
                "to_ledger_id": cash["id"],
                "amount": "10.00",
            },
        )
        if r.status_code >= 400:
            ok("contra_reject_same_ledger", str(r.status_code))
        else:
            bad("contra_reject_same_ledger", "accepted same ledger")
    else:
        bad("contra_entry", "missing cash/bank")

    print("\n=== 7) Reports: ledger / cashbook / daybook ===")
    if cash:
        r = client.get(f"/cashbook/ledger/{cash['id']}", params={"from_date": date.today().isoformat(), "to_date": date.today().isoformat()})
        if r.status_code == 200:
            data = r.json()
            ok("ledger_statement", f"entries={len(data.get('entries') or [])} closing={data.get('closing_balance')}")
        else:
            bad("ledger_statement", f"{r.status_code} {r.text[:200]}")

    r = client.get("/cashbook/cash-book", params={"from_date": date.today().isoformat(), "to_date": date.today().isoformat()})
    if r.status_code == 200:
        data = r.json()
        ok("cash_book", f"entries={len(data.get('entries') or [])}")
    else:
        bad("cash_book", f"{r.status_code} {r.text[:200]}")

    r = client.get("/cashbook/daybook", params={"from_date": date.today().isoformat(), "to_date": date.today().isoformat()})
    if r.status_code == 200:
        data = r.json()
        ok("daybook", f"entries={len(data.get('entries') or [])} debit={data.get('total_debit')}")
    else:
        bad("daybook", f"{r.status_code} {r.text[:200]}")

    r = client.get("/cashbook/patient-account", params={"patient_id": patient_id})
    if r.status_code == 200:
        data = r.json()
        ok("patient_account", f"deposit={data.get('deposit_balance')} entries={len(data.get('entries') or [])}")
    else:
        bad("patient_account", f"{r.status_code} {r.text[:200]}")

    print("\n=== 8) Menus present ===")
    r = client.get("/menus")
    if r.status_code == 200:
        menus = r.json()
        codes = {m.get("code") for m in menus}
        for needed in (
            "ledger_master",
            "advance_collection",
            "adjustment_entry",
            "receipt_voucher_adjustment_entry",
            "ledger_details",
            "cash_book",
            "daybook",
            "cashbook",
        ):
            if needed in codes:
                label = next(m.get("label") for m in menus if m.get("code") == needed)
                ok(f"menu:{needed}", label)
            else:
                bad(f"menu:{needed}", "not in /menus response")
    else:
        bad("menus", f"{r.status_code}")

    print("\n=== 9) OPD bill with advance adjust (if catalog available) ===")
    r = client.get("/opd-bills/catalog/services")
    services = r.json() if r.status_code == 200 else []
    r = client.get("/doctors", params={"page": 1, "page_size": 5})
    doctors = []
    if r.status_code == 200:
        body = r.json()
        doctors = body.get("items") or []
    bal = Decimal(str(client.get("/cashbook/patient-deposit", params={"patient_id": patient_id}).json().get("balance", 0)))
    if services and doctors and bal >= Decimal("10"):
        svc = services[0]
        doc = doctors[0]
        rate = Decimal(str(svc.get("rate") or 100))
        adjust = min(Decimal("10"), bal)
        net = rate - adjust
        if net < 0:
            net = Decimal("0")
            adjust = rate
        payload = {
            "patient_id": patient_id,
            "doctor_id": doc["id"],
            "token_session": "morning",
            "visit_category": "opd",
            "bill_date": date.today().isoformat(),
            "admin_charges": "0",
            "scheme_discount": "0",
            "sanctioned_scheme_amount": "0",
            "adjust_advance": str(adjust),
            "payments": [{"payment_mode_id": cash_mode["id"], "amount": str(net)}] if net > 0 else [],
            "lines": [
                {
                    "service_id": svc["id"],
                    "quantity": 1,
                    "rate": str(rate),
                }
            ],
        }
        # if net is 0, still need a payment of 0? validate may require payment. Use adjust only if net>0 or allow empty payments when net=0
        if net == 0:
            payload["payments"] = [{"payment_mode_id": cash_mode["id"], "amount": "0.00"}]
        r = client.post("/opd-bills", json=payload)
        if r.status_code in (200, 201):
            bill = r.json()
            ok("opd_bill_with_advance", f"{bill.get('bill_no')} net={bill.get('net_amount')} adj={bill.get('adjust_advance')}")
            r2 = client.get("/cashbook/patient-deposit", params={"patient_id": patient_id})
            bal2 = Decimal(str(r2.json().get("balance", 0)))
            if bal2 == bal - adjust:
                ok("opd_advance_deducted", f"{bal} -> {bal2}")
            else:
                bad("opd_advance_deducted", f"expected {bal - adjust}, got {bal2}")
        else:
            bad("opd_bill_with_advance", f"{r.status_code} {r.text[:500]}")
    else:
        print(f"  SKIP  opd_bill_with_advance — services={len(services)} doctors={len(doctors)} bal={bal}")

    print("\n==============================")
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print("==============================\n")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
