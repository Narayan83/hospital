"""Shared helpers for finding bills by bill no, patient id, or patient name."""

from __future__ import annotations

from app.api_client.client import ApiClient, ApiError


def patient_display_name(patient: dict | None) -> str:
    if not patient:
        return ""
    parts = [
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
    ]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    return str(patient.get("full_name") or patient.get("patient_name") or "").strip()


def resolve_patient_by_id(api: ApiClient, patient_no: str) -> dict | None:
    needle = (patient_no or "").strip()
    if not needle:
        return None
    result = api.search_patients(patient_no=needle, page_size=10)
    items = [
        item
        for item in (result.get("items") or [])
        if (item.get("patient_no") or "").strip().upper() == needle.upper()
    ]
    if not items:
        result = api.list_patients(search=needle, page_size=20)
        items = [
            item
            for item in (result.get("items") or [])
            if (item.get("patient_no") or "").strip().upper() == needle.upper()
        ]
    return items[0] if items else None


def search_patients_by_name(api: ApiClient, name: str) -> list[dict]:
    text = (name or "").strip()
    if not text:
        return []
    parts = text.split()
    first = parts[0] if parts else text
    last = parts[-1] if len(parts) > 1 else None
    try:
        result = api.search_patients(
            first_name=first,
            last_name=last,
            page_size=50,
        )
        items = list(result.get("items") or [])
    except ApiError:
        items = []
    if not items:
        try:
            result = api.list_patients(search=text, page_size=50)
            items = list(result.get("items") or [])
        except ApiError:
            items = []
    # Prefer matches that contain the typed text in the full name.
    needle = text.casefold()
    ranked: list[tuple[int, dict]] = []
    for item in items:
        display = patient_display_name(item).casefold()
        patient_no = (item.get("patient_no") or "").casefold()
        score = 0
        if display == needle or patient_no == needle:
            score = 0
        elif display.startswith(needle) or needle in display:
            score = 1
        else:
            score = 2
        ranked.append((score, item))
    ranked.sort(key=lambda pair: (pair[0], patient_display_name(pair[1]).casefold()))
    return [item for _, item in ranked]


def resolve_patient_for_search(
    api: ApiClient,
    parent,
    *,
    patient_no: str = "",
    name: str = "",
) -> dict | None:
    """Resolve a patient from id or name for bill find screens.

    - Patient id → exact resolve
    - Name → open master search with that name filled and results listed
    """
    from app.ui.components.patient_search_dialog import pick_patient

    needle_id = (patient_no or "").strip()
    needle_name = (name or "").strip()
    if needle_id:
        return resolve_patient_by_id(api, needle_id)

    if not needle_name:
        return None

    # Always show the matching patient list (name prefilled + auto-searched).
    return pick_patient(api, parent, initial_name=needle_name)


def list_bills_by_patient(
    api: ApiClient,
    bill_type: str,
    *,
    patient_no: str | None = None,
    patient_id: str | None = None,
) -> list[dict]:
    kind = (bill_type or "opd").strip().lower()
    if kind == "ipd":
        return list(
            api.list_ipd_discharges_by_patient(patient_id=patient_id, patient_no=patient_no) or []
        )
    if kind == "pathology":
        return list(
            api.list_pathology_bills_by_patient(patient_id=patient_id, patient_no=patient_no) or []
        )
    return list(api.list_opd_bills_by_patient(patient_id=patient_id, patient_no=patient_no) or [])


def fetch_bill_by_no(api: ApiClient, bill_type: str, bill_no: str) -> dict:
    kind = (bill_type or "opd").strip().lower()
    if kind == "ipd":
        return api.get_ipd_discharge_by_no(bill_no)
    if kind == "pathology":
        return api.get_pathology_bill_by_no(bill_no)
    return api.get_opd_bill_by_no(bill_no)


def fetch_bill_by_id(api: ApiClient, bill_type: str, bill_id: str) -> dict:
    kind = (bill_type or "opd").strip().lower()
    if kind == "ipd":
        return api.get_ipd_discharge(bill_id)
    if kind == "pathology":
        return api.get_pathology_bill(bill_id)
    return api.get_opd_bill(bill_id)


def bill_row_values(bill: dict, bill_type: str) -> list[str]:
    kind = (bill_type or "opd").strip().lower()
    bill_no = str(bill.get("bill_no") or "")
    bill_date = str(bill.get("bill_date") or "")
    patient_no = str(bill.get("patient_no") or "")
    patient_name = str(bill.get("patient_name") or "")
    net = bill.get("net_amount") or 0
    try:
        net_text = f"{float(net):.2f}"
    except (TypeError, ValueError):
        net_text = str(net)
    if kind == "ipd":
        doctor = str(bill.get("doctor_name") or "")
        ward = str(bill.get("ward_name") or bill.get("department_name") or "")
        return [bill_no, bill_date, patient_no, patient_name, doctor, ward, net_text]
    if kind == "pathology":
        doctor = str(bill.get("doctor_name") or bill.get("referring_doctor") or "")
        dept = str(bill.get("department_name") or "")
        return [bill_no, bill_date, patient_no, patient_name, doctor, dept, net_text]
    doctor = str(bill.get("doctor_name") or "")
    return [bill_no, bill_date, patient_no, patient_name, doctor, net_text]


def bill_table_headers(bill_type: str) -> list[str]:
    kind = (bill_type or "opd").strip().lower()
    if kind == "ipd":
        return ["Bill No", "Date", "Patient Id", "Name", "Doctor", "Ward", "Net"]
    if kind == "pathology":
        return ["Bill No", "Date", "Patient Id", "Name", "Pathologist", "Dept", "Net"]
    return ["Bill No", "Date", "Patient Id", "Name", "Doctor", "Net"]


def filter_active_bills(bills: list[dict]) -> list[dict]:
    return [
        bill
        for bill in bills
        if str(bill.get("status") or "").lower() not in {"cancelled", "canceled"}
    ]
