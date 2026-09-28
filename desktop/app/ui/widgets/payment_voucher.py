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
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.components.patient_search_dialog import pick_patient


class PaymentVoucherWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._patient: dict | None = None
        self._ledgers: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Payment / Adjustment Entry")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Post a receipt or payment between two ledgers. When the ledger is a patient deposit "
            "ledger, select the patient so the advance balance is updated."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Voucher")
        form = QFormLayout(form_box)

        self.entry_type = QComboBox()
        self.entry_type.addItem("Receipt", "receipt")
        self.entry_type.addItem("Payment", "payment")
        form.addRow("Entry Type *", self.entry_type)

        self.voucher_date = QDateEdit()
        self.voucher_date.setCalendarPopup(True)
        self.voucher_date.setDate(QDate.currentDate())
        form.addRow("Date *", self.voucher_date)

        self.ledger_combo = QComboBox()
        self.ledger_combo.currentIndexChanged.connect(self._on_ledger_changed)
        form.addRow("Ledger *", self.ledger_combo)

        self.counter_ledger_combo = QComboBox()
        form.addRow("Cash / Bank Ledger *", self.counter_ledger_combo)

        patient_row = QHBoxLayout()
        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Optional — required for deposit ledger")
        self.patient_no.returnPressed.connect(self._load_patient)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._load_patient)
        pick_btn = QPushButton("Pick")
        pick_btn.clicked.connect(self._pick_patient)
        patient_row.addWidget(self.patient_no, stretch=1)
        patient_row.addWidget(search_btn)
        patient_row.addWidget(pick_btn)
        form.addRow("Patient Id", patient_row)

        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        form.addRow("Patient Name", self.patient_name)

        self.deposit_balance = QLineEdit("0.00")
        self.deposit_balance.setReadOnly(True)
        form.addRow("Advance Balance", self.deposit_balance)

        self.amount = QLineEdit()
        form.addRow("Amount *", self.amount)

        self.narration = QLineEdit()
        form.addRow("Narration", self.narration)

        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Entry")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def refresh(self) -> None:
        try:
            self._ledgers = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        ledger_id = self.ledger_combo.currentData()
        counter_id = self.counter_ledger_combo.currentData()
        self.ledger_combo.clear()
        self.counter_ledger_combo.clear()
        for ledger in self._ledgers:
            label = f"{ledger.get('code')} — {ledger.get('name')}"
            self.ledger_combo.addItem(label, ledger.get("id"))
            if ledger.get("is_cash") or ledger.get("is_bank"):
                self.counter_ledger_combo.addItem(label, ledger.get("id"))
        if ledger_id:
            idx = self.ledger_combo.findData(ledger_id)
            if idx >= 0:
                self.ledger_combo.setCurrentIndex(idx)
        if counter_id:
            idx = self.counter_ledger_combo.findData(counter_id)
            if idx >= 0:
                self.counter_ledger_combo.setCurrentIndex(idx)

    def _current_ledger(self) -> dict | None:
        ledger_id = self.ledger_combo.currentData()
        return next((item for item in self._ledgers if item.get("id") == ledger_id), None)

    def _on_ledger_changed(self) -> None:
        ledger = self._current_ledger()
        if ledger and ledger.get("is_patient_deposit"):
            self.patient_no.setPlaceholderText("Required for patient deposit ledger")
        else:
            self.patient_no.setPlaceholderText("Optional")

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, self)
        if patient:
            self._apply_patient(patient)

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_no.setText(patient.get("patient_no") or "")
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self._refresh_deposit_balance()

    def _load_patient(self) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            self._patient = None
            self.patient_name.clear()
            self.deposit_balance.setText("0.00")
            return
        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                QMessageBox.warning(self, "Patient", f"No patient found: {patient_no}")
                return
            self._apply_patient(items[0])
        except ApiError as exc:
            QMessageBox.warning(self, "Patient", str(exc))

    def _refresh_deposit_balance(self) -> None:
        if not self._patient:
            self.deposit_balance.setText("0.00")
            return
        try:
            data = self.api.get_patient_deposit_balance(patient_id=self._patient.get("id"))
            self.deposit_balance.setText(f"{float(data.get('balance', 0)):,.2f}")
        except ApiError:
            self.deposit_balance.setText("0.00")

    def _clear(self) -> None:
        self._patient = None
        self.patient_no.clear()
        self.patient_name.clear()
        self.deposit_balance.setText("0.00")
        self.amount.clear()
        self.narration.clear()
        self.status.clear()
        self.voucher_date.setDate(QDate.currentDate())

    def _save(self) -> None:
        ledger_id = self.ledger_combo.currentData()
        counter_id = self.counter_ledger_combo.currentData()
        if not ledger_id or not counter_id:
            QMessageBox.warning(self, "Validation", "Select ledger and cash/bank ledger.")
            return
        ledger = self._current_ledger()
        if ledger and ledger.get("is_patient_deposit") and not self._patient:
            QMessageBox.warning(self, "Validation", "Patient is required for deposit ledger.")
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
            "ledger_id": ledger_id,
            "counter_ledger_id": counter_id,
            "patient_id": self._patient.get("id") if self._patient else None,
            "amount": str(amount),
            "entry_type": self.entry_type.currentData(),
            "narration": self.narration.text().strip() or None,
        }
        try:
            result = self.api.create_payment_voucher(payload)
            QMessageBox.information(self, "Success", f"Voucher saved: {result.get('voucher_no', '')}")
            self.status.setText(f"Saved {result.get('voucher_no', '')}")
            self.amount.clear()
            self.narration.clear()
            if self._patient:
                self._refresh_deposit_balance()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
