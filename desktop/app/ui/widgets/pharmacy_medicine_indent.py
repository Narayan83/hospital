from collections.abc import Callable

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
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


class PharmacyMedicineIndentWidget(QWidget):
    """Issue medicines from pharmacy stock to a ward (indent)."""

    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._catalog: list[dict] = []
        self._wards: list[dict] = []
        self._lines: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Medicine Indent")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #047857;")
        layout.addWidget(heading)

        hint = QLabel(
            "Issue medicines from Medical Shop stock to a ward. Stock is reduced on save."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint)

        bill_box = QGroupBox("Indent")
        bill_form = QFormLayout(bill_box)
        self.indent_no = QLineEdit()
        self.indent_no.setReadOnly(True)
        self.indent_no.setPlaceholderText("Assigned on Save")
        self.indent_date = QDateEdit()
        self.indent_date.setCalendarPopup(True)
        self.indent_date.setDisplayFormat("dd/MM/yyyy")
        self.indent_date.setDate(QDate.currentDate())
        self.ward_combo = QComboBox()
        self.ward_manual = QLineEdit()
        self.ward_manual.setPlaceholderText("Or type ward / department name")
        self.remarks = QLineEdit()
        bill_form.addRow("Indent No", self.indent_no)
        bill_form.addRow("Date", self.indent_date)
        bill_form.addRow("Ward", self.ward_combo)
        bill_form.addRow("Ward (manual)", self.ward_manual)
        bill_form.addRow("Remarks", self.remarks)
        layout.addWidget(bill_box)

        add_box = QGroupBox("Add Medicine")
        add_form = QFormLayout(add_box)
        self.item_combo = QComboBox()
        self.qty = QSpinBox()
        self.qty.setRange(1, 99999)
        self.qty.setValue(1)
        self.batch_no = QLineEdit()
        add_btn = QPushButton("Add Line")
        add_btn.clicked.connect(self._add_line)
        add_form.addRow("Item", self.item_combo)
        add_form.addRow("Quantity", self.qty)
        add_form.addRow("Batch No", self.batch_no)
        add_form.addRow("", add_btn)
        layout.addWidget(add_box)

        self.lines_table = QTableWidget(0, 4)
        self.lines_table.setHorizontalHeaderLabels(["Code", "Name", "Qty", "Batch"])
        self.lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.lines_table, stretch=1)

        self.status = QLabel("Add items and save to issue stock to the ward.")
        self.status.setStyleSheet("color: #475569;")
        layout.addWidget(self.status)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Indent / Issue Stock")
        save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self) -> None:
        try:
            self._catalog = self.api.list_pharmacy_items("MD")
            self._wards = self.api.list_wards() or []
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.ward_combo.clear()
        self.ward_combo.addItem("— Select ward —", None)
        for ward in self._wards:
            if ward.get("is_active") is False:
                continue
            label = ward.get("name") or ward.get("code") or ward.get("id")
            self.ward_combo.addItem(label, label)

        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        for item in self._catalog:
            self.item_combo.addItem(f"{item.get('code')} — {item.get('name')}", item)

    def _ward_name(self) -> str:
        manual = self.ward_manual.text().strip()
        if manual:
            return manual
        return (self.ward_combo.currentData() or self.ward_combo.currentText() or "").strip()

    def _add_line(self) -> None:
        item = self.item_combo.currentData()
        if not item:
            QMessageBox.warning(self, "Validation", "Select an item.")
            return
        self._lines.append(
            {
                "item_id": item.get("id"),
                "item_code": item.get("code"),
                "item_name": item.get("name"),
                "quantity": self.qty.value(),
                "rate": float(item.get("sale_rate") or item.get("mrp") or 0),
                "batch_no": self.batch_no.text().strip() or None,
            }
        )
        self._refresh_lines_table()

    def _refresh_lines_table(self) -> None:
        self.lines_table.setRowCount(len(self._lines))
        total_qty = 0
        for row, line in enumerate(self._lines):
            self.lines_table.setItem(row, 0, QTableWidgetItem(line["item_code"]))
            self.lines_table.setItem(row, 1, QTableWidgetItem(line["item_name"]))
            self.lines_table.setItem(row, 2, QTableWidgetItem(str(line["quantity"])))
            self.lines_table.setItem(row, 3, QTableWidgetItem(line.get("batch_no") or ""))
            total_qty += int(line["quantity"])
        self.status.setText(f"{len(self._lines)} line(s) · {total_qty} unit(s)")

    def _save(self) -> None:
        ward = self._ward_name()
        if not ward or ward.startswith("—"):
            QMessageBox.warning(self, "Validation", "Select or type a ward name.")
            return
        if not self._lines:
            QMessageBox.warning(self, "Validation", "Add at least one medicine line.")
            return
        payload = {
            "ward_name": ward,
            "remarks": self.remarks.text().strip() or None,
            "bill_date": self.indent_date.date().toPython().isoformat(),
            "lines": [
                {
                    "item_id": line["item_id"],
                    "quantity": line["quantity"],
                    "rate": float(line.get("rate") or 0),
                    "batch_no": line.get("batch_no"),
                }
                for line in self._lines
            ],
        }
        try:
            bill = self.api.create_pharmacy_indent(payload)
            self.indent_no.setText(bill.get("bill_no", ""))
            QMessageBox.information(
                self,
                "Saved",
                f"Indent {bill.get('bill_no')} issued to {ward}.\nStock has been reduced.",
            )
            self._clear(keep_no=True)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _clear(self, *, keep_no: bool = False) -> None:
        if not keep_no:
            self.indent_no.clear()
        self.ward_manual.clear()
        self.remarks.clear()
        self.batch_no.clear()
        self._lines.clear()
        self._refresh_lines_table()
