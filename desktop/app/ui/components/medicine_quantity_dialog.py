from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
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


def ask_medicine_quantity(medicine: dict, parent: QWidget | None = None) -> dict | None:
    dialog = MedicineQuantityDialog(medicine, parent)
    return dialog.values() if dialog.exec() == QDialog.DialogCode.Accepted else None


class MedicineQuantityDialog(QDialog):
    def __init__(self, medicine: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self._medicine = medicine
        self._values: dict | None = None
        self.setWindowTitle("Enter Quantity")
        self.setMinimumWidth(360)
        self._build_ui()

    def values(self) -> dict | None:
        return self._values

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        code = self._medicine.get("code", "")
        name = self._medicine.get("name", "")
        rate = self._medicine.get("sale_rate") or self._medicine.get("mrp") or 0
        stock = self._medicine.get("stock_qty", "")

        layout.addWidget(QLabel(f"<b>{name}</b>"))
        layout.addWidget(QLabel(f"Code: {code}  |  Rate: {float(rate):.2f}  |  Stock: {stock}"))

        form = QFormLayout()
        self.nos = QLineEdit("1")
        self.factor = QLineEdit("1")
        self.qty = QLineEdit()
        self.qty.setPlaceholderText("Required")
        form.addRow("Nos", self.nos)
        form.addRow("Factor", self.factor)
        form.addRow("Qty", self.qty)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.qty.setFocus()

    def _accept(self) -> None:
        try:
            nos = int(self._parse(self.nos.text(), "Nos"))
            factor = self._parse(self.factor.text(), "Factor")
            qty = int(self._parse(self.qty.text(), "Qty"))
        except ValueError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return
        if nos <= 0 or factor <= 0 or qty <= 0:
            QMessageBox.warning(self, "Validation", "Nos, Factor and Qty must be greater than zero.")
            return
        self._values = {"nos": nos, "factor": float(factor), "qty": qty}
        self.accept()

    @staticmethod
    def _parse(text: str, label: str) -> Decimal:
        value = text.strip()
        if not value:
            raise ValueError(f"{label} is required.")
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid {label}.") from exc
