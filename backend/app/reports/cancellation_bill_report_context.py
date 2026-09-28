from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.cancellation_bill_report import CancellationBillReportRead

_BILL_TYPE_LABELS = {
    "all": "All (OPD / IPD / Pathology)",
    "opd": "OPD",
    "ipd": "IPD",
    "pathology": "Pathology",
}


def build_cancellation_bill_report_context(report: CancellationBillReportRead) -> dict[str, Any]:
    return {
        "report_title": "CANCELLATION BILL DETAILS",
        "bill_type_label": _BILL_TYPE_LABELS.get(report.bill_type, report.bill_type),
        "period_label": (
            f"FROM {_fmt_date(report.from_date)} TO {_fmt_date(report.to_date)}"
        ),
        "rows": [
            {
                "serial_no": row.serial_no,
                "bill_type": row.bill_type,
                "bill_date": _fmt_date(row.bill_date),
                "bill_no": row.bill_no,
                "patient_no": row.patient_no,
                "patient_name": row.patient_name,
                "net_amount": _fmt_money(row.net_amount),
                "cancellation_remarks": row.cancellation_remarks,
                "cancelled_at": (
                    row.cancelled_at.strftime("%d/%m/%Y %H:%M")
                    if row.cancelled_at
                    else "—"
                ),
                "cancelled_by": row.cancelled_by or "—",
            }
            for row in report.rows
        ],
        "grand_total": _fmt_money(report.grand_total),
        "has_rows": bool(report.rows),
    }
