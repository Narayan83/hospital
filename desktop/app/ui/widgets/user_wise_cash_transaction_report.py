from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.print_utils import _populate_printer_combo, preview_report


class UserWiseCashTransactionReportWidget(QWidget):
    REPORT_DETAIL = "detail"
    REPORT_DAY_WISE = "day_wise"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._users: list[dict] = []
        self._payment_modes: list[dict] = []
        self._report: dict | None = None
        self._report_type = self.REPORT_DETAIL
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("User wise Cash Transaction Report")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Select user (or All), date range, payment mode, and report type. "
            "Detail shows bill lines by payment mode, then advance collections and receipts, "
            "then payments and refunds as debit — so the net matches the cash actually collected. "
            "Day wise shows collection totals for each day when multiple dates are selected. "
            "Use Print Report to preview, print, or export Excel."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.user_combo = QComboBox()
        self.user_combo.setMinimumWidth(280)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setDate(QDate.currentDate())
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setDate(QDate.currentDate())
        self.payment_mode_combo = QComboBox()
        self.payment_mode_combo.setMinimumWidth(280)
        form.addRow("User", self.user_combo)
        form.addRow("From Date", self.from_date)
        form.addRow("To Date", self.to_date)
        form.addRow("Payment Mode", self.payment_mode_combo)
        layout.addWidget(filters)

        type_row = QHBoxLayout()
        self._type_group = QButtonGroup(self)
        self._type_group.setExclusive(True)
        for idx, (value, label) in enumerate(
            (
                (self.REPORT_DETAIL, "Detail Report"),
                (self.REPORT_DAY_WISE, "Day wise Collection"),
            )
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("reportType", value)
            if value == self.REPORT_DETAIL:
                btn.setChecked(True)
            self._type_group.addButton(btn, idx)
            type_row.addWidget(btn)
        self._type_group.buttonClicked.connect(self._on_report_type_clicked)
        type_row.addStretch(1)
        layout.addLayout(type_row)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Report")
        load_btn.clicked.connect(self.refresh)
        print_btn = QPushButton("Print Report")
        print_btn.clicked.connect(self._print_report)
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(280)
        _populate_printer_combo(self.printer_combo)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(QLabel("Printer:"))
        btn_row.addWidget(self.printer_combo, stretch=1)
        btn_row.addWidget(print_btn)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Bill No", "Patient Id", "Name", "Bill Amount"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 100)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("Select filters and load the report.")
        self.summary.setStyleSheet("color: #475569; font-weight: bold;")
        layout.addWidget(self.summary)

    def _on_report_type_clicked(self, button: QPushButton) -> None:
        self._report_type = str(button.property("reportType") or self.REPORT_DETAIL)

    def _selected_user_id(self) -> str | None:
        return self.user_combo.currentData()

    def _selected_payment_mode_id(self) -> str | None:
        return self.payment_mode_combo.currentData()

    def refresh(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "User", "Select a user or All.")
            return
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        report_type = self._report_type
        try:
            self._report = self.api.get_user_cash_transaction_report(
                user_id=user_id,
                from_date=from_date,
                to_date=to_date,
                report_type=report_type,
                payment_mode_id=self._selected_payment_mode_id(),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return

        if report_type == self.REPORT_DAY_WISE:
            self._populate_day_wise_table(self._report)
        else:
            self._populate_detail_table(self._report)

        user_name = self._report.get("user_name") or ""
        net_total = float(self._report.get("overall_grand_total") or 0)
        view_label = "Day wise" if report_type == self.REPORT_DAY_WISE else "Detail"
        self.summary.setText(
            f"{view_label} — {user_name} — "
            f"{self._report.get('payment_mode_label') or 'All Modes'} — "
            f"Bills: {float(self._report.get('bill_collection_total') or 0):.2f} + "
            f"Advance/Receipt: {float(self._report.get('advance_collection_total') or 0):.2f} - "
            f"Payments: {float(self._report.get('payment_debit_total') or 0):.2f} = "
            f"Net Cash: {net_total:.2f}"
        )

    def _configure_detail_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Bill No", "Patient Id", "Name", "Bill Amount"])

    def _configure_day_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Date / User", "Bill Type Totals", "Payment Mode Totals", "Total"]
        )

    def _populate_detail_table(self, report: dict) -> None:
        self._configure_detail_headers()
        rows: list[tuple[str, list[str], bool]] = []

        def add_section_row(label: str) -> None:
            rows.append(("section", [label, "", "", ""], True))

        def add_total_row(label: str, amount: str) -> None:
            rows.append(("total", [label, "", "", amount], True))

        def add_data_row(values: list[str]) -> None:
            rows.append(("data", values, False))

        for bill_group in report.get("bill_type_groups") or []:
            bill_type = bill_group.get("bill_type") or "—"
            is_debit = bool(bill_group.get("is_debit"))
            sign = -1.0 if is_debit else 1.0
            if is_debit:
                bill_type = f"{bill_type} (Debit)"
            payment_groups = bill_group.get("payment_groups") or []
            if not payment_groups:
                add_section_row(f"{bill_type}")
                add_total_row(
                    f"{bill_type} Grand Total",
                    f"{sign * float(bill_group.get('grand_total') or 0):.2f}",
                )
                continue

            add_section_row(bill_type)
            for payment_group in payment_groups:
                mode_name = payment_group.get("payment_mode_name") or "—"
                add_section_row(f"  Payment Mode: {mode_name}")
                for row in payment_group.get("rows") or []:
                    add_data_row(
                        [
                            row.get("bill_no") or "",
                            row.get("patient_no") or "",
                            row.get("patient_name") or "",
                            f"{sign * float(row.get('amount') or 0):.2f}",
                        ]
                    )
                add_total_row(
                    f"  Sub Total ({mode_name})",
                    f"{sign * float(payment_group.get('subtotal') or 0):.2f}",
                )
            add_total_row(
                f"{bill_type} Grand Total",
                f"{sign * float(bill_group.get('grand_total') or 0):.2f}",
            )

        self._add_summary_rows(report, add_total_row)
        self._fill_rows(rows, amount_col=3)

    @staticmethod
    def _add_summary_rows(report: dict, add_total_row) -> None:
        add_total_row(
            "Bill Collection",
            f"{float(report.get('bill_collection_total') or 0):.2f}",
        )
        add_total_row(
            "Advance / Receipt Collection",
            f"{float(report.get('advance_collection_total') or 0):.2f}",
        )
        payments = float(report.get("payment_debit_total") or 0)
        add_total_row(
            "Payments / Refunds (Debit)",
            f"{-payments if payments else 0:.2f}",
        )
        add_total_row(
            "Net Cash Transaction",
            f"{float(report.get('overall_grand_total') or 0):.2f}",
        )

    def _populate_day_wise_table(self, report: dict) -> None:
        self._configure_day_headers()
        rows: list[tuple[str, list[str], bool]] = []

        for day in report.get("day_groups") or []:
            day_label = self._format_date(day.get("bill_date"))
            rows.append(("section", [f"Date: {day_label}", "", "", ""], True))
            for user in day.get("users") or []:
                type_parts = [
                    f"{name}: {float(amt):.2f}"
                    for name, amt in (user.get("bill_type_totals") or {}).items()
                ]
                mode_parts = [
                    f"{name}: {float(amt):.2f}"
                    for name, amt in (user.get("payment_mode_totals") or {}).items()
                ]
                rows.append(
                    (
                        "data",
                        [
                            user.get("user_name") or "",
                            "; ".join(type_parts),
                            "; ".join(mode_parts),
                            f"{float(user.get('day_total') or 0):.2f}",
                        ],
                        False,
                    )
                )
            rows.append(
                (
                    "total",
                    [
                        f"Day Total ({day_label})",
                        "",
                        "",
                        f"{float(day.get('day_total') or 0):.2f}",
                    ],
                    True,
                )
            )

        def add_total_row(label: str, amount: str) -> None:
            rows.append(("total", [label, "", "", amount], True))

        self._add_summary_rows(report, add_total_row)
        self._fill_rows(rows, amount_col=3)

    @staticmethod
    def _format_date(value: str | date | None) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value).date()
            except ValueError:
                if len(value) >= 10 and value[4] == "-":
                    parts = value[:10].split("-")
                    if len(parts) == 3:
                        return f"{parts[2]}/{parts[1]}/{parts[0]}"
                return value
        return value.strftime("%d/%m/%Y")

    def _fill_rows(self, rows: list[tuple[str, list[str], bool]], *, amount_col: int) -> None:
        self.table.setRowCount(len(rows))
        bold_font = QFont()
        bold_font.setBold(True)
        section_color = QColor("#e2e8f0")
        total_color = QColor("#fef3c7")

        for row_index, (row_kind, values, is_bold) in enumerate(rows):
            bg = section_color if row_kind == "section" else total_color if row_kind == "total" else None
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_bold:
                    item.setFont(bold_font)
                if col == amount_col and value:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if bg:
                    item.setBackground(bg)
                self.table.setItem(row_index, col, item)
            if row_kind == "section":
                self.table.setSpan(row_index, 0, 1, self.table.columnCount())

    def _print_report(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Print", "Select a user or All.")
            return
        if not self._report:
            QMessageBox.information(self, "Print", "Load the report before printing.")
            return
        endpoint = self.api.user_cash_transaction_report_endpoint(
            user_id=user_id,
            from_date=self.from_date.date().toPython().isoformat(),
            to_date=self.to_date.date().toPython().isoformat(),
            report_type=self._report_type,
            payment_mode_id=self._selected_payment_mode_id(),
        )
        title = (
            "User wise Day wise Collection Report"
            if self._report_type == self.REPORT_DAY_WISE
            else "User wise Cash Transaction Report"
        )
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title=title,
            printer_name=self.printer_combo.currentData(),
            report_code="USER_CASH_REPORT",
            landscape=True,
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _populate_printer_combo(self.printer_combo)
        self._load_users()
        self._load_payment_modes()

    def _load_payment_modes(self) -> None:
        current_id = self.payment_mode_combo.currentData()
        try:
            self._payment_modes = self.api.list_payment_modes()
        except ApiError as exc:
            QMessageBox.warning(self, "Payment Modes", str(exc))
            return
        self.payment_mode_combo.clear()
        self.payment_mode_combo.addItem("All Modes", "all")
        for mode in self._payment_modes:
            self.payment_mode_combo.addItem(mode.get("name") or "", mode.get("id"))

        target = current_id
        if not target:
            cash = next((m for m in self._payment_modes if m.get("is_cash")), None)
            target = cash.get("id") if cash else None
        if target:
            idx = self.payment_mode_combo.findData(target)
            if idx >= 0:
                self.payment_mode_combo.setCurrentIndex(idx)

    def _load_users(self) -> None:
        current_id = self.user_combo.currentData()
        try:
            self._users = self.api.list_users()
        except ApiError as exc:
            QMessageBox.warning(self, "Users", str(exc))
            return
        self.user_combo.clear()
        self.user_combo.addItem("All Users", "all")
        for user in self._users:
            label = f"{user.get('full_name', '')} ({user.get('email', '')})"
            self.user_combo.addItem(label, user.get("id"))
        if current_id:
            idx = self.user_combo.findData(current_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
