from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


class ContraEntryWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._ledgers: list[dict] = []
        self._build_ui()

    @staticmethod
    def _wide(widget: QWidget) -> QWidget:
        widget.setProperty("hmsAllowWide", True)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumWidth(280)
        return widget

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Contra Entry")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Transfer amount between cash and bank ledgers. Amount is debited to the To ledger "
            "and credited from the From ledger."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Contra")
        form = QFormLayout(form_box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setProperty("hmsResponsive", True)

        self.voucher_date = QDateEdit()
        self.voucher_date.setCalendarPopup(True)
        self.voucher_date.setDisplayFormat("dd-MM-yyyy")
        self.voucher_date.setDate(QDate.currentDate())
        self._wide(self.voucher_date)
        form.addRow("Date *", self.voucher_date)

        self.from_ledger = QComboBox()
        self._wide(self.from_ledger)
        form.addRow("From Ledger *", self.from_ledger)

        self.to_ledger = QComboBox()
        self._wide(self.to_ledger)
        form.addRow("To Ledger *", self.to_ledger)

        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self._wide(self.amount)
        form.addRow("Amount *", self.amount)

        self.narration = QLineEdit()
        self.narration.setPlaceholderText("Optional narration")
        self._wide(self.narration)
        form.addRow("Narration", self.narration)

        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Contra")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self._wide(self.status)
        layout.addWidget(self.status)
        layout.addStretch()

    def refresh(self) -> None:
        try:
            self._ledgers = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        cash_bank = [
            ledger
            for ledger in self._ledgers
            if ledger.get("is_cash") or ledger.get("is_bank")
        ]
        from_id = self.from_ledger.currentData()
        to_id = self.to_ledger.currentData()
        self.from_ledger.clear()
        self.to_ledger.clear()
        for ledger in cash_bank:
            label = f"{ledger.get('code')} — {ledger.get('name')}"
            self.from_ledger.addItem(label, ledger.get("id"))
            self.to_ledger.addItem(label, ledger.get("id"))
        if from_id:
            idx = self.from_ledger.findData(from_id)
            if idx >= 0:
                self.from_ledger.setCurrentIndex(idx)
        if to_id:
            idx = self.to_ledger.findData(to_id)
            if idx >= 0:
                self.to_ledger.setCurrentIndex(idx)

    def _clear(self) -> None:
        self.amount.clear()
        self.narration.clear()
        self.status.clear()
        self.voucher_date.setDate(QDate.currentDate())

    def _save(self) -> None:
        from_id = self.from_ledger.currentData()
        to_id = self.to_ledger.currentData()
        if not from_id or not to_id:
            QMessageBox.warning(self, "Validation", "Select both ledgers.")
            return
        if from_id == to_id:
            QMessageBox.warning(self, "Validation", "From and To ledgers must be different.")
            return
        try:
            amount = Decimal(self.amount.text().strip() or "0")
        except Exception:
            QMessageBox.warning(self, "Validation", "Enter a valid amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Amount must be greater than zero.")
            return

        qd = self.voucher_date.date()
        payload = {
            "voucher_date": date(qd.year(), qd.month(), qd.day()).isoformat(),
            "from_ledger_id": from_id,
            "to_ledger_id": to_id,
            "amount": str(amount),
            "narration": self.narration.text().strip() or None,
        }
        try:
            result = self.api.create_contra_entry(payload)
            QMessageBox.information(self, "Success", f"Contra saved: {result.get('voucher_no', '')}")
            self.status.setText(f"Saved {result.get('voucher_no', '')}")
            self.amount.clear()
            self.narration.clear()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
