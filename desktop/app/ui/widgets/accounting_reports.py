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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


class AccountingRegisterWidget(QWidget):
    """Daybook or Cash Book report."""

    def __init__(self, api: ApiClient, *, mode: str = "daybook"):
        super().__init__()
        self.api = api
        self.mode = mode
        self._build_ui()

    def _title(self) -> str:
        return "Cash Book" if self.mode == "cash_book" else "Daybook"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel(self._title())
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        form.addRow("From Date", self.from_date)
        form.addRow("To Date", self.to_date)
        layout.addWidget(filters)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load)
        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.summary = QLabel("Select dates and load.")
        self.summary.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Voucher", "Source", "Patient", "Ledger", "Narration", "Debit", "Credit", "Type"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        self._load()

    def _iso_date(self, widget: QDateEdit) -> str:
        qd = widget.date()
        return f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"

    def _load(self) -> None:
        try:
            if self.mode == "cash_book":
                data = self.api.get_cash_book(
                    from_date=self._iso_date(self.from_date),
                    to_date=self._iso_date(self.to_date),
                )
            else:
                data = self.api.get_daybook(
                    from_date=self._iso_date(self.from_date),
                    to_date=self._iso_date(self.to_date),
                )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        entries = data.get("entries") or []
        self.summary.setText(
            f"Debit: {float(data.get('total_debit', 0)):,.2f}   "
            f"Credit: {float(data.get('total_credit', 0)):,.2f}   "
            f"Rows: {len(entries)}"
        )
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("voucher_date", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("voucher_no", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("source_type", "")))
            patient = entry.get("patient_no") or ""
            self.table.setItem(row, 3, QTableWidgetItem(patient))
            ledger = f"{entry.get('ledger_code', '')} {entry.get('ledger_name', '')}".strip()
            self.table.setItem(row, 4, QTableWidgetItem(ledger))
            self.table.setItem(row, 5, QTableWidgetItem(entry.get("narration") or ""))
            self.table.setItem(row, 6, QTableWidgetItem(f"{float(entry.get('debit_amount', 0)):,.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{float(entry.get('credit_amount', 0)):,.2f}"))
            self.table.setItem(row, 8, QTableWidgetItem(entry.get("source_type", "")))


class LedgerDetailsWidget(QWidget):
    """Ledger-wise statement (ledger details)."""

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._ledgers: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Ledger Details")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.ledger_combo = QComboBox()
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        form.addRow("Ledger *", self.ledger_combo)
        form.addRow("From Date", self.from_date)
        form.addRow("To Date", self.to_date)
        layout.addWidget(filters)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Ledger Details")
        load_btn.clicked.connect(self._load)
        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.summary = QLabel("Select a ledger and load.")
        self.summary.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Voucher", "Patient", "Narration", "Debit", "Credit", "Balance", "Source"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        try:
            self._ledgers = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        current = self.ledger_combo.currentData()
        self.ledger_combo.clear()
        for ledger in self._ledgers:
            self.ledger_combo.addItem(
                f"{ledger.get('code')} — {ledger.get('name')}",
                ledger.get("id"),
            )
        if current:
            idx = self.ledger_combo.findData(current)
            if idx >= 0:
                self.ledger_combo.setCurrentIndex(idx)

    def _iso_date(self, widget: QDateEdit) -> str:
        qd = widget.date()
        return f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"

    def _load(self) -> None:
        ledger_id = self.ledger_combo.currentData()
        if not ledger_id:
            QMessageBox.warning(self, "Validation", "Select a ledger.")
            return
        try:
            data = self.api.get_cashbook_ledger_statement(
                ledger_id,
                from_date=self._iso_date(self.from_date),
                to_date=self._iso_date(self.to_date),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.summary.setText(
            f"{data.get('ledger_code', '')} — Opening: {float(data.get('opening_balance', 0)):,.2f}   "
            f"Closing: {float(data.get('closing_balance', 0)):,.2f}"
        )
        entries = data.get("entries") or []
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("voucher_date", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("voucher_no", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("patient_no") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("narration") or ""))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(entry.get('debit_amount', 0)):,.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{float(entry.get('credit_amount', 0)):,.2f}"))
            balance = entry.get("running_balance")
            bal_text = f"{float(balance):,.2f}" if balance is not None else ""
            self.table.setItem(row, 6, QTableWidgetItem(bal_text))
            self.table.setItem(row, 7, QTableWidgetItem(entry.get("source_type", "")))
