"""Build a clean Excel workbook for doctor collection reports (data only, no page headers)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.schemas.doctor_collection_report import (
    DoctorCollectionColumnReportRead,
    DoctorCollectionDateServiceReportRead,
    DoctorCollectionPaymentModeReportRead,
    DoctorCollectionReportRead,
)


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _autosize(ws) -> None:
    max_col = ws.max_column or 1
    for col in range(1, max_col + 1):
        letter = get_column_letter(col)
        width = 12
        for cell in ws[letter]:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 40))
        ws.column_dimensions[letter].width = width


def _write_section(ws, row: int, label: str, col_count: int) -> int:
    cell = ws.cell(row=row, column=1, value=label)
    cell.font = Font(bold=True)
    if col_count > 1:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_count)
    return row + 1


def _write_header(ws, row: int, headers: list[str]) -> int:
    for col, header in enumerate(headers, start=1):
        ws.cell(row=row, column=col, value=header).font = Font(bold=True)
    return row + 1


def build_doctor_collection_excel(
    report: (
        DoctorCollectionReportRead
        | DoctorCollectionColumnReportRead
        | DoctorCollectionPaymentModeReportRead
        | DoctorCollectionDateServiceReportRead
    ),
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    row = 1

    if isinstance(report, DoctorCollectionDateServiceReportRead):
        row = _write_date_service(ws, row, report)
    elif isinstance(report, DoctorCollectionColumnReportRead):
        row = _write_column(ws, row, report)
    elif isinstance(report, DoctorCollectionPaymentModeReportRead):
        row = _write_payment_mode(ws, row, report)
    elif report.report_type == "day_wise_summary":
        row = _write_day_wise(ws, row, report)
    else:
        row = _write_sharing(ws, row, report)

    _autosize(ws)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _write_date_service(ws, row: int, report: DoctorCollectionDateServiceReportRead) -> int:
    details = report.report_type == "date_service_details"
    if details:
        headers = [
            "Date",
            "Service",
            "Bill No",
            "Patient Id",
            "Payment Mode",
            "Original Rate",
            "Hospital",
            "Doctor",
            "Total",
        ]
    else:
        headers = ["Date", "Service", "Hospital", "Doctor", "Total"]
    row = _write_header(ws, row, headers)
    col_count = len(headers)

    for date_group in report.date_groups:
        bill_date = str(date_group.bill_date)
        row = _write_section(ws, row, f"Date: {bill_date}", col_count)
        for service in date_group.services:
            if details:
                if not service.rows:
                    ws.cell(row=row, column=1, value=bill_date)
                    ws.cell(row=row, column=2, value=service.service_name)
                    ws.cell(row=row, column=7, value=_money(service.hospital_amount))
                    ws.cell(row=row, column=8, value=_money(service.doctor_amount))
                    ws.cell(row=row, column=9, value=_money(service.total_amount))
                    row += 1
                else:
                    for detail in service.rows:
                        ws.cell(row=row, column=1, value=bill_date)
                        ws.cell(row=row, column=2, value=service.service_name)
                        ws.cell(row=row, column=3, value=detail.bill_no)
                        ws.cell(row=row, column=4, value=detail.patient_no)
                        ws.cell(row=row, column=5, value=detail.payment_mode)
                        ws.cell(row=row, column=6, value=_money(detail.original_rate))
                        ws.cell(row=row, column=7, value=_money(detail.hospital_amount))
                        ws.cell(row=row, column=8, value=_money(detail.doctor_amount))
                        ws.cell(row=row, column=9, value=_money(detail.total_amount))
                        row += 1
                total_row = [
                    "",
                    f"{service.service_name} Total",
                    "",
                    "",
                    "",
                    "",
                    _money(service.hospital_amount),
                    _money(service.doctor_amount),
                    _money(service.total_amount),
                ]
                for col, value in enumerate(total_row, start=1):
                    cell = ws.cell(row=row, column=col, value=value)
                    cell.font = Font(bold=True)
                row += 1
            else:
                ws.cell(row=row, column=1, value=bill_date)
                ws.cell(row=row, column=2, value=service.service_name)
                ws.cell(row=row, column=3, value=_money(service.hospital_amount))
                ws.cell(row=row, column=4, value=_money(service.doctor_amount))
                ws.cell(row=row, column=5, value=_money(service.total_amount))
                row += 1
        date_total = (
            ["Date Total", "", "", "", "", "", _money(date_group.hospital_amount),
             _money(date_group.doctor_amount), _money(date_group.total_amount)]
            if details
            else [
                "Date Total",
                "",
                _money(date_group.hospital_amount),
                _money(date_group.doctor_amount),
                _money(date_group.total_amount),
            ]
        )
        for col, value in enumerate(date_total, start=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.font = Font(bold=True)
        row += 2

    overall = (
        ["Overall Total", "", "", "", "", "", _money(report.overall_hospital_amount),
         _money(report.overall_doctor_amount), _money(report.overall_total_amount)]
        if details
        else [
            "Overall Total",
            "",
            _money(report.overall_hospital_amount),
            _money(report.overall_doctor_amount),
            _money(report.overall_total_amount),
        ]
    )
    for col, value in enumerate(overall, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = Font(bold=True)
    return row + 1


def _write_day_wise(ws, row: int, report: DoctorCollectionReportRead) -> int:
    headers = ["Date", "Hospital", "Doctor", "Total"]
    row = _write_header(ws, row, headers)
    for doctor in report.doctors:
        row = _write_section(ws, row, f"Doctor: {doctor.doctor_name}", 4)
        for date_group in doctor.date_groups:
            ws.cell(row=row, column=1, value=str(date_group.bill_date))
            ws.cell(row=row, column=2, value=_money(date_group.hospital_amount))
            ws.cell(row=row, column=3, value=_money(date_group.doctor_amount))
            ws.cell(row=row, column=4, value=_money(date_group.total_amount))
            row += 1
        for col, value in enumerate(
            [
                "Doctor Total",
                _money(doctor.grand_hospital_amount),
                _money(doctor.grand_doctor_amount),
                _money(doctor.grand_total_amount),
            ],
            start=1,
        ):
            ws.cell(row=row, column=col, value=value).font = Font(bold=True)
        row += 2
    for col, value in enumerate(
        [
            "Overall Total",
            _money(report.overall_hospital_amount),
            _money(report.overall_doctor_amount),
            _money(report.overall_total_amount),
        ],
        start=1,
    ):
        ws.cell(row=row, column=col, value=value).font = Font(bold=True)
    return row + 1


def _write_sharing(ws, row: int, report: DoctorCollectionReportRead) -> int:
    headers = [
        "Date",
        "Bill No",
        "Patient Id",
        "Payment Mode",
        "Service",
        "Original Rate",
        "Hospital",
        "Doctor",
        "Total",
    ]
    row = _write_header(ws, row, headers)
    for doctor in report.doctors:
        row = _write_section(ws, row, f"Doctor: {doctor.doctor_name}", 9)
        for date_group in doctor.date_groups:
            row = _write_section(ws, row, f"Date: {date_group.bill_date}", 9)
            for detail in date_group.rows:
                ws.cell(row=row, column=1, value=str(detail.bill_date))
                ws.cell(row=row, column=2, value=detail.bill_no)
                ws.cell(row=row, column=3, value=detail.patient_no)
                ws.cell(row=row, column=4, value=detail.payment_mode)
                ws.cell(row=row, column=5, value=detail.service_name)
                ws.cell(row=row, column=6, value=_money(detail.original_rate))
                ws.cell(row=row, column=7, value=_money(detail.hospital_amount))
                ws.cell(row=row, column=8, value=_money(detail.doctor_amount))
                ws.cell(row=row, column=9, value=_money(detail.total_amount))
                row += 1
            for col, value in enumerate(
                [
                    "Date Total",
                    "",
                    "",
                    "",
                    "",
                    "",
                    _money(date_group.hospital_amount),
                    _money(date_group.doctor_amount),
                    _money(date_group.total_amount),
                ],
                start=1,
            ):
                ws.cell(row=row, column=col, value=value).font = Font(bold=True)
            row += 1
        for col, value in enumerate(
            [
                "Doctor Total",
                "",
                "",
                "",
                "",
                "",
                _money(doctor.grand_hospital_amount),
                _money(doctor.grand_doctor_amount),
                _money(doctor.grand_total_amount),
            ],
            start=1,
        ):
            ws.cell(row=row, column=col, value=value).font = Font(bold=True)
        row += 1
        if doctor.service_summary:
            row = _write_section(ws, row, "Service Summary", 9)
            for svc in doctor.service_summary:
                ws.cell(row=row, column=5, value=svc.service_name)
                ws.cell(row=row, column=6, value=_money(svc.total_amount))
                ws.cell(row=row, column=7, value=_money(svc.hospital_amount))
                ws.cell(row=row, column=8, value=_money(svc.doctor_amount))
                row += 1
        row += 1
    for col, value in enumerate(
        [
            "Overall Total",
            "",
            "",
            "",
            "",
            "",
            _money(report.overall_hospital_amount),
            _money(report.overall_doctor_amount),
            _money(report.overall_total_amount),
        ],
        start=1,
    ):
        ws.cell(row=row, column=col, value=value).font = Font(bold=True)
    return row + 1


def _write_payment_mode(ws, row: int, report: DoctorCollectionPaymentModeReportRead) -> int:
    headers = ["Payment Mode / Doctor", "Hospital", "Doctor Share", "Total"]
    row = _write_header(ws, row, headers)
    for mode in report.payment_modes:
        row = _write_section(ws, row, f"Payment Mode: {mode.payment_mode}", 4)
        for doctor in mode.doctors:
            ws.cell(row=row, column=1, value=doctor.doctor_name)
            ws.cell(row=row, column=2, value=_money(doctor.hospital_amount))
            ws.cell(row=row, column=3, value=_money(doctor.doctor_amount))
            ws.cell(row=row, column=4, value=_money(doctor.total_amount))
            row += 1
        for col, value in enumerate(
            [
                "Mode Total",
                _money(mode.hospital_amount),
                _money(mode.doctor_amount),
                _money(mode.total_amount),
            ],
            start=1,
        ):
            ws.cell(row=row, column=col, value=value).font = Font(bold=True)
        row += 2
    for col, value in enumerate(
        [
            "Overall Total",
            _money(report.overall_hospital_amount),
            _money(report.overall_doctor_amount),
            _money(report.overall_total_amount),
        ],
        start=1,
    ):
        ws.cell(row=row, column=col, value=value).font = Font(bold=True)
    return row + 1


def _write_column(ws, row: int, report: DoctorCollectionColumnReportRead) -> int:
    service_ids = [col.service_id for col in report.service_columns]
    headers = ["Date", "Bill No", "Patient Id", "Name", "Payment Mode"]
    headers.extend(col.service_name for col in report.service_columns)
    headers.append("Total")
    row = _write_header(ws, row, headers)
    col_count = len(headers)
    for doctor in report.doctors:
        row = _write_section(ws, row, f"Doctor: {doctor.doctor_name}", col_count)
        for detail in doctor.rows:
            ws.cell(row=row, column=1, value=str(detail.bill_date))
            ws.cell(row=row, column=2, value=detail.bill_no)
            ws.cell(row=row, column=3, value=detail.patient_no)
            ws.cell(row=row, column=4, value=detail.patient_name)
            ws.cell(row=row, column=5, value=detail.payment_mode)
            for idx, service_id in enumerate(service_ids):
                amount = detail.amounts.get(service_id)
                ws.cell(
                    row=row,
                    column=6 + idx,
                    value=_money(amount) if amount else "",
                )
            ws.cell(row=row, column=col_count, value=_money(detail.total_amount))
            row += 1
        ws.cell(row=row, column=5, value="Doctor Total").font = Font(bold=True)
        for idx, service_id in enumerate(service_ids):
            cell = ws.cell(
                row=row,
                column=6 + idx,
                value=_money(doctor.column_totals.get(service_id)),
            )
            cell.font = Font(bold=True)
        ws.cell(row=row, column=col_count, value=_money(doctor.grand_total_amount)).font = Font(
            bold=True
        )
        row += 2
    ws.cell(row=row, column=1, value="Overall Total").font = Font(bold=True)
    ws.cell(row=row, column=col_count, value=_money(report.overall_total_amount)).font = Font(
        bold=True
    )
    return row + 1
