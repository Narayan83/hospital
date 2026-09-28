from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.doctor_collection_report import (
    DoctorCollectionColumnReportRead,
    DoctorCollectionDateServiceReportRead,
    DoctorCollectionPaymentModeReportRead,
    DoctorCollectionReportRead,
)


def build_doctor_collection_report_context(
    report: (
        DoctorCollectionReportRead
        | DoctorCollectionColumnReportRead
        | DoctorCollectionPaymentModeReportRead
        | DoctorCollectionDateServiceReportRead
    ),
) -> dict[str, Any]:
    if isinstance(report, DoctorCollectionColumnReportRead):
        return _build_column_context(report)
    if isinstance(report, DoctorCollectionPaymentModeReportRead):
        return _build_payment_mode_context(report)
    if isinstance(report, DoctorCollectionDateServiceReportRead):
        return _build_date_service_context(report)
    return _build_normal_context(report)


def _build_normal_context(report: DoctorCollectionReportRead) -> dict[str, Any]:
    doctors: list[dict[str, Any]] = []
    for doctor_group in report.doctors:
        date_groups: list[dict[str, Any]] = []
        for date_group in doctor_group.date_groups:
            date_groups.append(
                {
                    "bill_date": _fmt_date(date_group.bill_date),
                    "rows": [
                        {
                            "bill_type": row.bill_type,
                            "bill_no": row.bill_no,
                            "patient_no": row.patient_no,
                            "payment_mode": row.payment_mode,
                            "service_name": row.service_name,
                            "original_rate": _fmt_money(row.original_rate),
                            "hospital_amount": _fmt_money(row.hospital_amount),
                            "doctor_amount": _fmt_money(row.doctor_amount),
                            "total_amount": _fmt_money(row.total_amount),
                        }
                        for row in date_group.rows
                    ],
                    "total_amount": _fmt_money(date_group.total_amount),
                    "hospital_amount": _fmt_money(date_group.hospital_amount),
                    "doctor_amount": _fmt_money(date_group.doctor_amount),
                }
            )
        doctors.append(
            {
                "doctor_name": doctor_group.doctor_name,
                "date_groups": date_groups,
                "service_summary": [
                    {
                        "service_name": row.service_name,
                        "total_amount": _fmt_money(row.total_amount),
                        "hospital_amount": _fmt_money(row.hospital_amount),
                        "doctor_amount": _fmt_money(row.doctor_amount),
                    }
                    for row in doctor_group.service_summary
                ],
                "grand_total_amount": _fmt_money(doctor_group.grand_total_amount),
                "grand_hospital_amount": _fmt_money(doctor_group.grand_hospital_amount),
                "grand_doctor_amount": _fmt_money(doctor_group.grand_doctor_amount),
            }
        )

    titles = {
        "day_wise_summary": "Doctor wise Day wise Collection Summary",
        "sharing": "Doctor wise Sharing Report",
        "normal": "Doctor wise Sharing Report",
    }
    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    return {
        "report_title": titles.get(report.report_type, "Doctor wise Collection Report"),
        "report_type": report.report_type,
        "period_label": period_label,
        "doctors": doctors,
        "date_groups": [],
        "service_columns": [],
        "payment_modes": [],
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_hospital_amount": _fmt_money(report.overall_hospital_amount),
        "overall_doctor_amount": _fmt_money(report.overall_doctor_amount),
        "overall_column_totals": {},
        "has_rows": bool(report.doctors),
        "summary_only": report.report_type == "day_wise_summary",
    }


def _build_payment_mode_context(report: DoctorCollectionPaymentModeReportRead) -> dict[str, Any]:
    payment_modes: list[dict[str, Any]] = []
    for mode_group in report.payment_modes:
        payment_modes.append(
            {
                "payment_mode": mode_group.payment_mode,
                "doctors": [
                    {
                        "doctor_name": row.doctor_name,
                        "hospital_amount": _fmt_money(row.hospital_amount),
                        "doctor_amount": _fmt_money(row.doctor_amount),
                        "total_amount": _fmt_money(row.total_amount),
                    }
                    for row in mode_group.doctors
                ],
                "hospital_amount": _fmt_money(mode_group.hospital_amount),
                "doctor_amount": _fmt_money(mode_group.doctor_amount),
                "total_amount": _fmt_money(mode_group.total_amount),
            }
        )
    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    return {
        "report_title": "Payment Mode wise Doctor Collection Summary",
        "report_type": "payment_mode_summary",
        "period_label": period_label,
        "doctors": [],
        "date_groups": [],
        "service_columns": [],
        "payment_modes": payment_modes,
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_hospital_amount": _fmt_money(report.overall_hospital_amount),
        "overall_doctor_amount": _fmt_money(report.overall_doctor_amount),
        "overall_column_totals": {},
        "has_rows": bool(report.payment_modes),
    }


def _build_column_context(report: DoctorCollectionColumnReportRead) -> dict[str, Any]:
    service_columns = [
        {"service_id": col.service_id, "service_name": col.service_name}
        for col in report.service_columns
    ]
    doctors: list[dict[str, Any]] = []
    for doctor_group in report.doctors:
        doctors.append(
            {
                "doctor_name": doctor_group.doctor_name,
                "rows": [
                    {
                        "bill_date": _fmt_date(row.bill_date),
                        "bill_type": row.bill_type,
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
                    for row in doctor_group.rows
                ],
                "column_totals": {
                    service_id: _fmt_money(amount)
                    for service_id, amount in doctor_group.column_totals.items()
                },
                "grand_total_amount": _fmt_money(doctor_group.grand_total_amount),
            }
        )

    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    return {
        "report_title": "Doctor wise Collection Report (Column wise)",
        "report_type": "column_wise",
        "period_label": period_label,
        "doctors": doctors,
        "date_groups": [],
        "service_columns": service_columns,
        "payment_modes": [],
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_hospital_amount": "",
        "overall_doctor_amount": "",
        "overall_column_totals": {
            service_id: _fmt_money(amount)
            for service_id, amount in report.overall_column_totals.items()
        },
        "has_rows": bool(report.doctors),
        "has_service_columns": bool(service_columns),
    }


def _build_date_service_context(report: DoctorCollectionDateServiceReportRead) -> dict[str, Any]:
    date_groups: list[dict[str, Any]] = []
    for date_group in report.date_groups:
        date_groups.append(
            {
                "bill_date": _fmt_date(date_group.bill_date),
                "services": [
                    {
                        "service_name": svc.service_name,
                        "rows": [
                            {
                                "bill_type": row.bill_type,
                                "bill_no": row.bill_no,
                                "patient_no": row.patient_no,
                                "payment_mode": row.payment_mode,
                                "service_name": row.service_name,
                                "original_rate": _fmt_money(row.original_rate),
                                "hospital_amount": _fmt_money(row.hospital_amount),
                                "doctor_amount": _fmt_money(row.doctor_amount),
                                "total_amount": _fmt_money(row.total_amount),
                            }
                            for row in svc.rows
                        ],
                        "hospital_amount": _fmt_money(svc.hospital_amount),
                        "doctor_amount": _fmt_money(svc.doctor_amount),
                        "total_amount": _fmt_money(svc.total_amount),
                    }
                    for svc in date_group.services
                ],
                "hospital_amount": _fmt_money(date_group.hospital_amount),
                "doctor_amount": _fmt_money(date_group.doctor_amount),
                "total_amount": _fmt_money(date_group.total_amount),
            }
        )
    titles = {
        "date_service_summary": "Date wise Service wise Collection Summary",
        "date_service_details": "Date wise Service wise Collection Details",
    }
    period_label = f"From {_fmt_date(report.from_date)} — To {_fmt_date(report.to_date)}"
    return {
        "report_title": titles.get(report.report_type, "Date wise Service wise Collection"),
        "report_type": report.report_type,
        "period_label": period_label,
        "doctors": [],
        "date_groups": date_groups,
        "service_columns": [],
        "payment_modes": [],
        "overall_total_amount": _fmt_money(report.overall_total_amount),
        "overall_hospital_amount": _fmt_money(report.overall_hospital_amount),
        "overall_doctor_amount": _fmt_money(report.overall_doctor_amount),
        "overall_column_totals": {},
        "has_rows": bool(report.date_groups),
        "summary_only": report.report_type == "date_service_summary",
    }
