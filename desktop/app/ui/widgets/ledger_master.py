from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError

LEDGER_TYPES = [
    ("ASSET", "Asset"),
    ("LIABILITY", "Liability"),
    ("INCOME", "Income"),
    ("EXPENSE", "Expense"),
]


class LedgerMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Ledger Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)

        self.ledger_combo = QComboBox()
        self.ledger_combo.setEnabled(False)
        self.ledger_combo.currentIndexChanged.connect(self._on_ledger_selected)
        top.addWidget(QLabel("Select Ledger"))
        top.addWidget(self.ledger_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Ledger")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. CASH")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Cash Account")

        self.ledger_type = QComboBox()
        for value, label in LEDGER_TYPES:
            self.ledger_type.addItem(label, value)

        self.opening_balance = QDoubleSpinBox()
        self.opening_balance.setRange(0, 999_999_999.99)
        self.opening_balance.setDecimals(2)
        self.opening_balance.setMaximumWidth(160)

        flags = QHBoxLayout()
        self.is_cash = QCheckBox("Is Cash")
        self.is_bank = QCheckBox("Is Bank")
        self.is_patient_deposit = QCheckBox("Is Patient Deposit")
        self.is_cash.toggled.connect(self._on_cash_toggled)
        self.is_bank.toggled.connect(self._on_bank_toggled)
        flags.addWidget(self.is_cash)
        flags.addWidget(self.is_bank)
        flags.addWidget(self.is_patient_deposit)
        flags.addStretch()

        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Type *", self.ledger_type)
        form.addRow("Opening Balance", self.opening_balance)
        form.addRow("Flags", flags)
        layout.addWidget(form_box)

        hint = QLabel(
            "Opening balance is absolute. Asset/Expense open on Debit; "
            "Liability/Income open on Credit. Cash and Bank cannot both be set."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Code", "Name", "Type", "Opening", "Flags", ""]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def _on_cash_toggled(self, checked: bool) -> None:
        if checked and self.is_bank.isChecked():
            self.is_bank.blockSignals(True)
            self.is_bank.setChecked(False)
            self.is_bank.blockSignals(False)

    def _on_bank_toggled(self, checked: bool) -> None:
        if checked and self.is_cash.isChecked():
            self.is_cash.blockSignals(True)
            self.is_cash.setChecked(False)
            self.is_cash.blockSignals(False)

    def refresh(self) -> None:
        try:
            self._items = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._load_table()
        self._load_ledger_combo()

    def _flag_label(self, item: dict) -> str:
        parts: list[str] = []
        if item.get("is_cash"):
            parts.append("Cash")
        if item.get("is_bank"):
            parts.append("Bank")
        if item.get("is_patient_deposit"):
            parts.append("Deposit")
        return ", ".join(parts) if parts else "—"

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("ledger_type", "")))
            opening = item.get("opening_balance") or 0
            try:
                opening_text = f"{float(opening):,.2f}"
            except (TypeError, ValueError):
                opening_text = str(opening)
            self.table.setItem(row, 3, QTableWidgetItem(opening_text))
            self.table.setItem(row, 4, QTableWidgetItem(self._flag_label(item)))
            id_item = QTableWidgetItem(item.get("id") or "")
            self.table.setItem(row, 5, id_item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_ledger_combo(self) -> None:
        current = self.ledger_combo.currentData()
        self.ledger_combo.clear()
        self.ledger_combo.addItem("— Select —", None)
        for item in self._items:
            self.ledger_combo.addItem(
                f"{item.get('code')} — {item.get('name')}",
                item.get("id"),
            )
        if current:
            idx = self.ledger_combo.findData(current)
            if idx >= 0:
                self.ledger_combo.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.ledger_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        editable = not is_delete
        self.name.setEnabled(editable)
        self.ledger_type.setEnabled(editable)
        self.opening_balance.setEnabled(editable)
        self.is_cash.setEnabled(editable)
        self.is_bank.setEnabled(editable)
        self.is_patient_deposit.setEnabled(editable)
        if is_create:
            self._clear_form()

    def _on_ledger_selected(self) -> None:
        ledger_id = self.ledger_combo.currentData()
        if ledger_id:
            self._load_item(ledger_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        ledger_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and ledger_id:
            idx = self.ledger_combo.findData(ledger_id)
            if idx >= 0:
                self.ledger_combo.setCurrentIndex(idx)

    def _set_type(self, ledger_type: str | None) -> None:
        value = (ledger_type or "ASSET").upper()
        idx = self.ledger_type.findData(value)
        self.ledger_type.setCurrentIndex(idx if idx >= 0 else 0)

    def _load_item(self, ledger_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == ledger_id), None)
        if not item:
            try:
                item = self.api.get_ledger(ledger_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = ledger_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self._set_type(item.get("ledger_type"))
        try:
            self.opening_balance.setValue(float(item.get("opening_balance") or 0))
        except (TypeError, ValueError):
            self.opening_balance.setValue(0)
        self.is_cash.setChecked(bool(item.get("is_cash")))
        self.is_bank.setChecked(bool(item.get("is_bank")))
        self.is_patient_deposit.setChecked(bool(item.get("is_patient_deposit")))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self._set_type("ASSET")
        self.opening_balance.setValue(0)
        self.is_cash.setChecked(False)
        self.is_bank.setChecked(False)
        self.is_patient_deposit.setChecked(False)
        self.ledger_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _payload(self) -> dict:
        return {
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "ledger_type": self.ledger_type.currentData() or "ASSET",
            "opening_balance": round(self.opening_balance.value(), 2),
            "is_cash": self.is_cash.isChecked(),
            "is_bank": self.is_bank.isChecked(),
            "is_patient_deposit": self.is_patient_deposit.isChecked(),
        }

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            ledger_id = self.ledger_combo.currentData() or self._selected_id
            if not ledger_id:
                QMessageBox.warning(self, "Validation", "Select a ledger to delete.")
                return
            if (
                QMessageBox.question(self, "Confirm", "Deactivate this ledger?")
                != QMessageBox.StandardButton.Yes
            ):
                return
            try:
                self.api.delete_ledger(ledger_id)
                QMessageBox.information(self, "Success", "Ledger deactivated.")
                self._clear_form()
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        payload = self._payload()
        if not payload["code"] or not payload["name"]:
            QMessageBox.warning(self, "Validation", "Code and name are required.")
            return
        if payload["is_cash"] and payload["is_bank"]:
            QMessageBox.warning(self, "Validation", "A ledger cannot be both Cash and Bank.")
            return

        try:
            if mode == self.MODE_CREATE:
                self.api.create_ledger(payload)
                QMessageBox.information(self, "Success", "Ledger created.")
                self._clear_form()
            else:
                ledger_id = self.ledger_combo.currentData() or self._selected_id
                if not ledger_id:
                    QMessageBox.warning(self, "Validation", "Select a ledger to modify.")
                    return
                update_payload = {k: v for k, v in payload.items() if k != "code"}
                self.api.update_ledger(ledger_id, update_payload)
                QMessageBox.information(self, "Success", "Ledger updated.")
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
