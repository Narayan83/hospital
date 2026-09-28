from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _write_row(ws, row: int, values: list[Any], *, bold: bool = False) -> int:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        if bold:
            cell.font = Font(bold=True)
    return row + 1


def _autosize_columns(ws, max_col: int) -> None:
    for col in range(1, max_col + 1):
        letter = get_column_letter(col)
        max_len = 0
        for cell in ws[letter]:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 40)


def build_bill_excel(context: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Bill"

    header_fill = PatternFill("solid", fgColor="EFF6FF")
    title_font = Font(bold=True, size=14, color="1E40AF")
    section_font = Font(bold=True, color="1E40AF")

    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    title_cell = ws.cell(row=row, column=1, value=context.get("hospital_name", "Hospital"))
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="center")
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    sub = ws.cell(row=row, column=1, value=context.get("bill_title", "Bill"))
    sub.alignment = Alignment(horizontal="center")
    row += 2

    meta_rows = [
        ("Bill No", context.get("bill_no"), "Bill Date", context.get("bill_date")),
        ("Patient ID", context.get("patient_no"), "Patient Name", context.get("patient_name")),
    ]
    if context.get("admission_no") is not None:
        meta_rows.extend(
            [
                ("Admission No", context.get("admission_no"), "Stay Days", context.get("stay_days")),
                ("Admit Date", context.get("admission_date"), "Discharge Date", context.get("discharge_date")),
                ("Ward / Bed", f"{context.get('ward_name', '—')} / {context.get('bed_no', '—')}", "Doctor", context.get("doctor_name")),
            ]
        )
    else:
        meta_rows.append(("Doctor", context.get("doctor_name"), "Department", context.get("department_name")))
        if context.get("visit_category"):
            meta_rows.append(("Visit Type", context.get("visit_category"), "Token No", context.get("token_number")))
    meta_rows.append(("Scheme", context.get("scheme"), "", ""))

    for label1, val1, label2, val2 in meta_rows:
        row = _write_row(ws, row, [label1, val1, label2, val2], bold=False)
        ws.cell(row=row - 1, column=1).font = Font(bold=True)
        ws.cell(row=row - 1, column=3).font = Font(bold=True)

    payments = context.get("payments") or []
    if payments:
        row += 1
        ws.cell(row=row, column=1, value="Payment Details").font = section_font
        row += 1
        for col, heading in enumerate(["Payment Mode", "Ledger", "Amount"], start=1):
            cell = ws.cell(row=row, column=col, value=heading)
            cell.font = Font(bold=True)
            cell.fill = header_fill
        row += 1
        for payment in payments:
            row = _write_row(
                ws,
                row,
                [payment.get("mode"), payment.get("ledger"), payment.get("amount")],
            )
    elif context.get("payment_mode"):
        row = _write_row(ws, row, ["Payment Mode", context.get("payment_mode")])

    row += 1
    ws.cell(row=row, column=1, value="Service Details").font = section_font
    row += 1
    line_headers = ["#", "Code", "Description", "Category", "Rate", "Qty", "Amount"]
    for col, heading in enumerate(line_headers, start=1):
        cell = ws.cell(row=row, column=col, value=heading)
        cell.font = Font(bold=True)
        cell.fill = header_fill
    row += 1
    for line in context.get("lines") or []:
        row = _write_row(
            ws,
            row,
            [
                line.get("sr"),
                line.get("code"),
                line.get("name"),
                line.get("category"),
                line.get("rate"),
                line.get("qty"),
                line.get("amount"),
            ],
        )

    row += 1
    totals = [
        ("Gross Amount", context.get("gross_amount")),
        ("Admin Charges", context.get("admin_charges")),
        ("Scheme Discount", context.get("scheme_discount")),
        ("Advance Adjusted", context.get("adjust_advance")),
        ("Net Amount", context.get("net_amount")),
    ]
    for label, value in totals:
        if label == "Advance Adjusted" and context.get("hide_advance_on_bill"):
            continue
        ws.cell(row=row, column=5, value=label).font = Font(bold=True)
        amount_cell = ws.cell(row=row, column=7, value=value)
        if label == "Net Amount":
            amount_cell.font = Font(bold=True, color="B91C1C")
        row += 1

    if context.get("remarks"):
        row += 1
        row = _write_row(ws, row, ["Remarks", context.get("remarks")])

    _autosize_columns(ws, 7)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
