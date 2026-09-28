from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.modification_bill_report import ModificationBillReportRead

_BILL_TYPE_LABELS = {
    "all": "All (OPD / IPD / Pathology)",
    "opd": "OPD",
    "ipd": "IPD",
    "pathology": "Pathology",
}


def build_modification_bill_report_context(report: ModificationBillReportRead) -> dict[str, Any]:
    return {
        "report_title": "MODIFICATION BILL DETAILS",
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
                "modified_at": (
                    row.modified_at.strftime("%d/%m/%Y %H:%M")
                    if row.modified_at
                    else "—"
                ),
                "modified_by": row.modified_by or "—",
            }
            for row in report.rows
        ],
        "grand_total": _fmt_money(report.grand_total),
        "has_rows": bool(report.rows),
    }
