from PySide6.QtCore import QDate, Qt
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.components.patient_search_dialog import pick_patient


class CashbookWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._ledgers: list[dict] = []
        self._patient: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Cashbook / Ledger View")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "View ledger-wise cashbook entries or patient account details. "
            "OPD and IPD bills post automatically to payment-mode ledgers and income ledgers."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_ledger_tab(), "Ledger Statement")
        self.tabs.addTab(self._build_patient_tab(), "Patient Account")
        layout.addWidget(self.tabs, stretch=1)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

    def _build_ledger_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

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
        load_btn = QPushButton("Load Statement")
        load_btn.clicked.connect(self._load_ledger_statement)
        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.ledger_summary = QLabel("Select a ledger and load statement.")
        self.ledger_summary.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(self.ledger_summary)

        self.ledger_table = QTableWidget(0, 8)
        self.ledger_table.setHorizontalHeaderLabels(
            ["Date", "Voucher", "Patient", "Narration", "Ledger", "Debit", "Credit", "Balance"]
        )
        self.ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ledger_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ledger_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.ledger_table, stretch=1)
        return page

    def _build_patient_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        filters = QGroupBox("Patient")
        form = QFormLayout(filters)
        search_row = QHBoxLayout()
        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Patient Id")
        self.patient_no.returnPressed.connect(self._load_patient_account)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._load_patient_account)
        pick_btn = QPushButton("Pick Patient")
        pick_btn.clicked.connect(self._pick_patient)
        search_row.addWidget(self.patient_no, stretch=1)
        search_row.addWidget(search_btn)
        search_row.addWidget(pick_btn)
        form.addRow("Patient Id", search_row)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        form.addRow("Patient Name", self.patient_name)
        self.patient_from_date = QDateEdit()
        self.patient_from_date.setCalendarPopup(True)
        self.patient_from_date.setDate(QDate.currentDate().addMonths(-6))
        self.patient_to_date = QDateEdit()
        self.patient_to_date.setCalendarPopup(True)
        self.patient_to_date.setDate(QDate.currentDate())
        form.addRow("From Date", self.patient_from_date)
        form.addRow("To Date", self.patient_to_date)
        layout.addWidget(filters)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Patient Account")
        load_btn.clicked.connect(self._load_patient_account)
        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.patient_summary = QLabel("Enter patient id and load account details.")
        self.patient_summary.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(self.patient_summary)

        self.patient_table = QTableWidget(0, 8)
        self.patient_table.setHorizontalHeaderLabels(
            ["Date", "Voucher", "Source", "Narration", "Ledger", "Debit", "Credit", "Balance"]
        )
        self.patient_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.patient_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.patient_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.patient_table, stretch=1)
        return page

    def refresh(self) -> None:
        try:
            self._ledgers = self.api.list_ledgers()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            self._ledgers = []
        current = self.ledger_combo.currentData()
        self.ledger_combo.clear()
        self.ledger_combo.addItem("— Select Ledger —", None)
        for item in self._ledgers:
            self.ledger_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))
        if current:
            idx = self.ledger_combo.findData(current)
            if idx >= 0:
                self.ledger_combo.setCurrentIndex(idx)

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, self)
        if not patient:
            return
        self._patient = patient
        self.patient_no.setText(patient.get("patient_no", ""))
        self.patient_name.setText(self._format_patient_name(patient))

    def _format_patient_name(self, patient: dict) -> str:
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        return " ".join(p for p in parts if p)

    def _load_ledger_statement(self) -> None:
        ledger_id = self.ledger_combo.currentData()
        if not ledger_id:
            QMessageBox.warning(self, "Validation", "Select a ledger.")
            return
        try:
            data = self.api.get_cashbook_ledger_statement(
                ledger_id,
                from_date=self.from_date.date().toString("yyyy-MM-dd"),
                to_date=self.to_date.date().toString("yyyy-MM-dd"),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.ledger_summary.setText(
            f"{data.get('ledger_code')} — {data.get('ledger_name')} | "
            f"Opening: {float(data.get('opening_balance', 0)):.2f} | "
            f"Debit: {float(data.get('total_debit', 0)):.2f} | "
            f"Credit: {float(data.get('total_credit', 0)):.2f} | "
            f"Closing: {float(data.get('closing_balance', 0)):.2f}"
        )
        entries = data.get("entries") or []
        self.ledger_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._set_entry_row(self.ledger_table, row, entry, show_patient=True)
        self.status.setText(f"Loaded {len(entries)} ledger entries.")

    def _load_patient_account(self) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            QMessageBox.warning(self, "Validation", "Enter patient id.")
            return
        try:
            data = self.api.get_cashbook_patient_account(
                patient_no=patient_no,
                from_date=self.patient_from_date.date().toString("yyyy-MM-dd"),
                to_date=self.patient_to_date.date().toString("yyyy-MM-dd"),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.patient_name.setText(data.get("patient_name") or "")
        deposit = data.get("deposit_balance")
        deposit_text = f" | Advance: {float(deposit):.2f}" if deposit is not None else ""
        self.patient_summary.setText(
            f"Patient {data.get('patient_no')} | "
            f"Debit: {float(data.get('total_debit', 0)):.2f} | "
            f"Credit: {float(data.get('total_credit', 0)):.2f} | "
            f"Balance: {float(data.get('balance', 0)):.2f}{deposit_text}"
        )
        entries = data.get("entries") or []
        self.patient_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._set_entry_row(self.patient_table, row, entry, show_source=True)
        self.status.setText(f"Loaded {len(entries)} patient account entries.")

    def _set_entry_row(
        self,
        table: QTableWidget,
        row: int,
        entry: dict,
        *,
        show_patient: bool = False,
        show_source: bool = False,
    ) -> None:
        third_col = ""
        if show_patient:
            third_col = entry.get("patient_no") or ""
        elif show_source:
            source = entry.get("source_type") or ""
            third_col = source.replace("_", " ").upper()

        table.setItem(row, 0, QTableWidgetItem(str(entry.get("voucher_date", ""))))
        table.setItem(row, 1, QTableWidgetItem(entry.get("voucher_no") or ""))
        table.setItem(row, 2, QTableWidgetItem(third_col))
        table.setItem(row, 3, QTableWidgetItem(entry.get("narration") or ""))
        ledger_label = entry.get("ledger_code") or entry.get("ledger_name") or ""
        table.setItem(row, 4, QTableWidgetItem(ledger_label))
        debit = float(entry.get("debit_amount") or 0)
        credit = float(entry.get("credit_amount") or 0)
        balance = entry.get("running_balance")
        debit_item = QTableWidgetItem(f"{debit:.2f}" if debit else "")
        credit_item = QTableWidgetItem(f"{credit:.2f}" if credit else "")
        balance_item = QTableWidgetItem(f"{float(balance):.2f}" if balance is not None else "")
        for item in (debit_item, credit_item, balance_item):
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, 5, debit_item)
        table.setItem(row, 6, credit_item)
        table.setItem(row, 7, balance_item)
