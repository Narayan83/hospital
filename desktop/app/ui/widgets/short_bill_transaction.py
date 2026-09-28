from datetime import date, datetime

from PySide6.QtCore import QDate, QEvent, QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.print_utils import preview_report


class _NextFieldOnEnter(QObject):
    """Enter moves to the next entry field and does not press Save."""

    def __init__(self, fields: list[QWidget]):
        super().__init__()
        self._fields = fields

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        target = obj if obj in self._fields else None
        if target is None and isinstance(obj, QWidget):
            parent = obj.parentWidget()
            while parent is not None and parent not in self._fields:
                parent = parent.parentWidget()
            target = parent
        if target not in self._fields:
            return False
        if isinstance(target, QDateEdit):
            calendar = target.calendarWidget()
            if calendar is not None and calendar.isVisible():
                return False
        index = self._fields.index(target)
        if index + 1 < len(self._fields):
            self._fields[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
            if isinstance(self._fields[index + 1], QLineEdit):
                self._fields[index + 1].selectAll()
        return True


class ShortBillTransactionWidget(QWidget):
    def __init__(self, api: ApiClient, *, menu_code: str):
        super().__init__()
        self.api = api
        self.menu_code = menu_code
        self._bill_type: dict | None = None
        self._current_bill_id: str | None = None
        self._resolved_patient_id: str | None = None
        self._listed_ids: list[str] = []
        self._filling_patient = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.heading = QLabel("Short Bill")
        self.heading.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1e40af; text-decoration: underline;"
        )
        layout.addWidget(self.heading)

        top = QHBoxLayout()
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("Auto on save")
        self.bill_no.setMaximumWidth(160)
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        self.bill_date.setMaximumWidth(150)
        top.addWidget(QLabel("Bill No"))
        top.addWidget(self.bill_no)
        top.addSpacing(12)
        top.addWidget(QLabel("Date"))
        top.addWidget(self.bill_date)
        top.addStretch()
        layout.addLayout(top)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.service_name = QLineEdit()
        self.service_name.setObjectName("service_name")
        self.service_name.setProperty("hmsAllowWide", True)
        self.service_name.setMinimumWidth(560)
        self.service_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("Service *", self.service_name)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 9999999)
        self.amount.setDecimals(2)
        self.amount.setMaximumWidth(160)
        form.addRow("Amount *", self.amount)

        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Optional")
        self.patient_id.setMaximumWidth(160)
        self.patient_id.textChanged.connect(self._on_patient_id_edited)
        self.patient_name = QLineEdit()
        self.patient_name.setObjectName("patient_name")
        self.patient_name.setPlaceholderText("Customer / patient name")
        self.patient_name.setProperty("hmsPatientName", True)
        patient_row = QHBoxLayout()
        patient_row.addWidget(self.patient_id)
        patient_row.addWidget(QLabel("Name *"))
        patient_row.addWidget(self.patient_name, stretch=1)
        find_btn = QPushButton("Find")
        find_btn.clicked.connect(self._find_patient)
        patient_row.addWidget(find_btn)
        patient_host = QWidget()
        patient_host.setLayout(patient_row)
        form.addRow("Patient Id", patient_host)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._clear_form(keep_type=True))
        self.print_btn = QPushButton("Print Bill")
        self.print_btn.clicked.connect(self._print_current)
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self._close)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        report_box = QGroupBox("Report")
        report_layout = QVBoxLayout(report_box)

        search_row = QHBoxLayout()
        self.search_bill = QLineEdit()
        self.search_bill.setPlaceholderText("Bill no or patient name")
        self.search_bill.setMinimumWidth(280)
        self.search_bill.returnPressed.connect(self._search_bills)
        search_btn = QPushButton("Search Bill")
        search_btn.clicked.connect(self._search_bills)
        reprint_btn = QPushButton("Reprint")
        reprint_btn.clicked.connect(self._reprint)
        search_row.addWidget(QLabel("Search"))
        search_row.addWidget(self.search_bill, stretch=1)
        search_row.addWidget(search_btn)
        search_row.addWidget(reprint_btn)
        search_row.addStretch()
        report_layout.addLayout(search_row)

        dates = QHBoxLayout()
        self.report_from = QDateEdit()
        self.report_from.setCalendarPopup(True)
        self.report_from.setDisplayFormat("dd/MM/yyyy")
        self.report_from.setDate(QDate.currentDate().addMonths(-1))
        self.report_to = QDateEdit()
        self.report_to.setCalendarPopup(True)
        self.report_to.setDisplayFormat("dd/MM/yyyy")
        self.report_to.setDate(QDate.currentDate())
        dates.addWidget(QLabel("From"))
        dates.addWidget(self.report_from)
        dates.addWidget(QLabel("To"))
        dates.addWidget(self.report_to)
        load_report_btn = QPushButton("Load Report")
        load_report_btn.clicked.connect(self._load_report)
        print_report_btn = QPushButton("Print Report")
        print_report_btn.clicked.connect(self._print_report)
        dates.addWidget(load_report_btn)
        dates.addWidget(print_report_btn)
        dates.addStretch()
        report_layout.addLayout(dates)

        self.report_table = QTableWidget(0, 5)
        self.report_table.setHorizontalHeaderLabels(["SLNO", "Bill No", "Date", "Name", "Amount"])
        header = self.report_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.report_table.setColumnWidth(0, 50)
        self.report_table.setColumnWidth(2, 90)
        self.report_table.setColumnWidth(4, 90)
        self.report_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.doubleClicked.connect(self._open_selected_bill)
        report_layout.addWidget(self.report_table)
        layout.addWidget(report_box, stretch=1)

        entry_fields = [
            self.bill_date,
            self.service_name,
            self.amount,
            self.patient_id,
            self.patient_name,
        ]
        self._enter_filter = _NextFieldOnEnter(entry_fields)
        for field in entry_fields:
            field.installEventFilter(self._enter_filter)
            for editor in field.findChildren(QLineEdit):
                editor.installEventFilter(self._enter_filter)
        QWidget.setTabOrder(self.bill_date, self.service_name)
        QWidget.setTabOrder(self.service_name, self.amount)
        QWidget.setTabOrder(self.amount, self.patient_id)
        QWidget.setTabOrder(self.patient_id, self.patient_name)

        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def refresh(self) -> None:
        try:
            self._bill_type = self.api.get_short_bill_type_by_menu(self.menu_code)
        except ApiError as exc:
            QMessageBox.warning(self, "Setup", str(exc))
            return
        title = self._bill_type.get("name") or "Short Bill"
        self.heading.setText(title.upper())
        if not self._current_bill_id:
            self._apply_defaults()
        self.service_name.setFocus(Qt.FocusReason.OtherFocusReason)

    def _apply_defaults(self) -> None:
        if not self._bill_type:
            return
        service = self._bill_type.get("default_service_name") or ""
        self.service_name.setText(service)
        self.amount.setValue(float(self._bill_type.get("default_rate") or 0))

    def _find_patient(self) -> None:
        query = self.patient_id.text().strip() or self.patient_name.text().strip()
        if not query:
            QMessageBox.information(self, "Find", "Enter patient id or name to search.")
            return
        try:
            result = self.api.search_patients(query=query, page_size=5)
            items = result.get("items", [])
        except ApiError as exc:
            QMessageBox.warning(self, "Find", str(exc))
            return
        if not items:
            QMessageBox.information(self, "Find", "No patient found.")
            return
        patient = items[0]
        self._filling_patient = True
        self.patient_id.setText(patient.get("patient_no", ""))
        self._filling_patient = False
        name = " ".join(
            part
            for part in [
                patient.get("first_name"),
                patient.get("middle_name"),
                patient.get("last_name"),
            ]
            if part
        )
        self.patient_name.setText(name)
        self._resolved_patient_id = patient.get("id")
        self.patient_name.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_patient_id_edited(self) -> None:
        if self._filling_patient:
            return
        self._resolved_patient_id = None

    def _save(self) -> None:
        if not self._bill_type:
            return
        name = self.patient_name.text().strip()
        service = self.service_name.text().strip()
        if not name or not service:
            QMessageBox.warning(self, "Save", "Patient name and service are required.")
            return
        patient_id = getattr(self, "_resolved_patient_id", None)
        payload = {
            "short_bill_type_id": self._bill_type["id"],
            "bill_date": self.bill_date.date().toPython().isoformat(),
            "patient_id": patient_id,
            "patient_name": name,
            "service_name": service,
            "amount": self.amount.value(),
            "doctor_id": self._bill_type.get("default_doctor_id"),
        }
        try:
            if self._current_bill_id:
                update_payload = {
                    "bill_date": payload["bill_date"],
                    "patient_id": payload["patient_id"],
                    "patient_name": payload["patient_name"],
                    "service_name": payload["service_name"],
                    "amount": payload["amount"],
                }
                bill = self.api.update_short_bill(self._current_bill_id, update_payload)
            else:
                bill = self.api.create_short_bill(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return
        self._apply_bill(bill)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Saved")
        box.setText(f"Bill {bill.get('bill_no')} saved.")
        box.setInformativeText("Print Bill prints this receipt. Clear starts the next bill.")
        print_btn = box.addButton("Print Bill", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("OK", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is print_btn:
            self._print_bill_id(bill.get("id"), title=f"Bill {bill.get('bill_no')}")

    def _apply_bill(self, bill: dict) -> None:
        self._current_bill_id = bill.get("id")
        self._resolved_patient_id = bill.get("patient_id")
        self._filling_patient = True
        self.bill_no.setText(bill.get("bill_no") or "")
        bill_date = bill.get("bill_date")
        if bill_date:
            parsed = QDate.fromString(str(bill_date)[:10], "yyyy-MM-dd")
            if parsed.isValid():
                self.bill_date.setDate(parsed)
        self.patient_id.setText(bill.get("patient_no") or "")
        self._filling_patient = False
        self.patient_name.setText(bill.get("patient_name") or "")
        self.service_name.setText(bill.get("service_name") or "")
        self.amount.setValue(float(bill.get("amount") or 0))

    def _delete(self) -> None:
        if not self._current_bill_id:
            QMessageBox.information(self, "Delete", "No bill selected to delete.")
            return
        if (
            QMessageBox.question(self, "Delete", "Delete this bill?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.api.delete_short_bill(self._current_bill_id)
            self._clear_form(keep_type=True)
            QMessageBox.information(self, "Deleted", "Bill deleted.")
        except ApiError as exc:
            QMessageBox.warning(self, "Delete", str(exc))

    def _clear_form(self, *, keep_type: bool = False) -> None:
        self._current_bill_id = None
        self._resolved_patient_id = None
        self.bill_no.clear()
        self.bill_date.setDate(QDate.currentDate())
        self.patient_id.clear()
        self.patient_name.clear()
        if keep_type:
            self._apply_defaults()
        else:
            self.service_name.clear()
            self.amount.setValue(0)
        self.service_name.setFocus(Qt.FocusReason.OtherFocusReason)

    def _close(self) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QDialog):
                parent.reject()
                return
            parent = parent.parentWidget()
        window = self.window()
        show_module = getattr(window, "_show_module", None)
        if callable(show_module):
            show_module("dashboard")

    def _print_current(self) -> None:
        if not self._current_bill_id:
            QMessageBox.information(
                self,
                "Print Bill",
                "Save a bill first, or search a bill and open it to reprint.",
            )
            return
        self._print_bill_id(self._current_bill_id, title=f"Bill {self.bill_no.text().strip()}")

    def _print_bill_id(self, bill_id: str | None, *, title: str = "Bill") -> None:
        if not bill_id:
            return
        preview_report(
            self.api,
            self.api.short_bill_print_endpoint(bill_id),
            parent=self,
            title=title,
            report_code="SHORT_BILL",
        )

    def _search_bills(self) -> None:
        if not self._bill_type:
            return
        query = self.search_bill.text().strip()
        if not query:
            QMessageBox.information(self, "Search", "Enter a bill number or patient name.")
            self.search_bill.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        try:
            items = self.api.search_short_bills(
                short_bill_type_id=self._bill_type["id"],
                query=query,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))
            return
        if not items:
            QMessageBox.information(self, "Search", "No bill found.")
            return
        self._fill_bill_table(items)
        if len(items) == 1:
            self._apply_bill(items[0])
            return
        QMessageBox.information(
            self,
            "Search",
            "Select a bill and click Reprint, or double-click a row to open it.",
        )

    def _open_selected_bill(self) -> None:
        bill_id = self._selected_bill_id()
        if not bill_id:
            return
        try:
            bill = self.api.get_short_bill(bill_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Bill", str(exc))
            return
        self._apply_bill(bill)

    def _reprint(self) -> None:
        bill_id = self._selected_bill_id() or self._current_bill_id
        if not bill_id:
            QMessageBox.information(
                self,
                "Reprint",
                "Search a bill, or select one in the list, then click Reprint.",
            )
            return
        label = self.bill_no.text().strip() or "Bill"
        self._print_bill_id(bill_id, title=f"Reprint {label}")

    def _selected_bill_id(self) -> str | None:
        selected = self.report_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self._listed_ids):
            return self._listed_ids[row]
        return None

    def _fill_bill_table(self, bills: list[dict]) -> None:
        rows = [
            {
                "bill_id": bill.get("id") or "",
                "bill_no": bill.get("bill_no") or "",
                "bill_date": bill.get("bill_date"),
                "patient_name": bill.get("patient_name") or "",
                "amount": float(bill.get("amount") or 0),
            }
            for bill in bills
        ]
        total = sum(row["amount"] for row in rows)
        self._render_rows(rows, total)

    def _load_report(self) -> None:
        if not self._bill_type:
            return
        from_date = self.report_from.date().toPython().isoformat()
        to_date = self.report_to.date().toPython().isoformat()
        try:
            report = self.api.get_short_bill_report(
                short_bill_type_id=self._bill_type["id"],
                from_date=from_date,
                to_date=to_date,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return
        rows = [
            {
                "bill_id": row.get("bill_id") or "",
                "bill_no": row.get("bill_no") or "",
                "bill_date": row.get("bill_date"),
                "patient_name": row.get("patient_name") or "",
                "amount": float(row.get("amount") or 0),
            }
            for row in (report.get("rows") or [])
        ]
        self._render_rows(rows, float(report.get("grand_total") or 0))

    def _render_rows(self, rows: list[dict], grand_total: float) -> None:
        self._listed_ids = [row.get("bill_id") or "" for row in rows]
        self.report_table.clearSpans()
        self.report_table.setRowCount(len(rows) + 1)
        bold = QFont()
        bold.setBold(True)
        for row_index, row in enumerate(rows):
            values = [
                str(row_index + 1),
                row.get("bill_no") or "",
                self._format_date(row.get("bill_date")),
                row.get("patient_name") or "",
                f"{float(row.get('amount') or 0):.2f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.report_table.setItem(row_index, col, item)
        total_row = len(rows)
        total_label = QTableWidgetItem("Total....")
        total_label.setFont(bold)
        total_label.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.report_table.setSpan(total_row, 0, 1, 4)
        self.report_table.setItem(total_row, 0, total_label)
        total_amount = QTableWidgetItem(f"{grand_total:.2f}")
        total_amount.setFont(bold)
        total_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.report_table.setItem(total_row, 4, total_amount)

    def _print_report(self) -> None:
        if not self._bill_type:
            return
        endpoint = self.api.short_bill_report_endpoint(
            short_bill_type_id=self._bill_type["id"],
            from_date=self.report_from.date().toPython().isoformat(),
            to_date=self.report_to.date().toPython().isoformat(),
        )
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title=f"{self._bill_type.get('name', 'Short Bill')} Report",
            report_code="SHORT_BILL_REPORT",
        )

    @staticmethod
    def _format_date(value: str | date | None) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value).date()
            except ValueError:
                return value
        return value.strftime("%d/%m/%Y")
