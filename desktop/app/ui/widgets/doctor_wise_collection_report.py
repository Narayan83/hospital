from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.print_utils import _populate_printer_combo, preview_report
from app.ui.table_utils import enable_column_resize

_FILTER_CHECKBOX_STYLE = """
QCheckBox {
    color: #0f172a;
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #64748b;
    border-radius: 3px;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #1e40af;
    border-color: #1e40af;
}
QCheckBox::indicator:unchecked {
    background: #ffffff;
    border-color: #64748b;
}
"""


class _FilterResizeHandle(QFrame):
    """Drag vertically to grow/shrink the filter list height."""

    def __init__(self, on_delta, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_delta = on_delta
        self._dragging = False
        self._last_y = 0
        self.setObjectName("filterResizeHandle")
        self.setFixedHeight(10)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag up or down to resize selection lists")
        self.setStyleSheet(
            "QFrame#filterResizeHandle {"
            "  background: #e2e8f0;"
            "  border: 1px solid #cbd5e1;"
            "  border-radius: 4px;"
            "}"
            "QFrame#filterResizeHandle:hover { background: #bfdbfe; }"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_y = int(event.globalPosition().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            y = int(event.globalPosition().y())
            delta = y - self._last_y
            self._last_y = y
            if delta:
                self._on_delta(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DoctorWiseCollectionReportWidget(QWidget):
    REPORT_SHARING = "sharing"
    REPORT_DAY_WISE = "day_wise_summary"
    REPORT_PAYMENT_MODE = "payment_mode_summary"
    REPORT_COLUMN = "column_wise"
    REPORT_DATE_SERVICE_SUMMARY = "date_service_summary"
    REPORT_DATE_SERVICE_DETAILS = "date_service_details"

    _FILTER_MIN_HEIGHT = 90
    _FILTER_MAX_HEIGHT = 420
    _FILTER_DEFAULT_HEIGHT = 140

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._doctors: list[dict] = []
        self._doctor_checks: list[tuple[str, QCheckBox]] = []
        self._payment_checks: list[tuple[str, QCheckBox]] = []
        self._service_checks: list[tuple[str, QCheckBox]] = []
        self._report: dict | None = None
        self._report_type = self.REPORT_SHARING
        self._filter_list_height = self._FILTER_DEFAULT_HEIGHT
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        heading = QLabel("Doctor wise Collection Report")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        title_row.addWidget(heading)
        title_row.addStretch(1)
        help_btn = QPushButton("Help")
        help_btn.setToolTip("How to use this report")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setFixedHeight(28)
        help_btn.setStyleSheet(
            "QPushButton {"
            "  background: #eff6ff; color: #1e40af; border: 1px solid #93c5fd;"
            "  border-radius: 6px; padding: 4px 14px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #dbeafe; }"
        )
        help_btn.clicked.connect(self._show_help)
        title_row.addWidget(help_btn)
        layout.addLayout(title_row)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate())
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        for field in (self.from_date, self.to_date):
            field.setMaximumWidth(140)
            field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top.addWidget(QLabel("From"))
        top.addWidget(self.from_date)
        top.addWidget(QLabel("To"))
        top.addWidget(self.to_date)

        print_btn = QPushButton("Print Report")
        print_btn.clicked.connect(self._print_report)
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(220)
        _populate_printer_combo(self.printer_combo)
        top.addStretch(1)
        top.addWidget(QLabel("Printer"))
        top.addWidget(self.printer_combo)
        top.addWidget(print_btn)
        layout.addLayout(top)

        # Selection boxes first
        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)

        (
            doctor_box,
            self.select_all_doctors,
            self.doctor_search,
            self.doctor_scroll,
            self.doctor_host,
            self.doctor_list_layout,
        ) = self._make_filter_box(
            "Doctors",
            all_label="All Doctors",
            search_placeholder="Search doctors…",
            on_select_all=lambda: self._set_all_checks(self._doctor_checks, True),
            on_clear=lambda: self._set_all_checks(self._doctor_checks, False),
            on_toggle_all=self._toggle_all_doctors,
            on_search=self._filter_doctor_checks,
        )
        filters_row.addWidget(doctor_box, stretch=1)

        (
            payment_box,
            self.select_all_payments,
            self.payment_search,
            self.payment_scroll,
            self.payment_host,
            self.payment_list_layout,
        ) = self._make_filter_box(
            "Payment Mode Filter",
            all_label="All Modes",
            search_placeholder="Search payment modes…",
            on_select_all=lambda: self._set_all_checks(self._payment_checks, True),
            on_clear=lambda: self._set_all_checks(self._payment_checks, False),
            on_toggle_all=self._toggle_all_payments,
            on_search=self._filter_payment_checks,
        )
        filters_row.addWidget(payment_box, stretch=1)

        (
            service_box,
            self.select_all_services,
            self.service_search,
            self.service_scroll,
            self.service_host,
            self.service_list_layout,
        ) = self._make_filter_box(
            "Services Filter",
            all_label="All Services",
            search_placeholder="Search services…",
            on_select_all=lambda: self._set_all_checks(self._service_checks, True),
            on_clear=lambda: self._set_all_checks(self._service_checks, False),
            on_toggle_all=self._toggle_all_services,
            on_search=self._filter_service_checks,
        )
        filters_row.addWidget(service_box, stretch=1)

        layout.addLayout(filters_row)

        # Drag handle to resize selection lists
        self._resize_handle = _FilterResizeHandle(self._on_filter_resize_delta)
        layout.addWidget(self._resize_handle)

        # Report type buttons below selection boxes
        type_row = QHBoxLayout()
        type_row.setSpacing(6)
        self._type_group = QButtonGroup(self)
        self._type_group.setExclusive(True)
        type_defs = [
            (self.REPORT_DAY_WISE, "Day wise Summary"),
            (self.REPORT_PAYMENT_MODE, "Payment Mode Summary"),
            (self.REPORT_SHARING, "Doctor wise Sharing"),
            (self.REPORT_COLUMN, "Column wise"),
            (self.REPORT_DATE_SERVICE_SUMMARY, "Date/Service Summary"),
            (self.REPORT_DATE_SERVICE_DETAILS, "Date/Service Details"),
        ]
        for idx, (value, label) in enumerate(type_defs):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("reportType", value)
            if value == self.REPORT_SHARING:
                btn.setChecked(True)
            self._type_group.addButton(btn, idx)
            type_row.addWidget(btn)
        self._type_group.buttonClicked.connect(self._on_report_type_clicked)
        type_row.addStretch(1)

        load_btn = QPushButton("Load Report")
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setFixedHeight(32)
        load_btn.setMinimumWidth(120)
        load_btn.setStyleSheet(
            "QPushButton {"
            "  background: #059669; color: #ffffff; border: 1px solid #047857;"
            "  border-radius: 6px; padding: 4px 18px; font-weight: 700;"
            "}"
            "QPushButton:hover { background: #047857; }"
            "QPushButton:pressed { background: #065f46; }"
        )
        load_btn.clicked.connect(self.refresh)
        type_row.addWidget(load_btn)
        layout.addLayout(type_row)

        self.table = QTableWidget(0, 8)
        self.table.setProperty("hmsNoStretch", True)
        self._configure_normal_headers()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("Select filters and load the report.")
        self.summary.setStyleSheet("color: #475569; font-weight: bold;")
        layout.addWidget(self.summary)

        self._load_filters_if_needed()

    def _make_filter_box(
        self,
        title: str,
        *,
        all_label: str,
        search_placeholder: str,
        on_select_all,
        on_clear,
        on_toggle_all,
        on_search,
    ) -> tuple[QGroupBox, QCheckBox, QLineEdit, QScrollArea, QWidget, QVBoxLayout]:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(6, 6, 6, 6)
        box_layout.setSpacing(4)

        search = QLineEdit()
        search.setPlaceholderText(search_placeholder)
        search.setClearButtonEnabled(True)
        search.textChanged.connect(on_search)
        box_layout.addWidget(search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(self._FILTER_MIN_HEIGHT)
        scroll.setMaximumHeight(self._filter_list_height)
        scroll.setFixedHeight(self._filter_list_height)
        host = QWidget()
        list_layout = QVBoxLayout(host)
        list_layout.setContentsMargins(4, 2, 4, 2)
        list_layout.setSpacing(2)
        list_layout.addStretch(1)
        scroll.setWidget(host)
        box_layout.addWidget(scroll)

        select_all = QCheckBox(all_label)
        select_all.setChecked(True)
        select_all.setStyleSheet(_FILTER_CHECKBOX_STYLE)
        select_all.stateChanged.connect(on_toggle_all)
        box_layout.addWidget(select_all)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        select_btn = QPushButton("Select All")
        select_btn.setFixedHeight(24)
        select_btn.clicked.connect(on_select_all)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(on_clear)
        for btn in (select_btn, clear_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #f8fafc; color: #1e40af; border: 1px solid #cbd5e1;"
                "  border-radius: 4px; padding: 2px 10px; font-size: 11px;"
                "}"
                "QPushButton:hover { background: #eff6ff; }"
            )
        btn_row.addWidget(select_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        box_layout.addLayout(btn_row)

        return box, select_all, search, scroll, host, list_layout

    def _apply_filter_list_height(self) -> None:
        height = max(self._FILTER_MIN_HEIGHT, min(self._FILTER_MAX_HEIGHT, self._filter_list_height))
        self._filter_list_height = height
        for scroll in (self.doctor_scroll, self.payment_scroll, self.service_scroll):
            scroll.setMinimumHeight(self._FILTER_MIN_HEIGHT)
            scroll.setMaximumHeight(height)
            scroll.setFixedHeight(height)

    def _on_filter_resize_delta(self, delta: int) -> None:
        self._filter_list_height = self._filter_list_height + delta
        self._apply_filter_list_height()

    def _set_all_checks(
        self,
        checks: list[tuple[str, QCheckBox]],
        checked: bool,
        *,
        visible_only: bool = False,
    ) -> None:
        for _, checkbox in checks:
            if visible_only and not checkbox.isVisible():
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        if checks is self._doctor_checks:
            self._sync_select_all_doctors()
        elif checks is self._payment_checks:
            self._sync_select_all_payments()
        else:
            self._sync_select_all_services()

    def _toggle_visible_checks(
        self,
        checks: list[tuple[str, QCheckBox]],
        state: int,
    ) -> None:
        checked = state == Qt.CheckState.Checked.value
        self._set_all_checks(checks, checked, visible_only=True)

    def _filter_checks(
        self,
        checks: list[tuple[str, QCheckBox]],
        query: str,
    ) -> None:
        needle = (query or "").strip().casefold()
        for _, checkbox in checks:
            label = checkbox.text().casefold()
            checkbox.setVisible(not needle or needle in label)

    def _filter_doctor_checks(self, text: str) -> None:
        self._filter_checks(self._doctor_checks, text)

    def _filter_payment_checks(self, text: str) -> None:
        self._filter_checks(self._payment_checks, text)

    def _filter_service_checks(self, text: str) -> None:
        self._filter_checks(self._service_checks, text)

    def _on_report_type_clicked(self, button: QPushButton) -> None:
        self._report_type = str(button.property("reportType") or self.REPORT_SHARING)

    def _selected_report_type(self) -> str:
        return self._report_type or self.REPORT_SHARING

    def _show_help(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Doctor Collection Report — Help")
        dialog.setMinimumSize(520, 480)
        dialog.resize(560, 520)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("How to use")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a;")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        def add_card(heading: str, lines: list[str], *, accent: str = "#1e40af") -> None:
            card = QFrame()
            card.setStyleSheet(
                "QFrame {"
                f"  background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid {accent};"
                "  border-radius: 8px;"
                "}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(4)
            h = QLabel(heading)
            h.setStyleSheet(f"font-weight: 700; color: {accent}; font-size: 13px; border: none;")
            card_layout.addWidget(h)
            for line in lines:
                lab = QLabel(line)
                lab.setWordWrap(True)
                lab.setStyleSheet("color: #334155; font-size: 12px; border: none;")
                card_layout.addWidget(lab)
            body_layout.addWidget(card)

        add_card(
            "Quick steps",
            [
                "1. Choose From / To dates at the top.",
                "2. Filter Doctors / Payment Modes / Services in the selection lists.",
                "3. Drag the grey bar under the lists to show more options.",
                "4. Use Select All / Clear under each list, or the All checkbox.",
                "5. Pick a report type button (Day wise, Sharing, Column wise, etc.).",
                "6. Click the green Load Report button on the right of those type buttons.",
                "7. Print / Save to Excel from the top row if needed.",
            ],
        )
        add_card(
            "Report types",
            [
                "• Day wise Summary — each doctor, each day total (no bill lines).",
                "• Payment Mode Summary — totals by payment mode, then doctor.",
                "• Doctor wise Sharing — hospital/doctor split with bill detail + service summary.",
                "• Column wise — one row per bill; each setup service is its own amount column.",
                "• Date/Service Summary — each date, then selected service totals (all billed services).",
                "• Date/Service Details — each date, then selected service, then each bill line.",
            ],
            accent="#0369a1",
        )
        add_card(
            "Column wise setup (one-time)",
            [
                "Where: Masters → Patient Service Master",
                "How:",
                "1. Open the service that should appear as a column (e.g. Consultation, OT).",
                "2. Set “Dr Collection Col ?” = Y",
                "3. Save the service.",
                "4. Come back here, choose Column wise, then click the green Load Report.",
                "Only services with Y appear as columns. If the report is empty, no service has Y yet.",
            ],
            accent="#b45309",
        )
        add_card(
            "Filters & Load Report",
            [
                "• Search boxes filter the checkbox lists as you type.",
                "• All Doctors / All Modes / All Services checkbox sits below each list.",
                "• Select All / Clear buttons select or clear the visible items.",
                "• Drag the grey bar under the lists to show more doctors / modes / services.",
                "• Services — for Sharing / Day wise / Payment Mode / Date-Service, limit lines to selected services.",
                "• Load Report (green) sits to the right of the report type buttons, after the selection lists — choose type first, then load.",
            ],
            accent="#047857",
        )
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setDefault(True)
        root.addWidget(buttons)
        dialog.exec()

    def _apply_column_drag(self) -> None:
        self.table.setProperty("hmsNoStretch", True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        enable_column_resize(self.table)

    def _configure_normal_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Date",
                "Bill No",
                "Patient Id",
                "Payment Mode",
                "Service",
                "Original Rate",
                "Hospital",
                "Doctor",
            ]
        )
        self._apply_column_drag()

    def _configure_day_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Hospital", "Doctor", "Total"])
        self._apply_column_drag()

    def _configure_payment_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Payment Mode / Doctor", "Hospital", "Doctor Share", "Total"]
        )
        self._apply_column_drag()

    def _configure_date_service_summary_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Service", "Hospital", "Doctor", "Total"])
        self._apply_column_drag()

    def _configure_date_service_detail_headers(self) -> None:
        self.table.clearSpans()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Bill No",
                "Patient Id",
                "Payment Mode",
                "Original Rate",
                "Hospital",
                "Doctor",
                "Total",
            ]
        )
        self._apply_column_drag()

    def _configure_column_headers(self, service_columns: list[dict]) -> None:
        labels = ["Date", "Bill No", "Patient Id", "Name", "Payment Mode"]
        labels.extend(col.get("service_name") or "" for col in service_columns)
        labels.append("Total")
        self.table.clearSpans()
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self._apply_column_drag()

    def refresh(self) -> None:
        self._load_filters_if_needed()
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        doctor_ids = self._effective_doctor_ids()
        if doctor_ids is not None and not doctor_ids:
            QMessageBox.warning(self, "Doctors", "Select at least one doctor or choose All Doctors.")
            return
        payment_modes = self._effective_payment_modes()
        if payment_modes is not None and not payment_modes:
            QMessageBox.warning(self, "Payment Mode", "Select at least one payment mode or All Modes.")
            return
        service_ids = self._effective_service_ids()
        if service_ids is not None and not service_ids:
            QMessageBox.warning(self, "Services", "Select at least one service or All Services.")
            return
        report_type = self._selected_report_type()
        try:
            self._report = self.api.get_doctor_collection_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                payment_modes=payment_modes,
                report_type=report_type,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return

        overall = (
            "Overall Total — Hospital: "
            f"{float(self._report.get('overall_hospital_amount') or 0):.2f} | "
            f"Doctor: {float(self._report.get('overall_doctor_amount') or 0):.2f} | "
            f"Total: {float(self._report.get('overall_total_amount') or 0):.2f}"
        )

        if report_type == self.REPORT_COLUMN:
            self._populate_column_table(self._report)
            service_columns = self._report.get("service_columns") or []
            if not service_columns:
                self.summary.setText(
                    "No services marked for columns. Set “Doctor Collection Column = Y” "
                    "in Patient Service Master."
                )
            else:
                doctor_count = len(self._report.get("doctors") or [])
                self.summary.setText(
                    f"Separate sections for {doctor_count} doctor(s). "
                    f"Overall Total Collection: {float(self._report.get('overall_total_amount') or 0):.2f}"
                )
        elif report_type == self.REPORT_PAYMENT_MODE:
            self._populate_payment_mode_table(self._report)
            self.summary.setText(overall)
        elif report_type == self.REPORT_DAY_WISE:
            self._populate_day_wise_table(self._report)
            self.summary.setText(overall)
        elif report_type == self.REPORT_DATE_SERVICE_SUMMARY:
            self._populate_date_service_summary_table(self._report)
            self.summary.setText(overall)
        elif report_type == self.REPORT_DATE_SERVICE_DETAILS:
            self._populate_date_service_details_table(self._report)
            self.summary.setText(overall)
        else:
            self._populate_normal_table(self._report)
            self.summary.setText(overall)

    def _load_filters_if_needed(self) -> None:
        self._load_doctors_if_needed()
        self._load_payment_modes_if_needed()
        self._load_services_if_needed()

    def _add_filter_checkbox(
        self,
        list_layout: QVBoxLayout,
        checks: list[tuple[str, QCheckBox]],
        key: str,
        label: str,
        on_sync,
    ) -> None:
        checkbox = QCheckBox(str(label))
        checkbox.setChecked(True)
        checkbox.setStyleSheet(_FILTER_CHECKBOX_STYLE)
        checkbox.stateChanged.connect(on_sync)
        checks.append((key, checkbox))
        # Keep trailing stretch at the end so items stay top-aligned.
        insert_at = max(0, list_layout.count() - 1)
        list_layout.insertWidget(insert_at, checkbox)

    def _clear_filter_list(self, list_layout: QVBoxLayout) -> None:
        while list_layout.count():
            item = list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        list_layout.addStretch(1)

    def _load_doctors_if_needed(self) -> None:
        if self._doctor_checks:
            return
        cache = get_session().cache
        if cache.loaded and cache.doctors:
            self._doctors = list(cache.doctors)
        else:
            try:
                page = self.api.list_doctors(page=1, page_size=500)
                self._doctors = page.get("items") or []
            except ApiError:
                self._doctors = []
        self._clear_filter_list(self.doctor_list_layout)
        self._doctor_checks = []
        for doctor in self._doctors:
            label = doctor.get("full_name") or doctor.get("doctor_code") or doctor.get("id")
            self._add_filter_checkbox(
                self.doctor_list_layout,
                self._doctor_checks,
                doctor.get("id"),
                label,
                self._sync_select_all_doctors,
            )
        self._filter_doctor_checks(self.doctor_search.text())

    def _load_payment_modes_if_needed(self) -> None:
        if self._payment_checks:
            return
        try:
            modes = self.api.list_payment_modes() or []
        except ApiError:
            modes = []
        self._clear_filter_list(self.payment_list_layout)
        self._payment_checks = []
        for mode in modes:
            if mode.get("is_active") is False:
                continue
            name = (mode.get("name") or "").strip()
            if not name:
                continue
            self._add_filter_checkbox(
                self.payment_list_layout,
                self._payment_checks,
                name,
                name,
                self._sync_select_all_payments,
            )
        self._filter_payment_checks(self.payment_search.text())

    def _load_services_if_needed(self) -> None:
        if self._service_checks:
            return
        try:
            services = self.api.list_patient_services() or []
        except ApiError:
            services = []
        self._clear_filter_list(self.service_list_layout)
        self._service_checks = []
        for service in services:
            if service.get("is_active") is False:
                continue
            label = service.get("name") or service.get("code") or service.get("id")
            self._add_filter_checkbox(
                self.service_list_layout,
                self._service_checks,
                service.get("id"),
                label,
                self._sync_select_all_services,
            )
        self._filter_service_checks(self.service_search.text())

    def _selected_doctor_ids(self) -> list[str]:
        return [doctor_id for doctor_id, checkbox in self._doctor_checks if checkbox.isChecked() and doctor_id]

    def _selected_payment_modes(self) -> list[str]:
        return [name for name, checkbox in self._payment_checks if checkbox.isChecked() and name]

    def _selected_service_ids(self) -> list[str]:
        return [sid for sid, checkbox in self._service_checks if checkbox.isChecked() and sid]

    def _effective_doctor_ids(self) -> list[str] | None:
        selected = self._selected_doctor_ids()
        if self._doctor_checks and len(selected) == len(self._doctor_checks):
            return None
        return selected

    def _effective_payment_modes(self) -> list[str] | None:
        selected = self._selected_payment_modes()
        if self._payment_checks and len(selected) == len(self._payment_checks):
            return None
        return selected

    def _effective_service_ids(self) -> list[str] | None:
        selected = self._selected_service_ids()
        if self._service_checks and len(selected) == len(self._service_checks):
            return None
        return selected

    def _toggle_all_doctors(self, state: int) -> None:
        self._toggle_visible_checks(self._doctor_checks, state)

    def _toggle_all_payments(self, state: int) -> None:
        self._toggle_visible_checks(self._payment_checks, state)

    def _toggle_all_services(self, state: int) -> None:
        self._toggle_visible_checks(self._service_checks, state)

    def _sync_select_all(
        self,
        checks: list[tuple[str, QCheckBox]],
        select_all: QCheckBox,
    ) -> None:
        visible = [checkbox for _, checkbox in checks if checkbox.isVisible()]
        if not visible:
            return
        all_checked = all(checkbox.isChecked() for checkbox in visible)
        select_all.blockSignals(True)
        select_all.setChecked(all_checked)
        select_all.blockSignals(False)

    def _sync_select_all_doctors(self) -> None:
        self._sync_select_all(self._doctor_checks, self.select_all_doctors)

    def _sync_select_all_payments(self) -> None:
        self._sync_select_all(self._payment_checks, self.select_all_payments)

    def _sync_select_all_services(self) -> None:
        self._sync_select_all(self._service_checks, self.select_all_services)

    def _populate_day_wise_table(self, report: dict) -> None:
        self._configure_day_headers()
        rows: list[tuple[list[str], bool, str]] = []
        for doctor_idx, doctor_group in enumerate(report.get("doctors") or []):
            if doctor_idx > 0:
                rows.append((["", "", "", ""], False, "spacer"))
            rows.append(
                ([f"Doctor: {doctor_group.get('doctor_name') or '—'}", "", "", ""], True, "doctor")
            )
            for date_group in doctor_group.get("date_groups") or []:
                rows.append(
                    (
                        [
                            str(date_group.get("bill_date") or ""),
                            f"{float(date_group.get('hospital_amount') or 0):.2f}",
                            f"{float(date_group.get('doctor_amount') or 0):.2f}",
                            f"{float(date_group.get('total_amount') or 0):.2f}",
                        ],
                        False,
                        "data",
                    )
                )
            rows.append(
                (
                    [
                        "Doctor Total",
                        f"{float(doctor_group.get('grand_hospital_amount') or 0):.2f}",
                        f"{float(doctor_group.get('grand_doctor_amount') or 0):.2f}",
                        f"{float(doctor_group.get('grand_total_amount') or 0):.2f}",
                    ],
                    True,
                    "total",
                )
            )
        self._fill_simple_rows(rows, amount_start=1)

    def _populate_payment_mode_table(self, report: dict) -> None:
        self._configure_payment_headers()
        rows: list[tuple[list[str], bool, str]] = []
        for mode_idx, mode_group in enumerate(report.get("payment_modes") or []):
            if mode_idx > 0:
                rows.append((["", "", "", ""], False, "spacer"))
            rows.append(
                (
                    [f"Payment Mode: {mode_group.get('payment_mode') or '—'}", "", "", ""],
                    True,
                    "doctor",
                )
            )
            for row in mode_group.get("doctors") or []:
                rows.append(
                    (
                        [
                            row.get("doctor_name") or "",
                            f"{float(row.get('hospital_amount') or 0):.2f}",
                            f"{float(row.get('doctor_amount') or 0):.2f}",
                            f"{float(row.get('total_amount') or 0):.2f}",
                        ],
                        False,
                        "data",
                    )
                )
            rows.append(
                (
                    [
                        "Mode Total",
                        f"{float(mode_group.get('hospital_amount') or 0):.2f}",
                        f"{float(mode_group.get('doctor_amount') or 0):.2f}",
                        f"{float(mode_group.get('total_amount') or 0):.2f}",
                    ],
                    True,
                    "total",
                )
            )
        self._fill_simple_rows(rows, amount_start=1)

    def _populate_date_service_summary_table(self, report: dict) -> None:
        self._configure_date_service_summary_headers()
        rows: list[tuple[list[str], bool, str]] = []
        for date_idx, date_group in enumerate(report.get("date_groups") or []):
            if date_idx > 0:
                rows.append((["", "", "", ""], False, "spacer"))
            rows.append(
                ([f"Date: {date_group.get('bill_date') or '—'}", "", "", ""], True, "doctor")
            )
            for svc in date_group.get("services") or []:
                rows.append(
                    (
                        [
                            svc.get("service_name") or "",
                            f"{float(svc.get('hospital_amount') or 0):.2f}",
                            f"{float(svc.get('doctor_amount') or 0):.2f}",
                            f"{float(svc.get('total_amount') or 0):.2f}",
                        ],
                        False,
                        "data",
                    )
                )
            rows.append(
                (
                    [
                        "Date Total",
                        f"{float(date_group.get('hospital_amount') or 0):.2f}",
                        f"{float(date_group.get('doctor_amount') or 0):.2f}",
                        f"{float(date_group.get('total_amount') or 0):.2f}",
                    ],
                    True,
                    "total",
                )
            )
        self._fill_simple_rows(rows, amount_start=1)

    def _populate_date_service_details_table(self, report: dict) -> None:
        self._configure_date_service_detail_headers()
        rows: list[tuple[list[str], bool, str]] = []
        for date_idx, date_group in enumerate(report.get("date_groups") or []):
            if date_idx > 0:
                rows.append((["", "", "", "", "", "", ""], False, "spacer"))
            rows.append(
                (
                    [f"Date: {date_group.get('bill_date') or '—'}", "", "", "", "", "", ""],
                    True,
                    "doctor",
                )
            )
            for svc in date_group.get("services") or []:
                rows.append(
                    (
                        [f"Service: {svc.get('service_name') or '—'}", "", "", "", "", "", ""],
                        True,
                        "date",
                    )
                )
                for row in svc.get("rows") or []:
                    rows.append(
                        (
                            [
                                row.get("bill_no") or "",
                                row.get("patient_no") or "",
                                row.get("payment_mode") or "—",
                                f"{float(row.get('original_rate') or 0):.2f}",
                                f"{float(row.get('hospital_amount') or 0):.2f}",
                                f"{float(row.get('doctor_amount') or 0):.2f}",
                                f"{float(row.get('total_amount') or 0):.2f}",
                            ],
                            False,
                            "data",
                        )
                    )
                rows.append(
                    (
                        [
                            "Service Total",
                            "",
                            "",
                            "",
                            f"{float(svc.get('hospital_amount') or 0):.2f}",
                            f"{float(svc.get('doctor_amount') or 0):.2f}",
                            f"{float(svc.get('total_amount') or 0):.2f}",
                        ],
                        True,
                        "total",
                    )
                )
            rows.append(
                (
                    [
                        "Date Total",
                        "",
                        "",
                        "",
                        f"{float(date_group.get('hospital_amount') or 0):.2f}",
                        f"{float(date_group.get('doctor_amount') or 0):.2f}",
                        f"{float(date_group.get('total_amount') or 0):.2f}",
                    ],
                    True,
                    "total",
                )
            )
        self._fill_simple_rows(rows, amount_start=3)

    def _fill_simple_rows(self, rows: list[tuple[list[str], bool, str]], *, amount_start: int) -> None:
        col_count = self.table.columnCount()
        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for row_idx, (values, is_bold, style) in enumerate(rows):
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_bold:
                    item.setFont(bold)
                if style == "doctor":
                    item.setBackground(QColor("#dbeafe"))
                elif style == "date":
                    item.setBackground(QColor("#e2e8f0"))
                elif style == "total":
                    item.setBackground(QColor("#fef3c7"))
                elif style == "spacer":
                    item.setBackground(QColor("#f8fafc"))
                if col_idx >= amount_start and value and style not in {"doctor", "date"}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)
            if style in {"doctor", "date", "spacer"}:
                self.table.setSpan(row_idx, 0, 1, col_count)
            if style == "spacer":
                self.table.setRowHeight(row_idx, 10)
        self._apply_column_drag()

    def _populate_normal_table(self, report: dict) -> None:
        self._configure_normal_headers()
        rows: list[tuple[str, list[str], bool, str]] = []

        def add_section(label: str) -> None:
            rows.append(("section", [label, "", "", "", "", "", "", ""], True, "doctor"))

        def add_subsection(label: str) -> None:
            rows.append(("section", [label, "", "", "", "", "", "", ""], True, "date"))

        def add_total(values: list[str]) -> None:
            rows.append(("total", values, True, "total"))

        def add_data(values: list[str]) -> None:
            rows.append(("data", values, False, "data"))

        doctor_groups = list(report.get("doctors") or [])
        for doctor_idx, doctor_group in enumerate(doctor_groups):
            if doctor_idx > 0:
                rows.append(("spacer", ["", "", "", "", "", "", "", ""], False, "spacer"))
            add_section(f"Doctor: {doctor_group.get('doctor_name') or '—'}")
            for date_group in doctor_group.get("date_groups") or []:
                add_subsection(f"Date: {date_group.get('bill_date')}")
                for row in date_group.get("rows") or []:
                    add_data(
                        [
                            str(date_group.get("bill_date") or ""),
                            row.get("bill_no") or "",
                            row.get("patient_no") or "",
                            row.get("payment_mode") or "—",
                            row.get("service_name") or "",
                            f"{float(row.get('original_rate') or 0):.2f}",
                            f"{float(row.get('hospital_amount') or 0):.2f}",
                            f"{float(row.get('doctor_amount') or 0):.2f}",
                        ]
                    )
                add_total(
                    [
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        f"{float(date_group.get('hospital_amount') or 0):.2f}",
                        f"{float(date_group.get('doctor_amount') or 0):.2f}",
                    ]
                )
            add_total(
                [
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    f"{float(doctor_group.get('grand_hospital_amount') or 0):.2f}",
                    f"{float(doctor_group.get('grand_doctor_amount') or 0):.2f}",
                ]
            )
            add_section(
                f"Service Summary — {doctor_group.get('doctor_name') or 'Doctor'} "
                f"({report.get('from_date')} to {report.get('to_date')})"
            )
            for row in doctor_group.get("service_summary") or []:
                add_data(
                    [
                        "",
                        "",
                        "",
                        "",
                        row.get("service_name") or "",
                        f"{float(row.get('total_amount') or 0):.2f}",
                        f"{float(row.get('hospital_amount') or 0):.2f}",
                        f"{float(row.get('doctor_amount') or 0):.2f}",
                    ]
                )

        col_count = self.table.columnCount()
        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for row_idx, (_kind, values, is_bold, style) in enumerate(rows):
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_bold:
                    item.setFont(bold)
                if style == "doctor":
                    item.setBackground(QColor("#dbeafe"))
                elif style == "date":
                    item.setBackground(QColor("#e2e8f0"))
                elif style == "total":
                    item.setBackground(QColor("#fef3c7"))
                elif style == "spacer":
                    item.setBackground(QColor("#f8fafc"))
                if col_idx >= 5 and value:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)
            if style == "doctor":
                self.table.setSpan(row_idx, 0, 1, col_count)
            elif style == "spacer":
                self.table.setSpan(row_idx, 0, 1, col_count)
                self.table.setRowHeight(row_idx, 10)

        self._apply_column_drag()

    def _populate_column_table(self, report: dict) -> None:
        service_columns = list(report.get("service_columns") or [])
        self._configure_column_headers(service_columns)
        service_ids = [str(col.get("service_id") or "") for col in service_columns]
        amount_start_col = 5
        total_col = amount_start_col + len(service_ids)
        col_count = total_col + 1

        rows: list[tuple[list[str], bool, str]] = []

        doctor_groups = list(report.get("doctors") or [])
        for doctor_idx, doctor_group in enumerate(doctor_groups):
            if doctor_idx > 0:
                rows.append(([""] * col_count, False, "spacer"))

            header_cells = [f"Doctor: {doctor_group.get('doctor_name') or '—'}"] + (
                [""] * (col_count - 1)
            )
            rows.append((header_cells, True, "doctor"))

            for row in doctor_group.get("rows") or []:
                amounts = row.get("amounts") or {}
                cells = [
                    str(row.get("bill_date") or ""),
                    row.get("bill_no") or "",
                    row.get("patient_no") or "",
                    row.get("patient_name") or "",
                    row.get("payment_mode") or "—",
                ]
                for service_id in service_ids:
                    raw = amounts.get(service_id)
                    try:
                        value = float(raw or 0)
                    except (TypeError, ValueError):
                        value = 0.0
                    cells.append(f"{value:.2f}" if value else "")
                cells.append(f"{float(row.get('total_amount') or 0):.2f}")
                rows.append((cells, False, "data"))

            column_totals = doctor_group.get("column_totals") or {}
            total_cells = ["", "", "", "", "Doctor Total"]
            for service_id in service_ids:
                total_cells.append(f"{float(column_totals.get(service_id) or 0):.2f}")
            total_cells.append(f"{float(doctor_group.get('grand_total_amount') or 0):.2f}")
            rows.append((total_cells, True, "total"))

        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for row_idx, (values, is_bold, style) in enumerate(rows):
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_bold or col_idx == total_col:
                    item.setFont(bold)
                if style == "doctor":
                    item.setBackground(QColor("#dbeafe"))
                elif style == "total":
                    item.setBackground(QColor("#fef3c7"))
                elif style == "spacer":
                    item.setBackground(QColor("#f8fafc"))
                if col_idx >= amount_start_col and value:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row_idx, col_idx, item)
            if style in {"doctor", "spacer"}:
                self.table.setSpan(row_idx, 0, 1, col_count)
            if style == "spacer":
                self.table.setRowHeight(row_idx, 12)

        self._apply_column_drag()

    def _print_report(self) -> None:
        if not self._report:
            QMessageBox.information(self, "Print", "Load the report first.")
            return
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        doctor_ids = self._effective_doctor_ids()
        payment_modes = self._effective_payment_modes()
        service_ids = self._effective_service_ids()
        report_type = self._selected_report_type()
        endpoint = self.api.doctor_collection_report_endpoint(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=service_ids,
            payment_modes=payment_modes,
            report_type=report_type,
        )
        titles = {
            self.REPORT_DAY_WISE: "Doctor wise Day wise Collection Summary",
            self.REPORT_PAYMENT_MODE: "Payment Mode wise Doctor Collection",
            self.REPORT_SHARING: "Doctor wise Sharing Report",
            self.REPORT_COLUMN: "Doctor wise Collection Report (Column wise)",
            self.REPORT_DATE_SERVICE_SUMMARY: "Date wise Service wise Collection Summary",
            self.REPORT_DATE_SERVICE_DETAILS: "Date wise Service wise Collection Details",
        }
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title=titles.get(report_type, "Doctor wise Collection Report"),
            report_code="DOCTOR_COLLECTION",
        )
