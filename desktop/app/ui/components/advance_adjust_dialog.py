from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


def prompt_advance_adjust(
    parent: QWidget | None,
    *,
    available: Decimal | float | int | str,
    current: Decimal | float | int | str = 0,
    title: str = "Adjust Advance",
) -> Decimal | None:
    """Ask for an advance amount using a plain text field (avoids QDoubleSpinBox input bugs).

    Returns the chosen amount, or None if cancelled / unavailable.
    """
    try:
        available_amt = Decimal(str(available or 0))
    except (InvalidOperation, ValueError, TypeError):
        available_amt = Decimal("0")
    try:
        current_amt = Decimal(str(current or 0))
    except (InvalidOperation, ValueError, TypeError):
        current_amt = Decimal("0")

    if available_amt <= 0:
        QMessageBox.information(
            parent,
            title,
            "No advance balance is available for this patient.\n\n"
            "Collect advance first (Collect Advance), then try Adjust Advance again.",
        )
        return None

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(360)
    layout = QVBoxLayout(dialog)

    hint = QLabel(
        f"Available advance: {available_amt:,.2f}\n"
        "Enter the amount to adjust against this bill."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #475569;")
    layout.addWidget(hint)

    form = QFormLayout()
    amount_edit = QLineEdit()
    initial = min(max(current_amt, Decimal("0")), available_amt)
    amount_edit.setText(f"{initial:.2f}" if initial > 0 else "")
    amount_edit.setPlaceholderText("0.00")
    amount_edit.selectAll()
    form.addRow("Amount", amount_edit)
    layout.addLayout(form)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    amount_edit.setFocus()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    raw = amount_edit.text().strip().replace(",", "")
    if not raw:
        return Decimal("0")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        QMessageBox.warning(parent, title, "Enter a valid amount.")
        return None
    if amount < 0:
        QMessageBox.warning(parent, title, "Amount cannot be negative.")
        return None
    if amount > available_amt:
        QMessageBox.warning(
            parent,
            title,
            f"Amount cannot exceed available advance ({available_amt:,.2f}).",
        )
        return None
    return amount.quantize(Decimal("0.01"))
