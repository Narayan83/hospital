from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.short_bill import ShortBillRead, ShortBillReportRead


def build_short_bill_report_context(report: ShortBillReportRead) -> dict[str, Any]:
    return {
        "report_title": report.short_bill_type_name.upper(),
        "billing_type_label": report.short_bill_type_name,
        "period_label": (
            f"FROM {_fmt_date(report.from_date)} TO {_fmt_date(report.to_date)}"
        ),
        "rows": [
            {
                "serial_no": row.serial_no,
                "bill_date": _fmt_date(row.bill_date),
                "patient_name": row.patient_name,
                "amount": _fmt_money(row.amount),
            }
            for row in report.rows
        ],
        "grand_total": _fmt_money(report.grand_total),
        "has_rows": bool(report.rows),
    }


def build_short_bill_receipt_context(bill: ShortBillRead) -> dict[str, Any]:
    amount = _fmt_money(bill.amount)
    title = (bill.short_bill_type_name or "Bill").upper()
    return {
        "bill_title": title,
        "bill_no": bill.bill_no,
        "bill_date": _fmt_date(bill.bill_date),
        "patient_no": bill.patient_no or "—",
        "patient_name": bill.patient_name,
        "department_name": bill.short_bill_type_name or "—",
        "doctor_name": bill.doctor_name or "—",
        "lines": [
            {
                "sr": 1,
                "name": bill.service_name,
                "rate": amount,
                "qty": "1",
                "amount": amount,
            }
        ],
        "admin_charges": "0.00",
        "scheme_discount": "0.00",
        "adjust_advance": "0.00",
        "gross_amount": amount,
        "net_amount": amount,
        "payment_mode": "Cash",
        "payments": [],
        "remarks": "",
    }
