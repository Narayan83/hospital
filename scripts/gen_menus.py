"""Generate menu_definitions.py from legacy hsp.xlsx export."""
import re
from pathlib import Path

from openpyxl import load_workbook

EXCEL = Path(r"c:\Users\tss\OneDrive\Desktop\hsp.xlsx")
OUTPUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "seeds" / "menu_definitions.py"

ROOT_SORT = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    6: 50,
    104: 60,
    154: 70,
}

LABEL_OVERRIDES = {
    "medical records": "Medical Records",
    "user type creation": "User Type Creation",
    "service catagory master": "Service Category Master",
    "hospital sections creattion": "Hospital Sections",
    "commen masters": "Common Masters",
    "opd bill": "OPD Bill",
    "payment_mode_entry": "Payment Mode Entry",
    "scaned document date modification": "Scanned Document Date Modification",
    "alter scanned document id": "Alter Scanned Document ID",
    "form 3c reoport": "Form 3C Report",
    "marketing egency master": "Marketing Agency Master",
    "medicine purchase bill": "Medicine Purchase Bill",
}

CODE_OVERRIDES = {
    "service_catagory_master": "service_category_master",
    "hospital_sections_creattion": "hospital_sections",
    "commen_masters": "common_masters",
    "scaned_document_date_modification": "scanned_document_date_modification",
    "form_3c_reoport": "form_3c_report",
    "marketing_egency_master": "marketing_agency_master",
    "medicine_purchase_bill_109": "medicine_purchase_bill_shop",
}


def to_code(name: str, mcode: int) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip()).strip("_").lower()
    s = s or f"menu_{mcode}"
    return CODE_OVERRIDES.get(s, s)


def to_label(name: str) -> str:
    label = str(name).replace("_", " ")
    return LABEL_OVERRIDES.get(label.lower(), label)


def clean_form(value) -> str | None:
    if value is None or value == r"\N" or str(value).strip() in ("", "None"):
        return None
    return str(value).strip()


def clean_param(value) -> str | None:
    if value is None or str(value).strip() in ("", " ", "None", r"\N"):
        return None
    return str(value).strip()


def main() -> None:
    wb = load_workbook(EXCEL, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))[1:]

    roots: dict[int, dict] = {}
    children: list[dict] = []
    seen_codes: set[str] = set()

    for row in rows:
        mcode, under, uorder, mname, exform, prmtr = row
        if str(mname).strip().lower() == "exit":
            continue
        code = to_code(mname, mcode)
        base = code
        while code in seen_codes:
            code = f"{base}_{mcode}"
        seen_codes.add(code)
        entry = {
            "mcode": mcode,
            "under": under,
            "uorder": uorder or 0,
            "mname": mname,
            "code": code,
            "label": to_label(mname),
            "exform": clean_form(exform),
            "prmtr": clean_param(prmtr),
        }
        if under == 0:
            roots[mcode] = entry
        else:
            children.append(entry)

    lines = [
        "# Legacy hsp.xlsx export",
        "# (code, label, parent_code, sort_order, legacy_mcode, legacy_form, parameters)",
        "MENU_DEFINITIONS = [",
        '    ("dashboard", "Dashboard", None, 1, None, None, None),',
    ]
    for mcode in sorted(roots):
        r = roots[mcode]
        sort_order = ROOT_SORT.get(mcode, mcode)
        lines.append(
            f'    ("{r["code"]}", "{r["label"]}", None, {sort_order}, {r["mcode"]}, {r["exform"]!r}, {r["prmtr"]!r}),'
        )
    lines.append('    ("user_management", "User Management", None, 100, None, None, None),')

    for c in sorted(children, key=lambda x: (x["under"], x["uorder"], x["mcode"])):
        parent = roots.get(c["under"])
        parent_code = parent["code"] if parent else f"parent_{c['under']}"
        lines.append(
            f'    ("{c["code"]}", "{c["label"]}", "{parent_code}", {c["uorder"]}, {c["mcode"]}, {c["exform"]!r}, {c["prmtr"]!r}),'
        )

    for code, label, order in [
        ("user_registration", "User Registration", 1),
        ("role_management", "Role Creation", 2),
        ("role_menu_permissions", "Role Menu Permissions", 3),
        ("user_role_mapping", "Role Mapping", 4),
        ("notification_setup", "Notification Setup", 5),
    ]:
        lines.append(f'    ("{code}", "{label}", "user_management", {order}, None, None, None),')

    lines.append("]")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines) - 3} menu entries to {OUTPUT}")


if __name__ == "__main__":
    main()
