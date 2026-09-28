from decimal import Decimal
from typing import Any

from app.reports.bill_context import _fmt_date, _fmt_money
from app.schemas.user_cash_transaction_report import UserCashTransactionReportRead


def _fmt_signed(value: Any, is_debit: bool) -> str:
    amount = Decimal(str(value or 0))
    if is_debit and amount > 0:
        amount = -amount
    return f"{amount:.2f}"


def build_user_cash_transaction_report_context(
    report: UserCashTransactionReportRead,
) -> dict[str, Any]:
    bill_type_groups: list[dict[str, Any]] = []
    for bill_group in report.bill_type_groups:
        payment_groups: list[dict[str, Any]] = []
        for payment_group in bill_group.payment_groups:
            payment_groups.append(
                {
                    "payment_mode_name": payment_group.payment_mode_name,
                    "rows": [
                        {
                            "bill_no": row.bill_no,
                            "patient_no": row.patient_no,
                            "patient_name": row.patient_name,
                            "amount": _fmt_signed(row.amount, row.is_debit),
                            "bill_date": _fmt_date(row.bill_date) if row.bill_date else "",
                        }
                        for row in payment_group.rows
                    ],
                    "subtotal": _fmt_signed(payment_group.subtotal, bill_group.is_debit),
                }
            )
        bill_type_groups.append(
            {
                "bill_type": bill_group.bill_type,
                "payment_groups": payment_groups,
                "grand_total": _fmt_signed(bill_group.grand_total, bill_group.is_debit),
                "is_debit": bill_group.is_debit,
            }
        )

    day_groups: list[dict[str, Any]] = []
    for day in report.day_groups:
        users = []
        for user in day.users:
            users.append(
                {
                    "user_name": user.user_name,
                    "bill_type_totals": {
                        key: _fmt_money(value) for key, value in user.bill_type_totals.items()
                    },
                    "payment_mode_totals": {
                        key: _fmt_money(value) for key, value in user.payment_mode_totals.items()
                    },
                    "day_total": _fmt_money(user.day_total),
                }
            )
        day_groups.append(
            {
                "bill_date": _fmt_date(day.bill_date),
                "users": users,
                "day_total": _fmt_money(day.day_total),
            }
        )

    period_parts: list[str] = []
    if report.from_date:
        period_parts.append(f"From {_fmt_date(report.from_date)}")
    if report.to_date:
        period_parts.append(f"To {_fmt_date(report.to_date)}")
    period_label = " — ".join(period_parts) if period_parts else "All dates"

    title = "User wise Cash Transaction Report"
    if report.report_type == "day_wise":
        title = "User wise Day wise Collection Report"

    return {
        "report_title": title,
        "user_name": report.user_name,
        "period_label": period_label,
        "payment_mode_label": report.payment_mode_label,
        "report_type": report.report_type,
        "bill_type_groups": bill_type_groups,
        "day_groups": day_groups,
        "bill_collection_total": _fmt_money(report.bill_collection_total),
        "advance_collection_total": _fmt_money(report.advance_collection_total),
        "payment_debit_total": _fmt_signed(report.payment_debit_total, True),
        "overall_grand_total": _fmt_money(report.overall_grand_total),
        "has_rows": bool(report.day_groups)
        or any(
            payment_group.rows
            for bill_group in report.bill_type_groups
            for payment_group in bill_group.payment_groups
        ),
    }
