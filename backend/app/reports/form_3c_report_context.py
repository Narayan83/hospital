from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.form_3c_report import Form3CReportRead


def build_form_3c_report_context(report: Form3CReportRead) -> dict[str, Any]:
    return {
        "report_title": "FORM3C REPORT",
        "billing_type_label": report.billing_type_name,
        "period_label": (
            f"FROM {_fmt_date(report.from_date)} TO {_fmt_date(report.to_date)}"
        ),
        "rows": [
            {
                "serial_no": row.serial_no,
                "bill_date": _fmt_date(row.bill_date),
                "bill_no": row.bill_no,
                "payment_mode": row.payment_mode,
                "patient_name": row.patient_name,
                "service_name": row.service_name,
                "total_amount": _fmt_money(row.total_amount),
            }
            for row in report.rows
        ],
        "grand_total": _fmt_money(report.grand_total),
        "has_rows": bool(report.rows),
    }
