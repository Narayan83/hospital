from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.pathology_collection_report import (
    PathologyCollectionColumnReportRead,
    PathologyCollectionReportRead,
)


def build_pathology_collection_report_context(
    report: PathologyCollectionReportRead | PathologyCollectionColumnReportRead,
) -> dict[str, Any]:
    if isinstance(report, PathologyCollectionColumnReportRead):
        return _build_column_context(report)
    return _build_normal_context(report)


def _build_normal_context(report: PathologyCollectionReportRead) -> dict[str, Any]:
    is_referral = report.report_type == "referral_wise"
    groups: list[dict[str, Any]] = []
    for group in report.groups:
        date_groups: list[dict[str, Any]] = []
        for date_group in group.date_groups:
            date_groups.append(
                {
                    "bill_date": _fmt_date(date_group.bill_date),
                    "rows": [
                        {
                            "bill_no": row.bill_no,
                            "patient_no": row.patient_no,
                            "patient_name": row.patient_name,
                            "payment_mode": row.payment_mode,
                            "pathologist_name": row.pathologist_name,
                            "referring_doctor": row.referring_doctor,
                            "service_name": row.service_name,
                            "rate": _fmt_money(row.rate),
                            "amount": _fmt_money(row.amount),
                        }
                        for row in date_group.rows
                    ],
                    "total_amount": _fmt_money(date_group.total_amount),
                }
            )
        groups.append(
            {
                "group_name": group.group_name,
                "date_groups": date_groups,
                "service_summary": [
                    {
                        "service_name": row.service_name,
                        "total_amount": _fmt_money(row.total_amount),
                    }
                    for row in group.service_summary
                ],
                "grand_total_amount": _fmt_money(group.grand_total_amount),
            }
        )

    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    title = (
        "Pathology Reference Doctor wise Collection Report"
        if is_referral
        else "Pathology Doctor wise Collection Report"
    )
    group_label = "Reference Doctor" if is_referral else "Pathologist"
    return {
        "report_title": title,
        "report_type": report.report_type,
        "group_label": group_label,
        "is_referral": is_referral,
        "period_label": period_label,
        "groups": groups,
        "service_columns": [],
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_column_totals": {},
        "has_rows": bool(report.groups),
    }


def _build_column_context(report: PathologyCollectionColumnReportRead) -> dict[str, Any]:
    service_columns = [
        {"service_id": col.service_id, "service_name": col.service_name}
        for col in report.service_columns
    ]
    groups: list[dict[str, Any]] = []
    for group in report.groups:
        groups.append(
            {
                "group_name": group.group_name,
                "rows": [
                    {
                        "bill_date": _fmt_date(row.bill_date),
                        "bill_no": row.bill_no,
                        "patient_no": row.patient_no,
                        "patient_name": row.patient_name,
                        "payment_mode": row.payment_mode,
                        "amounts": {
                            service_id: (_fmt_money(amount) if amount else "")
                            for service_id, amount in row.amounts.items()
                        },
                        "total_amount": _fmt_money(row.total_amount),
                    }
                    for row in group.rows
                ],
                "column_totals": {
                    service_id: _fmt_money(amount)
                    for service_id, amount in group.column_totals.items()
                },
                "grand_total_amount": _fmt_money(group.grand_total_amount),
            }
        )

    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    return {
        "report_title": "Pathology Doctor wise Collection Report (Column wise)",
        "report_type": "column_wise",
        "group_label": "Pathologist",
        "is_referral": False,
        "period_label": period_label,
        "groups": groups,
        "service_columns": service_columns,
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_column_totals": {
            service_id: _fmt_money(amount)
            for service_id, amount in report.overall_column_totals.items()
        },
        "has_rows": bool(report.groups),
        "has_service_columns": bool(service_columns),
    }
