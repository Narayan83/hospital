from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def default_sharing_split(total: Decimal, doctor_percent: Decimal) -> tuple[Decimal, Decimal]:
    percent = max(Decimal("0"), min(doctor_percent, Decimal("100")))
    doctor_amount = (total * percent / Decimal("100")).quantize(Decimal("0.01"))
    hospital_amount = total - doctor_amount
    return hospital_amount, doctor_amount


def ask_doctor_sharing_split(
    *,
    service_name: str,
    total_amount: Decimal,
    doctor_percent: Decimal,
    doctor_name: str | None = None,
    parent: QWidget | None = None,
) -> dict[str, Decimal] | None:
    dialog = DoctorSharingSplitDialog(
        service_name=service_name,
        total_amount=total_amount,
        doctor_percent=doctor_percent,
        doctor_name=doctor_name,
        parent=parent,
    )
    return dialog.values() if dialog.exec() == QDialog.DialogCode.Accepted else None


class DoctorSharingSplitDialog(QDialog):
    def __init__(
        self,
        *,
        service_name: str,
        total_amount: Decimal,
        doctor_percent: Decimal,
        doctor_name: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._total_amount = total_amount
        self._values: dict[str, Decimal] | None = None
        hospital, doctor = default_sharing_split(total_amount, doctor_percent)
        self.setWindowTitle("Doctor Sharing Split")
        self.setMinimumWidth(360)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._build_ui(service_name, doctor_name, doctor_percent, hospital, doctor)
        self.raise_()
        self.activateWindow()

    def values(self) -> dict[str, Decimal] | None:
        return self._values

    def _build_ui(
        self,
        service_name: str,
        doctor_name: str | None,
        doctor_percent: Decimal,
        hospital: Decimal,
        doctor: Decimal,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{service_name}</b>"))
        doctor_label = doctor_name or "Doctor"
        layout.addWidget(
            QLabel(
                f"Total: {float(self._total_amount):.2f}  |  "
                f"{doctor_label} share: {float(doctor_percent):.2f}%"
            )
        )
        layout.addWidget(QLabel("Edit hospital and doctor amounts, then press Enter."))

        form = QFormLayout()
        self.hospital_amount = QLineEdit(f"{float(hospital):.2f}")
        self.doctor_amount = QLineEdit(f"{float(doctor):.2f}")
        form.addRow("Hospital Amount", self.hospital_amount)
        form.addRow("Doctor Amount", self.doctor_amount)
        layout.addLayout(form)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._accept)
        layout.addWidget(ok_btn)

        for field in (self.hospital_amount, self.doctor_amount):
            field.returnPressed.connect(self._accept)
        self.hospital_amount.setFocus()

    def _parse_amount(self, field: QLineEdit, label: str) -> Decimal | None:
        text = field.text().strip()
        if not text:
            QMessageBox.warning(self, "Validation", f"{label} is required.")
            return None
        try:
            return Decimal(text).quantize(Decimal("0.01"))
        except InvalidOperation:
            QMessageBox.warning(self, "Validation", f"Invalid {label}.")
            return None

    def _accept(self) -> None:
        hospital = self._parse_amount(self.hospital_amount, "Hospital amount")
        if hospital is None:
            return
        doctor = self._parse_amount(self.doctor_amount, "Doctor amount")
        if doctor is None:
            return
        if hospital < 0 or doctor < 0:
            QMessageBox.warning(self, "Validation", "Amounts cannot be negative.")
            return
        if hospital + doctor <= 0:
            QMessageBox.warning(self, "Validation", "Total amount must be greater than zero.")
            return
        self._values = {
            "hospital_amount": hospital,
            "doctor_amount": doctor,
        }
        self.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept()
            return
        super().keyPressEvent(event)
