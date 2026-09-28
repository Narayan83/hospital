from __future__ import annotations

from decimal import Decimal

from app.reports.bill_context import _fmt_date
from app.schemas.accounting_voucher import AdvanceCollectionRead


def _fmt_amount(value) -> str:
    try:
        return f"{Decimal(str(value or 0)):,.2f}"
    except Exception:
        return "0.00"


def build_advance_receipt_context(
    advance: AdvanceCollectionRead,
    *,
    balance_after=None,
) -> dict:
    payment_mode = " — ".join(
        p for p in (advance.payment_mode_code, advance.payment_mode_name) if p
    ) or "—"

    return {
        "bill_title": "Advance Receipt",
        "voucher_no": advance.voucher_no or "",
        "voucher_date": _fmt_date(advance.voucher_date),
        "patient_no": advance.patient_no or "",
        "patient_name": advance.patient_name or "",
        "amount": _fmt_amount(advance.amount),
        "payment_mode": payment_mode,
        "narration": (advance.narration or "").strip(),
        "balance_after": _fmt_amount(
            balance_after if balance_after is not None else advance.amount
        ),
    }
