from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_payment_modes_cache
from app.session import get_session


class PaymentModeMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._ledgers: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Payment Mode Creation")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        self.mode_select = QComboBox()
        self.mode_select.setEnabled(False)
        self.mode_select.currentIndexChanged.connect(self._on_mode_selected)
        top.addWidget(QLabel("Select Mode"))
        top.addWidget(self.mode_select, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Payment Mode")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. CASH")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Cash")
        self.is_cash = QCheckBox("Cash payment (for billing cash tracking)")
        self.ledger = QComboBox()
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("", self.is_cash)
        form.addRow("Post to Ledger *", self.ledger)
        ledger_hint = QLabel("Bill payments post to this ledger in cashbook.")
        ledger_hint.setStyleSheet("color: #64748b; font-size: 10px;")
        form.addRow("", ledger_hint)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Ledger", "Cash?", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._ledgers = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            self._ledgers = []
        self._load_ledger_combo()
        cache = get_session().cache
        if cache.loaded:
            self._items = list(cache.payment_modes)
        else:
            try:
                self._items = self.api.list_payment_modes()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._load_table()
        self._load_mode_combo()

    def _load_ledger_combo(self) -> None:
        current = self.ledger.currentData()
        self.ledger.clear()
        self.ledger.addItem("— No Ledger —", None)
        for item in self._ledgers:
            self.ledger.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))
        if current:
            idx = self.ledger.findData(current)
            if idx >= 0:
                self.ledger.setCurrentIndex(idx)

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            ledger_label = item.get("ledger_code") or item.get("ledger_name") or ""
            self.table.setItem(row, 2, QTableWidgetItem(ledger_label))
            self.table.setItem(row, 3, QTableWidgetItem("Yes" if item.get("is_cash") else "No"))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_mode_combo(self) -> None:
        current = self.mode_select.currentData()
        self.mode_select.clear()
        self.mode_select.addItem("— Select —", None)
        for item in self._items:
            self.mode_select.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))
        if current:
            idx = self.mode_select.findData(current)
            if idx >= 0:
                self.mode_select.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.mode_select.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        self.name.setEnabled(enabled)
        self.is_cash.setEnabled(enabled)
        self.ledger.setEnabled(enabled)
        self.sort_order.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_mode_selected(self) -> None:
        mode_id = self.mode_select.currentData()
        if mode_id:
            self._load_item(mode_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        mode_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and mode_id:
            idx = self.mode_select.findData(mode_id)
            if idx >= 0:
                self.mode_select.setCurrentIndex(idx)

    def _load_item(self, mode_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == mode_id), None)
        if not item:
            try:
                item = self.api.get_payment_mode(mode_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = mode_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.is_cash.setChecked(bool(item.get("is_cash")))
        if item.get("ledger_id"):
            idx = self.ledger.findData(item.get("ledger_id"))
            if idx >= 0:
                self.ledger.setCurrentIndex(idx)
        else:
            self.ledger.setCurrentIndex(0)
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.is_cash.setChecked(False)
        self.ledger.setCurrentIndex(0)
        self.sort_order.setValue(0)
        self.mode_select.setCurrentIndex(0)
        self.table.clearSelection()

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            mode_id = self.mode_select.currentData() or self._selected_id
            if not mode_id:
                QMessageBox.warning(self, "Validation", "Select a payment mode to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this payment mode?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_payment_mode(mode_id)
                QMessageBox.information(self, "Success", "Payment mode deactivated.")
                self._clear_form()
                refresh_payment_modes_cache(self.api)
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        code = self.code.text().strip()
        name = self.name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validation", "Code and name are required.")
            return
        if self.ledger.currentData() is None:
            QMessageBox.warning(
                self,
                "Validation",
                "Select a ledger — OPD/IPD bill payments post to this ledger in cashbook.",
            )
            return

        payload = {
            "code": code,
            "name": name,
            "is_cash": self.is_cash.isChecked(),
            "ledger_id": self.ledger.currentData(),
            "sort_order": self.sort_order.value(),
        }
        try:
            if mode == self.MODE_CREATE:
                self.api.create_payment_mode(payload)
                QMessageBox.information(self, "Success", "Payment mode created.")
                self._clear_form()
            else:
                mode_id = self.mode_select.currentData() or self._selected_id
                if not mode_id:
                    QMessageBox.warning(self, "Validation", "Select a payment mode to modify.")
                    return
                self.api.update_payment_mode(
                    mode_id,
                    {
                        "name": name,
                        "is_cash": self.is_cash.isChecked(),
                        "ledger_id": self.ledger.currentData(),
                        "sort_order": self.sort_order.value(),
                    },
                )
                QMessageBox.information(self, "Success", "Payment mode updated.")
            refresh_payment_modes_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
