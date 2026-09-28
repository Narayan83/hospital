from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
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


class PharmacyPurchaseReturnWidget(QWidget):
    """Return medicines to supplier — reduces pharmacy stock."""

    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._catalog: list[dict] = []
        self._suppliers: list[dict] = []
        self._lines: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Medicine Purchase Return")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #b45309;")
        layout.addWidget(heading)

        hint = QLabel(
            "Return purchased stock to the supplier. Available stock is checked before save."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint)

        bill_box = QGroupBox("Return Bill")
        bill_form = QFormLayout(bill_box)
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("Assigned on Save")
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        self.supplier = QComboBox()
        self.invoice_no = QLineEdit()
        self.remarks = QLineEdit()
        bill_form.addRow("Return No", self.bill_no)
        bill_form.addRow("Return Date", self.bill_date)
        bill_form.addRow("Supplier", self.supplier)
        bill_form.addRow("Supplier Invoice / Ref", self.invoice_no)
        bill_form.addRow("Remarks", self.remarks)
        layout.addWidget(bill_box)

        add_box = QGroupBox("Add Item to Return")
        add_form = QFormLayout(add_box)
        self.item_combo = QComboBox()
        self.qty = QSpinBox()
        self.qty.setRange(1, 99999)
        self.qty.setValue(1)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 999999)
        self.rate.setDecimals(2)
        self.batch_no = QLineEdit()
        add_btn = QPushButton("Add Line")
        add_btn.clicked.connect(self._add_line)
        add_form.addRow("Item", self.item_combo)
        add_form.addRow("Quantity", self.qty)
        add_form.addRow("Rate", self.rate)
        add_form.addRow("Batch No", self.batch_no)
        add_form.addRow("", add_btn)
        layout.addWidget(add_box)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Code", "Name", "Qty", "Rate", "Amount"])
        self.lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.lines_table, stretch=1)

        self.total_label = QLabel("Return Total: 0.00")
        self.total_label.setStyleSheet("font-weight: bold; color: #b45309;")
        layout.addWidget(self.total_label)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Purchase Return")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self) -> None:
        try:
            self._suppliers = self.api.list_pharmacy_suppliers()
            self._catalog = self.api.list_pharmacy_items("MD")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.supplier.clear()
        self.supplier.addItem("— Select —", None)
        for supplier in self._suppliers:
            self.supplier.addItem(f"{supplier.get('code')} — {supplier.get('name')}", supplier.get("id"))
        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        for item in self._catalog:
            self.item_combo.addItem(f"{item.get('code')} — {item.get('name')}", item)
        try:
            self.item_combo.currentIndexChanged.disconnect(self._on_item_changed)
        except TypeError:
            pass
        self.item_combo.currentIndexChanged.connect(self._on_item_changed)
        self._on_item_changed()

    def _on_item_changed(self) -> None:
        item = self.item_combo.currentData()
        if not item:
            return
        self.rate.setValue(float(item.get("purchase_rate") or item.get("mrp") or 0))

    def _add_line(self) -> None:
        item = self.item_combo.currentData()
        if not item:
            QMessageBox.warning(self, "Validation", "Select an item.")
            return
        qty = self.qty.value()
        rate = Decimal(str(self.rate.value()))
        amount = rate * qty
        self._lines.append(
            {
                "item_id": item.get("id"),
                "item_code": item.get("code"),
                "item_name": item.get("name"),
                "quantity": qty,
                "rate": rate,
                "amount": amount,
                "batch_no": self.batch_no.text().strip() or None,
            }
        )
        self._refresh_lines_table()

    def _refresh_lines_table(self) -> None:
        self.lines_table.setRowCount(len(self._lines))
        total = Decimal("0")
        for row, line in enumerate(self._lines):
            self.lines_table.setItem(row, 0, QTableWidgetItem(line["item_code"]))
            self.lines_table.setItem(row, 1, QTableWidgetItem(line["item_name"]))
            self.lines_table.setItem(row, 2, QTableWidgetItem(str(line["quantity"])))
            self.lines_table.setItem(row, 3, QTableWidgetItem(f"{line['rate']:.2f}"))
            self.lines_table.setItem(row, 4, QTableWidgetItem(f"{line['amount']:.2f}"))
            total += line["amount"]
        self.total_label.setText(f"Return Total: {total:.2f}")

    def _save(self) -> None:
        if not self._lines:
            QMessageBox.warning(self, "Validation", "Add at least one item line.")
            return
        payload = {
            "supplier_id": self.supplier.currentData(),
            "invoice_no": self.invoice_no.text().strip() or None,
            "remarks": self.remarks.text().strip() or None,
            "bill_date": self.bill_date.date().toPython().isoformat(),
            "bill_kind": "return",
            "lines": [
                {
                    "item_id": line["item_id"],
                    "quantity": line["quantity"],
                    "rate": float(line["rate"]),
                    "batch_no": line.get("batch_no"),
                }
                for line in self._lines
            ],
        }
        try:
            bill = self.api.create_pharmacy_purchase_return(payload)
            self.bill_no.setText(bill.get("bill_no", ""))
            QMessageBox.information(self, "Saved", f"Purchase return {bill.get('bill_no')} saved.")
            self._clear(keep_bill_no=True)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _clear(self, *, keep_bill_no: bool = False) -> None:
        if not keep_bill_no:
            self.bill_no.clear()
        self.invoice_no.clear()
        self.remarks.clear()
        self.batch_no.clear()
        self._lines.clear()
        self._refresh_lines_table()
