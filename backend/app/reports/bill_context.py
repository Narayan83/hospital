from datetime import date, datetime
from decimal import Decimal
from typing import Any


HOSPITAL_NAME = "Hospital Management System"


def _profile_field(profile: Any, name: str, default: Any = None) -> Any:
    if isinstance(profile, dict):
        value = profile.get(name)
    else:
        value = getattr(profile, name, None)
    return default if value is None or value == "" else value


def hospital_header_context(profile: Any, *, name_field: str = "name") -> dict[str, Any]:
    name = _profile_field(profile, name_field) or _profile_field(profile, "name") or HOSPITAL_NAME
    address_lines = [
        _profile_field(profile, "address_line1"),
        _profile_field(profile, "address_line2"),
        _profile_field(profile, "address_line3"),
        _profile_field(profile, "address_line4"),
    ]
    city = _profile_field(profile, "city")
    state = _profile_field(profile, "state")
    pin_code = _profile_field(profile, "pin_code")
    phone = str(_profile_field(profile, "phone") or _profile_field(profile, "mobile") or "").strip()
    email = str(_profile_field(profile, "email") or "").strip()
    website = str(_profile_field(profile, "website") or "").strip()
    gstin = str(_profile_field(profile, "gstin") or "").strip()
    software_id = str(_profile_field(profile, "software_id") or "").strip()

    trailing_address = [part for part in [city, state, pin_code] if part]
    address_parts = [part for part in address_lines if part]
    if trailing_address:
        address_parts.append(", ".join(trailing_address))

    return {
        "hospital_name": name,
        "hospital_address": ", ".join(address_parts),
        "hospital_address_lines": [part for part in address_lines if part],
        "hospital_phone": phone,
        "hospital_email": email,
        "hospital_website": website,
        "hospital_gstin": gstin,
        "hospital_software_id": software_id,
    }


def _fmt_money(value: Any) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):.2f}"


def _fmt_date(value: date | datetime | str | None) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    if len(text) >= 10 and text[4] == "-":
        parts = text[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return text


def _bill_field(bill: Any, name: str, default: Any = None) -> Any:
    if isinstance(bill, dict):
        value = bill.get(name)
    else:
        value = getattr(bill, name, None)
    return default if value is None else value


def _bill_lines(bill: Any) -> list[Any]:
    if isinstance(bill, dict):
        return bill.get("lines") or []
    return getattr(bill, "lines", None) or []


def _active_lines(bill: Any) -> list[Any]:
    lines = _bill_lines(bill)
    if isinstance(bill, dict):
        return lines
    return [line for line in lines if getattr(line, "is_active", True)]


def _line_rows(lines: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(lines, start=1):
        if isinstance(line, dict):
            rows.append(
                {
                    "sr": index,
                    "code": line.get("service_code", ""),
                    "name": line.get("service_name", ""),
                    "category": line.get("category_name") or line.get("sub_category_name") or "",
                    "rate": _fmt_money(line.get("rate")),
                    "qty": line.get("quantity", 1),
                    "amount": _fmt_money(line.get("amount")),
                }
            )
        else:
            rows.append(
                {
                    "sr": index,
                    "code": line.service_code,
                    "name": line.service_name,
                    "category": line.category_name or line.sub_category_name or "",
                    "rate": _fmt_money(line.rate),
                    "qty": line.quantity,
                    "amount": _fmt_money(line.amount),
                }
            )
    return rows


def _payment_rows(bill: Any) -> list[dict[str, Any]]:
    payments = _bill_field(bill, "payments", []) or []
    rows = []
    for payment in payments:
        if isinstance(payment, dict):
            rows.append(
                {
                    "mode": payment.get("payment_mode_name") or payment.get("payment_mode_code") or "—",
                    "ledger": payment.get("ledger_name") or payment.get("ledger_code") or "—",
                    "amount": _fmt_money(payment.get("amount")),
                }
            )
        else:
            rows.append(
                {
                    "mode": getattr(payment, "payment_mode_name", None)
                    or getattr(payment, "payment_mode_code", None)
                    or "—",
                    "ledger": getattr(payment, "ledger_name", None)
                    or getattr(payment, "ledger_code", None)
                    or "—",
                    "amount": _fmt_money(getattr(payment, "amount", 0)),
                }
            )
    return rows


def _payment_context(bill: Any) -> dict[str, Any]:
    payments = _payment_rows(bill)
    return {
        "payment_mode": _bill_field(bill, "payment_mode_name", "—"),
        "payments": payments,
        "has_split_payments": len(payments) > 1,
    }


def _patient_display_name(patient: Any) -> str:
    if isinstance(patient, dict):
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        name = " ".join(p for p in parts if p)
        return name or patient.get("patient_name") or "—"
    parts = [
        getattr(patient, "first_name", None),
        getattr(patient, "middle_name", None),
        getattr(patient, "last_name", None),
    ]
    name = " ".join(p for p in parts if p)
    return name or "—"


def _patient_field(patient: Any, name: str, default: Any = None) -> Any:
    if isinstance(patient, dict):
        value = patient.get(name)
    else:
        value = getattr(patient, name, None)
    return default if value is None or value == "" else value


def _patient_full_name(patient: Any) -> str:
    title = _patient_field(patient, "title", "")
    parts = [
        title,
        _patient_field(patient, "first_name", ""),
        _patient_field(patient, "middle_name", ""),
        _patient_field(patient, "last_name", ""),
    ]
    name = " ".join(str(part) for part in parts if part)
    return name or _patient_display_name(patient)


def _patient_contact_address(patient: Any) -> str:
    parts = []
    for field in (
        "contact_address1",
        "contact_address2",
        "contact_address3",
        "contact_address4",
        "contact_address5",
    ):
        value = _patient_field(patient, field)
        if value:
            parts.append(str(value))
    return ", ".join(parts) or "—"


def build_patient_card_context(patient: Any) -> dict[str, Any]:
    gender = _patient_field(patient, "gender", "—")
    gender_labels = {"M": "Male", "F": "Female", "O": "Other"}
    mobile = (
        _patient_field(patient, "mobile")
        or _patient_field(patient, "mobile2")
        or _patient_field(patient, "phone")
        or "—"
    )
    return {
        "patient_no": _patient_field(patient, "patient_no", "—"),
        "patient_name": _patient_full_name(patient),
        "age": _patient_field(patient, "age", "—"),
        "gender": gender,
        "gender_label": gender_labels.get(str(gender), str(gender)),
        "date_of_birth": _fmt_date(_patient_field(patient, "date_of_birth")),
        "blood_group": _patient_field(patient, "blood_group", "—"),
        "mobile": mobile,
        "address": _patient_contact_address(patient),
        "patient_type": _patient_field(patient, "patient_type", "General"),
        "hospital_section": _patient_field(patient, "hospital_section_name")
        or _patient_field(patient, "facility", "—"),
        "registered_on": _fmt_date(_patient_field(patient, "created_at")),
    }


def build_opd_casesheet_context(
    patient: Any,
    *,
    case_date: str,
    doctor_name: str,
    hospital_name: str = HOSPITAL_NAME,
) -> dict[str, Any]:
    if isinstance(patient, dict):
        patient_no = patient.get("patient_no") or "—"
    else:
        patient_no = getattr(patient, "patient_no", None) or "—"
    return {
        "hospital_name": hospital_name,
        "page_title": "OPD Case Sheet",
        "patient_no": patient_no,
        "patient_name": _patient_display_name(patient),
        "case_date": case_date,
        "doctor_name": doctor_name or "—",
    }


def build_opd_bill_context(bill: Any, *, hospital_name: str = HOSPITAL_NAME) -> dict[str, Any]:
    visit = _bill_field(bill, "visit_category", "opd") or "opd"
    payment_ctx = _payment_context(bill)
    return {
        "hospital_name": hospital_name,
        "bill_title": "OPD Bill / Receipt",
        "bill_no": _bill_field(bill, "bill_no"),
        "bill_date": _fmt_date(_bill_field(bill, "bill_date")),
        "patient_no": _bill_field(bill, "patient_no"),
        "patient_name": _bill_field(bill, "patient_name"),
        "doctor_name": _bill_field(bill, "doctor_name", "—"),
        "department_name": _bill_field(bill, "department_name", "—"),
        **payment_ctx,
        "cash_credit": "Cash" if _bill_field(bill, "is_cash", True) else "Credit",
        "scheme": _bill_field(bill, "scheme", "—"),
        "visit_category": str(visit).replace("_", " ").upper(),
        "token_number": _bill_field(bill, "token_number"),
        "admin_charges": _fmt_money(_bill_field(bill, "admin_charges", 0)),
        "scheme_discount": _fmt_money(_bill_field(bill, "scheme_discount", 0)),
        "adjust_advance": _fmt_money(_bill_field(bill, "adjust_advance", 0)),
        "gross_amount": _fmt_money(_bill_field(bill, "gross_amount", 0)),
        "net_amount": _fmt_money(_bill_field(bill, "net_amount", 0)),
        "lines": _line_rows(_active_lines(bill)),
        "remarks": _bill_field(bill, "remarks", ""),
    }


def build_ipd_bill_context(bill: Any, *, hospital_name: str = HOSPITAL_NAME) -> dict[str, Any]:
    payment_ctx = _payment_context(bill)
    return {
        "hospital_name": hospital_name,
        "bill_title": "IPD Discharge Bill",
        "bill_no": _bill_field(bill, "bill_no"),
        "bill_date": _fmt_date(_bill_field(bill, "discharge_date")),
        "admission_no": _bill_field(bill, "admission_no", "—"),
        "admission_date": _fmt_date(_bill_field(bill, "admission_date")),
        "discharge_date": _fmt_date(_bill_field(bill, "discharge_date")),
        "stay_days": _bill_field(bill, "stay_days", "—"),
        "patient_no": _bill_field(bill, "patient_no"),
        "patient_name": _bill_field(bill, "patient_name"),
        "ward_name": _bill_field(bill, "ward_name", "—"),
        "bed_no": _bill_field(bill, "bed_no", "—"),
        "doctor_name": _bill_field(bill, "doctor_name", "—"),
        "department_name": _bill_field(bill, "department_name", "—"),
        **payment_ctx,
        "cash_credit": "Cash" if _bill_field(bill, "is_cash", True) else "Credit",
        "scheme": _bill_field(bill, "scheme", "—"),
        "admin_charges": _fmt_money(_bill_field(bill, "admin_charges", 0)),
        "scheme_discount": _fmt_money(_bill_field(bill, "scheme_discount", 0)),
        "adjust_advance": (
            "0.00"
            if _bill_field(bill, "hide_advance_on_bill", False)
            else _fmt_money(_bill_field(bill, "adjust_advance", 0))
        ),
        "hide_advance_on_bill": bool(_bill_field(bill, "hide_advance_on_bill", False)),
        "gross_amount": _fmt_money(_bill_field(bill, "gross_amount", 0)),
        "net_amount": _fmt_money(_bill_field(bill, "net_amount", 0)),
        "lines": _line_rows(_active_lines(bill)),
        "remarks": _bill_field(bill, "remarks", ""),
    }


def _doctor_display_name(name: Any, qualification: Any) -> str:
    name = (name or "").strip() if isinstance(name, str) else name
    qualification = (qualification or "").strip() if isinstance(qualification, str) else qualification
    if not name:
        return "—"
    if qualification:
        return f"{name}, {qualification}"
    return name


def _pathology_line_rows(lines: list[Any]) -> list[dict[str, Any]]:
    """Billable pathology lines only — omit bundle sub-tests (no rate/amount)."""
    rows: list[dict[str, Any]] = []
    for line in lines:
        if isinstance(line, dict):
            panel_id = line.get("panel_service_id")
            is_parent = bool(line.get("is_panel_parent"))
            code = line.get("service_code", "")
            name = line.get("service_name", "")
            category = line.get("category_name") or line.get("sub_category_name") or ""
            rate_raw = line.get("rate")
            qty = line.get("quantity", 1)
            amount_raw = line.get("amount")
        else:
            panel_id = getattr(line, "panel_service_id", None)
            is_parent = bool(getattr(line, "is_panel_parent", False))
            code = line.service_code
            name = line.service_name
            category = line.category_name or line.sub_category_name or ""
            rate_raw = line.rate
            qty = line.quantity
            amount_raw = line.amount
        is_bundle_member = bool(panel_id) and not is_parent
        if is_bundle_member:
            continue
        try:
            rate_val = Decimal(str(rate_raw if rate_raw is not None else 0))
            amount_val = Decimal(str(amount_raw if amount_raw is not None else 0))
        except Exception:
            rate_val = Decimal("0")
            amount_val = Decimal("0")
        # Sub-tests and other non-charged lines are not printed on the bill.
        if not is_parent and rate_val == 0 and amount_val == 0:
            continue
        rows.append(
            {
                "sr": len(rows) + 1,
                "code": code,
                "name": name,
                "category": category,
                "rate": _fmt_money(rate_raw),
                "qty": qty,
                "amount": _fmt_money(amount_raw),
            }
        )
    return rows


def build_pathology_bill_context(bill: Any, *, hospital_name: str = HOSPITAL_NAME) -> dict[str, Any]:
    order_status = _bill_field(bill, "order_status", "—") or "—"
    pathologist_name = _bill_field(bill, "doctor_name", "—")
    doctor_qualification = _bill_field(bill, "doctor_qualification", None)
    referring_doctor = _bill_field(bill, "referring_doctor", "—") or "—"
    # Bill receipt "Doctor Name" shows the reference/referring doctor (not pathologist).
    doctor_name = referring_doctor if referring_doctor not in ("", "—") else "—"
    return {
        "hospital_name": hospital_name,
        "bill_title": "Pathology Bill / Receipt",
        "bill_no": _bill_field(bill, "bill_no"),
        "bill_date": _fmt_date(_bill_field(bill, "bill_date")),
        "patient_no": _bill_field(bill, "patient_no"),
        "patient_name": _bill_field(bill, "patient_name"),
        "patient_gender": _bill_field(bill, "patient_gender", "—"),
        "patient_age": _bill_field(bill, "patient_age", "—"),
        "doctor_name": doctor_name,
        "doctor_qualification": doctor_qualification or "—",
        "doctor_display": _doctor_display_name(pathologist_name, doctor_qualification),
        "referring_doctor": referring_doctor,
        "department_name": _bill_field(bill, "department_name", "Pathology"),
        "payment_mode": _bill_field(bill, "payment_mode_name", "—"),
        "cash_credit": "Cash" if _bill_field(bill, "is_cash", True) else "Credit",
        "scheme": _bill_field(bill, "scheme", "—"),
        "sample_no": _bill_field(bill, "sample_no", "—"),
        "order_status": str(order_status).replace("_", " ").title(),
        "admin_charges": _fmt_money(_bill_field(bill, "admin_charges", 0)),
        "scheme_discount": _fmt_money(_bill_field(bill, "scheme_discount", 0)),
        "adjust_advance": _fmt_money(_bill_field(bill, "adjust_advance", 0)),
        "gross_amount": _fmt_money(_bill_field(bill, "gross_amount", 0)),
        "net_amount": _fmt_money(_bill_field(bill, "net_amount", 0)),
        "lines": _pathology_line_rows(_active_lines(bill)),
        "remarks": _bill_field(bill, "remarks", ""),
    }


def _pharmacy_line_rows(lines: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(lines, start=1):
        rows.append(
            {
                "sr": index,
                "code": _bill_field(line, "item_code", ""),
                "name": _bill_field(line, "item_name", ""),
                "category": _bill_field(line, "batch_no", "") or _bill_field(line, "unit", ""),
                "rate": _fmt_money(_bill_field(line, "rate", 0)),
                "qty": _bill_field(line, "quantity", 1),
                "amount": _fmt_money(_bill_field(line, "line_net", _bill_field(line, "amount", 0))),
            }
        )
    return rows


def build_pharmacy_sale_bill_context(bill: Any, *, hospital_name: str = HOSPITAL_NAME) -> dict[str, Any]:
    return {
        "hospital_name": hospital_name,
        "bill_title": "Medical Bill / Receipt",
        "bill_no": _bill_field(bill, "bill_no"),
        "bill_date": _fmt_date(_bill_field(bill, "bill_date")),
        "patient_no": "—",
        "patient_name": _bill_field(bill, "patient_name", "Walk-in Customer") or "Walk-in Customer",
        "doctor_name": _bill_field(bill, "doctor_name", "—") or "—",
        "department_name": "Medical Shop",
        "payment_mode": "Cash" if _bill_field(bill, "is_cash", True) else "Credit",
        "cash_credit": "Cash" if _bill_field(bill, "is_cash", True) else "Credit",
        "scheme": _bill_field(bill, "scheme", "—") or "—",
        "admin_charges": "0.00",
        "scheme_discount": _fmt_money(_bill_field(bill, "discount_amount", 0)),
        "adjust_advance": "0.00",
        "gross_amount": _fmt_money(_bill_field(bill, "gross_amount", 0)),
        "net_amount": _fmt_money(_bill_field(bill, "net_amount", 0)),
        "lines": _pharmacy_line_rows(_active_lines(bill)),
        "remarks": _bill_field(bill, "remarks", ""),
    }


def _additional_range_rows(value: Any) -> list[dict[str, str]]:
    """Normalise reference-range rows (pydantic objects or dicts) for the template."""
    if not value:
        return []
    rows: list[dict[str, str]] = []
    for entry in value:
        if isinstance(entry, dict):
            age_group = entry.get("age_group")
            gender = entry.get("gender")
            range_text = entry.get("range_text")
        else:
            age_group = getattr(entry, "age_group", None)
            gender = getattr(entry, "gender", None)
            range_text = getattr(entry, "range_text", None)
        rows.append(
            {
                "age_group": age_group or "",
                "gender": gender or "",
                "range_text": range_text or "",
            }
        )
    return rows


def build_pathology_report_context(
    bill: Any,
    order: Any | None = None,
    *,
    hospital_name: str = HOSPITAL_NAME,
    print_layout_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = build_pathology_bill_context(bill, hospital_name=hospital_name)
    # Map each bill line to its parent bundle so report rows can be grouped under
    # the main service (main service prints once, sub-tests listed beneath it).
    line_meta: dict[str, dict[str, Any]] = {}
    for line in _active_lines(bill):
        if isinstance(line, dict):
            line_meta[line.get("id")] = {
                "panel_service_id": line.get("panel_service_id"),
                "panel_name": line.get("panel_name"),
            }
        else:
            line_meta[getattr(line, "id", None)] = {
                "panel_service_id": getattr(line, "panel_service_id", None),
                "panel_name": getattr(line, "panel_name", None),
            }
    tests = []
    if order is not None:
        result_rows = getattr(order, "results", None) or (
            order.get("results") if isinstance(order, dict) else []
        )
        # Order by bundle first (panel group), then member order within the bundle.
        line_sort: dict[str, int] = {}
        panel_group: dict[str, int] = {}
        line_panel: dict[str, str] = {}
        for line in sorted(
            _active_lines(bill),
            key=lambda ln: int(
                (ln.get("sort_order") if isinstance(ln, dict) else getattr(ln, "sort_order", 0)) or 0
            ),
        ):
            if isinstance(line, dict):
                line_id = str(line.get("id") or "")
                order = int(line.get("sort_order") or 0)
                is_parent = bool(line.get("is_panel_parent"))
                panel_id = line.get("service_id") if is_parent else line.get("panel_service_id")
            else:
                line_id = str(getattr(line, "id", "") or "")
                order = int(getattr(line, "sort_order", 0) or 0)
                is_parent = bool(getattr(line, "is_panel_parent", False))
                panel_id = (
                    getattr(line, "service_id", None)
                    if is_parent
                    else getattr(line, "panel_service_id", None)
                )
            line_sort[line_id] = order
            if panel_id:
                panel_key = str(panel_id)
                line_panel[line_id] = panel_key
                if is_parent:
                    panel_group[panel_key] = order
                else:
                    panel_group.setdefault(panel_key, order)

        def _result_sort_key(row: Any) -> tuple:
            if isinstance(row, dict):
                sort_order = row.get("sort_order")
                bill_line_id = str(row.get("bill_line_id") or "")
                group_order = row.get("panel_group_order")
                line_order = row.get("bill_line_sort_order")
                panel_id = row.get("panel_service_id")
            else:
                sort_order = getattr(row, "sort_order", None)
                bill_line_id = str(getattr(row, "bill_line_id", "") or "")
                group_order = getattr(row, "panel_group_order", None)
                line_order = getattr(row, "bill_line_sort_order", None)
                panel_id = getattr(row, "panel_service_id", None)
            if line_order is None:
                line_order = line_sort.get(bill_line_id, 10**9)
            if group_order is None:
                panel_key = str(panel_id or line_panel.get(bill_line_id) or "")
                group_order = panel_group.get(panel_key, line_order)
            explicit = int(sort_order) if sort_order is not None else 10**9
            return (int(group_order), int(line_order), explicit, bill_line_id)

        for row in sorted(result_rows, key=_result_sort_key):
            if isinstance(row, dict):
                pname = row.get("parameter_name") or row.get("service_name") or "—"
                result_display = row.get("result_value") or ""
                meta = line_meta.get(row.get("bill_line_id"), {})
                tests.append(
                    {
                        "name": pname,
                        "code": row.get("parameter_code") or row.get("service_code") or "",
                        "service_name": row.get("service_name") or "",
                        "result": result_display,
                        "unit": row.get("unit_name") or "—",
                        "reference_range": row.get("reference_range_text") or "—",
                        "additional_ranges": _additional_range_rows(row.get("additional_ranges")),
                        "method": row.get("method") or "—",
                        "is_abnormal": bool(row.get("is_abnormal")),
                        "panel_service_id": meta.get("panel_service_id"),
                        "panel_name": meta.get("panel_name"),
                    }
                )
            else:
                result_display = row.result_value or ""
                meta = line_meta.get(getattr(row, "bill_line_id", None), {})
                tests.append(
                    {
                        "name": row.parameter_name or row.service_name or "—",
                        "code": row.parameter_code or row.service_code or "",
                        "service_name": row.service_name or "",
                        "result": result_display,
                        "unit": row.unit_name or "—",
                        "reference_range": row.reference_range_text or "—",
                        "additional_ranges": _additional_range_rows(
                            getattr(row, "additional_ranges", None)
                        ),
                        "method": row.method or "—",
                        "is_abnormal": bool(row.is_abnormal),
                        "panel_service_id": meta.get("panel_service_id"),
                        "panel_name": meta.get("panel_name"),
                    }
                )
    else:
        for line in base["lines"]:
            tests.append(
                {
                    "name": line["name"],
                    "code": line["code"],
                    "service_name": line["name"],
                    "result": "Pending",
                    "unit": "—",
                    "reference_range": "—",
                    "additional_ranges": [],
                    "method": "—",
                    "is_abnormal": False,
                    "panel_service_id": None,
                    "panel_name": None,
                }
            )
    sample_no = None
    sample_date = base["bill_date"]
    order_status = None
    if order:
        sample_no = _bill_field(order, "sample_no")
        sd = _bill_field(order, "sample_date")
        if sd:
            sample_date = _fmt_date(sd)
        order_status = _bill_field(order, "status")
    # Group tests under their main service / bundle. A bundle prints its name once
    # as a heading, then its sub-tests below it (with spacing). Standalone tests
    # print as their own single-row group.
    groups: list[dict[str, Any]] = []
    group_pos: dict[str, int] = {}
    for test in tests:
        panel_id = test.get("panel_service_id")
        panel_name = test.get("panel_name")
        if panel_id and panel_name:
            key = f"bundle::{panel_id}"
            if key not in group_pos:
                group_pos[key] = len(groups)
                groups.append({"header": panel_name, "tests": []})
            groups[group_pos[key]]["tests"].append(test)
        else:
            groups.append({"header": None, "tests": [test]})

    base.update(
        {
            "report_title": "Laboratory Investigation Report",
            "report_date": base["bill_date"],
            "sample_date": sample_date,
            "sample_no": sample_no or "—",
            "order_status": (order_status or "billed").replace("_", " ").title(),
            "tests": tests,
            "test_groups": groups,
            "report_layout": _pathology_report_layout(bill, print_layout_options),
        }
    )
    return base


def _pathology_report_layout_defaults() -> dict[str, int]:
    return {
        "font_size": 13,
        "row_padding": 6,
        "group_gap": 12,
        "sub_indent": 14,
    }


def merge_pathology_report_layout(
    base: dict[str, Any] | None,
    options: dict[str, Any] | None,
) -> dict[str, int]:
    """Merge saved Print Master layout options over report defaults."""
    merged = _pathology_report_layout_defaults()
    for source in (base, options):
        if not isinstance(source, dict):
            continue
        for key in merged:
            value = source.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                merged[key] = int(value)
    return merged


def _pathology_report_layout(bill: Any, print_options: dict[str, Any] | None = None) -> dict[str, int]:
    """Adjustable print spacing for the pathology report."""
    bill_override = _bill_field(bill, "report_layout", None)
    return merge_pathology_report_layout(
        bill_override if isinstance(bill_override, dict) else None,
        print_options,
    )


def _summary_field(summary: Any, name: str, default: str = "—") -> str:
    if isinstance(summary, dict):
        value = summary.get(name)
    else:
        value = getattr(summary, name, None)
    if value is None or value == "":
        return default
    return str(value)


def _gender_label(gender: str | None) -> str:
    if not gender:
        return "—"
    labels = {"M": "Male", "F": "Female", "O": "Other"}
    return labels.get(str(gender).upper(), str(gender))


def _parse_label_value_lines(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            name, value = line.split(":", 1)
            rows.append({"name": name.strip(), "value": value.strip()})
        else:
            rows.append({"name": line, "value": ""})
    return rows


def build_discharge_summary_context(
    summary: Any,
    *,
    hospital_name: str = HOSPITAL_NAME,
) -> dict[str, Any]:
    if isinstance(summary, dict):
        gender = summary.get("patient_gender")
        summary_date = summary.get("summary_date")
        admission_date = summary.get("admission_date")
        discharge_date = summary.get("discharge_date")
        stay_days = summary.get("stay_days")
    else:
        gender = getattr(summary, "patient_gender", None)
        summary_date = getattr(summary, "summary_date", None)
        admission_date = getattr(summary, "admission_date", None)
        discharge_date = getattr(summary, "discharge_date", None)
        stay_days = getattr(summary, "stay_days", None)

    investigation = _summary_field(summary, "investigation", "")
    medications = _summary_field(summary, "medications_on_discharge", "")
    advice = _summary_field(summary, "advice_follow_up", "")
    if isinstance(summary, dict):
        include_admission = bool(summary.get("include_admission_details", False))
    else:
        include_admission = bool(getattr(summary, "include_admission_details", False))

    return {
        "hospital_name": hospital_name,
        "report_title": "IPD Discharge Summary",
        "summary_no": _summary_field(summary, "summary_no"),
        "summary_date": _fmt_date(summary_date),
        "admission_no": _summary_field(summary, "admission_no"),
        "admission_date": _fmt_date(admission_date),
        "discharge_date": _fmt_date(discharge_date),
        "stay_days": stay_days if stay_days is not None else "—",
        "patient_no": _summary_field(summary, "patient_no"),
        "patient_name": _summary_field(summary, "patient_name"),
        "patient_age": _summary_field(summary, "patient_age"),
        "patient_gender": _gender_label(gender),
        "ward_name": _summary_field(summary, "ward_name"),
        "bed_no": _summary_field(summary, "bed_no"),
        "department_name": _summary_field(summary, "department_name"),
        "doctor_name": _summary_field(summary, "doctor_name"),
        "chief_complaint": _summary_field(summary, "chief_complaint", ""),
        "history_of_illness": _summary_field(summary, "history_of_illness", ""),
        "diagnosis_on_admission": _summary_field(summary, "diagnosis_on_admission", ""),
        "final_diagnosis": _summary_field(summary, "final_diagnosis", ""),
        "investigation": investigation,
        "investigation_rows": _parse_label_value_lines(investigation) if investigation else [],
        "treatment_given": _summary_field(summary, "treatment_given", ""),
        "procedures": _summary_field(summary, "procedures", ""),
        "condition_on_discharge": _summary_field(summary, "condition_on_discharge", ""),
        "medications_on_discharge": medications,
        "advice_lines": _parse_label_value_lines(medications) if medications else [],
        "advice_follow_up": advice,
        "remarks": _summary_field(summary, "remarks", ""),
        "include_admission_details": include_admission,
    }
