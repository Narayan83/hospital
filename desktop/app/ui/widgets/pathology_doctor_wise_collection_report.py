from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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


class PathologyDoctorWiseCollectionReportWidget(QWidget):
    REPORT_NORMAL = "normal"
    REPORT_COLUMN = "column_wise"
    REPORT_REFERRAL = "referral_wise"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._doctors: list[dict] = []
        self._doctor_checks: list[tuple[str, QCheckBox]] = []
        self._referral_checks: list[tuple[str, QCheckBox]] = []
        self._report: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Pathology Doctor wise Collection Report")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Normal report groups pathology bills by pathologist. "
            "Column wise uses services marked “Doctor Collection Column = Y”. "
            "Reference doctor wise is a bill summary (one row per bill, bill net amount) "
            "grouped by reference doctor (from / to date)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate())
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.report_type = QComboBox()
        self.report_type.addItem("Normal report (Pathologist wise)", self.REPORT_NORMAL)
        self.report_type.addItem("Column wise report", self.REPORT_COLUMN)
        self.report_type.addItem("Reference doctor wise report", self.REPORT_REFERRAL)
        self.report_type.currentIndexChanged.connect(self._on_report_type_changed)
        for field in (self.from_date, self.to_date, self.report_type):
            field.setMaximumWidth(280)
            field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        form.addRow("From Date", self.from_date)
        form.addRow("To Date", self.to_date)
        form.addRow("Report Type", self.report_type)
        layout.addWidget(filters)

        self.doctor_box = QGroupBox("Pathologists")
        doctor_layout = QVBoxLayout(self.doctor_box)
        self.select_all_doctors = QCheckBox("All Pathologists")
        self.select_all_doctors.setChecked(True)
        self.select_all_doctors.stateChanged.connect(self._toggle_all_doctors)
        doctor_layout.addWidget(self.select_all_doctors)

        doctor_scroll = QScrollArea()
        doctor_scroll.setWidgetResizable(True)
        doctor_scroll.setMaximumHeight(140)
        self.doctor_host = QWidget()
        self.doctor_list_layout = QVBoxLayout(self.doctor_host)
        doctor_scroll.setWidget(self.doctor_host)
        doctor_layout.addWidget(doctor_scroll)
        layout.addWidget(self.doctor_box)

        self.referral_box = QGroupBox("Reference Doctors")
        referral_layout = QVBoxLayout(self.referral_box)
        self.select_all_referrals = QCheckBox("All Reference Doctors")
        self.select_all_referrals.setChecked(True)
        self.select_all_referrals.stateChanged.connect(self._toggle_all_referrals)
        referral_layout.addWidget(self.select_all_referrals)

        referral_scroll = QScrollArea()
        referral_scroll.setWidgetResizable(True)
        referral_scroll.setMaximumHeight(140)
        self.referral_host = QWidget()
        self.referral_list_layout = QVBoxLayout(self.referral_host)
        referral_scroll.setWidget(self.referral_host)
        referral_layout.addWidget(referral_scroll)
        self.referral_hint = QLabel(
            "Bill summary by reference doctor name (one bill = one row, bill net amount). "
            "Load list using the selected from / to dates."
        )
        self.referral_hint.setWordWrap(True)
        self.referral_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        referral_layout.addWidget(self.referral_hint)
        layout.addWidget(self.referral_box)
        self.referral_box.hide()

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

        self.table = QTableWidget(0, 8)
        self.table.setProperty("hmsNoStretch", True)
        self._configure_normal_headers(is_referral=False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.summary = QLabel("Select filters and load the report.")
        self.summary.setStyleSheet("color: #475569; font-weight: bold;")
        layout.addWidget(self.summary)

    def _selected_report_type(self) -> str:
        return str(self.report_type.currentData() or self.REPORT_NORMAL)

    def _on_report_type_changed(self) -> None:
        is_referral = self._selected_report_type() == self.REPORT_REFERRAL
        self.doctor_box.setVisible(not is_referral)
        self.referral_box.setVisible(is_referral)
        if is_referral:
            self._load_referrals()

    def _apply_column_drag(self) -> None:
        self.table.setProperty("hmsNoStretch", True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        enable_column_resize(self.table)

    def _configure_normal_headers(self, *, is_referral: bool) -> None:
        self.table.clearSpans()
        mid_label = "Pathologist" if is_referral else "Referring Doctor"
        if is_referral:
            self.table.setColumnCount(7)
            self.table.setHorizontalHeaderLabels(
                [
                    "Date",
                    "Bill No",
                    "Patient Id",
                    "Patient Name",
                    mid_label,
                    "Payment Mode",
                    "Bill Amount",
                ]
            )
        else:
            self.table.setColumnCount(8)
            self.table.setHorizontalHeaderLabels(
                [
                    "Date",
                    "Bill No",
                    "Patient Id",
                    "Patient Name",
                    mid_label,
                    "Payment Mode",
                    "Service",
                    "Amount",
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
        report_type = self._selected_report_type()
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()

        doctor_ids = None
        referral_names = None
        if report_type == self.REPORT_REFERRAL:
            self._load_referrals()
            referral_names = (
                None
                if self.select_all_referrals.isChecked()
                else self._selected_referral_names()
            )
            if referral_names is not None and not referral_names:
                QMessageBox.warning(
                    self,
                    "Reference Doctors",
                    "Select at least one reference doctor or choose All Reference Doctors.",
                )
                return
        else:
            self._load_doctors_if_needed()
            doctor_ids = (
                None if self.select_all_doctors.isChecked() else self._selected_doctor_ids()
            )
            if doctor_ids is not None and not doctor_ids:
                QMessageBox.warning(
                    self,
                    "Pathologists",
                    "Select at least one pathologist or choose All Pathologists.",
                )
                return

        try:
            self._report = self.api.get_pathology_collection_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                referral_names=referral_names,
                report_type=report_type,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Report", str(exc))
            return

        if report_type == self.REPORT_COLUMN:
            self._populate_column_table(self._report)
            service_columns = self._report.get("service_columns") or []
            if not service_columns:
                self.summary.setText(
                    "No services marked for columns. Set “Doctor Collection Column = Y” "
                    "in Patient Service Master."
                )
            else:
                group_count = len(self._report.get("groups") or [])
                self.summary.setText(
                    f"Separate sections for {group_count} pathologist(s). "
                    f"Overall Total: {float(self._report.get('overall_total_amount') or 0):.2f}"
                )
        else:
            self._populate_normal_table(
                self._report,
                is_referral=(report_type == self.REPORT_REFERRAL),
            )
            label = "reference doctor(s)" if report_type == self.REPORT_REFERRAL else "pathologist(s)"
            group_count = len(self._report.get("groups") or [])
            self.summary.setText(
                f"{group_count} {label}. "
                f"Overall Total: {float(self._report.get('overall_total_amount') or 0):.2f}"
            )

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
        while self.doctor_list_layout.count():
            item = self.doctor_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._doctor_checks = []
        for doctor in self._doctors:
            label = doctor.get("full_name") or doctor.get("doctor_code") or doctor.get("id")
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._sync_select_all_doctors)
            self._doctor_checks.append((doctor.get("id"), checkbox))
            self.doctor_list_layout.addWidget(checkbox)

    def _load_referrals(self) -> None:
        from_date = self.from_date.date().toPython().isoformat()
        to_date = self.to_date.date().toPython().isoformat()
        try:
            names = self.api.list_pathology_referring_doctors(
                from_date=from_date,
                to_date=to_date,
            )
        except ApiError:
            names = []

        while self.referral_list_layout.count():
            item = self.referral_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._referral_checks = []
        for name in names:
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._sync_select_all_referrals)
            self._referral_checks.append((name, checkbox))
            self.referral_list_layout.addWidget(checkbox)
        if not names:
            empty = QLabel("No referring doctors found for the selected dates.")
            empty.setStyleSheet("color: #94a3b8;")
            self.referral_list_layout.addWidget(empty)

    def _selected_doctor_ids(self) -> list[str]:
        return [
            doctor_id
            for doctor_id, checkbox in self._doctor_checks
            if checkbox.isChecked() and doctor_id
        ]

    def _selected_referral_names(self) -> list[str]:
        return [
            name for name, checkbox in self._referral_checks if checkbox.isChecked() and name
        ]

    def _toggle_all_doctors(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        for _, checkbox in self._doctor_checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

    def _toggle_all_referrals(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        for _, checkbox in self._referral_checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

    def _sync_select_all_doctors(self) -> None:
        if not self._doctor_checks:
            return
        all_checked = all(checkbox.isChecked() for _, checkbox in self._doctor_checks)
        self.select_all_doctors.blockSignals(True)
        self.select_all_doctors.setChecked(all_checked)
        self.select_all_doctors.blockSignals(False)

    def _sync_select_all_referrals(self) -> None:
        if not self._referral_checks:
            return
        all_checked = all(checkbox.isChecked() for _, checkbox in self._referral_checks)
        self.select_all_referrals.blockSignals(True)
        self.select_all_referrals.setChecked(all_checked)
        self.select_all_referrals.blockSignals(False)

    def _populate_normal_table(self, report: dict, *, is_referral: bool) -> None:
        self._configure_normal_headers(is_referral=is_referral)
        rows: list[tuple[str, list[str], bool, str]] = []
        col_count = 7 if is_referral else 8
        amount_col = col_count - 1

        def add_section(label: str) -> None:
            rows.append(("section", [label] + [""] * (col_count - 1), True, "doctor"))

        def add_subsection(label: str) -> None:
            rows.append(("section", [label] + [""] * (col_count - 1), True, "date"))

        def add_total(values: list[str]) -> None:
            rows.append(("total", values, True, "total"))

        def add_data(values: list[str]) -> None:
            rows.append(("data", values, False, "data"))

        group_label = "Reference Doctor" if is_referral else "Pathologist"
        groups = list(report.get("groups") or [])
        for group_idx, group in enumerate(groups):
            if group_idx > 0:
                rows.append(("spacer", [""] * col_count, False, "spacer"))
            add_section(f"{group_label}: {group.get('group_name') or '—'}")
            for date_group in group.get("date_groups") or []:
                add_subsection(f"Date: {date_group.get('bill_date')}")
                for row in date_group.get("rows") or []:
                    mid = (
                        row.get("pathologist_name")
                        if is_referral
                        else row.get("referring_doctor")
                    ) or "—"
                    if is_referral:
                        add_data(
                            [
                                str(date_group.get("bill_date") or ""),
                                row.get("bill_no") or "",
                                row.get("patient_no") or "",
                                row.get("patient_name") or "",
                                mid,
                                row.get("payment_mode") or "—",
                                f"{float(row.get('amount') or 0):.2f}",
                            ]
                        )
                    else:
                        add_data(
                            [
                                str(date_group.get("bill_date") or ""),
                                row.get("bill_no") or "",
                                row.get("patient_no") or "",
                                row.get("patient_name") or "",
                                mid,
                                row.get("payment_mode") or "—",
                                row.get("service_name") or "",
                                f"{float(row.get('amount') or 0):.2f}",
                            ]
                        )
                if is_referral:
                    add_total(
                        [
                            "",
                            "",
                            "",
                            "",
                            "",
                            "Date Total",
                            f"{float(date_group.get('total_amount') or 0):.2f}",
                        ]
                    )
                else:
                    add_total(
                        [
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "Date Total",
                            f"{float(date_group.get('total_amount') or 0):.2f}",
                        ]
                    )
            if is_referral:
                add_total(
                    [
                        "",
                        "",
                        "",
                        "",
                        "",
                        f"{group_label} Total",
                        f"{float(group.get('grand_total_amount') or 0):.2f}",
                    ]
                )
            else:
                add_total(
                    [
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        f"{group_label} Total",
                        f"{float(group.get('grand_total_amount') or 0):.2f}",
                    ]
                )
                add_section(
                    f"Service Summary — {group.get('group_name') or group_label} "
                    f"({report.get('from_date')} to {report.get('to_date')})"
                )
                for row in group.get("service_summary") or []:
                    add_data(
                        [
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            row.get("service_name") or "",
                            f"{float(row.get('total_amount') or 0):.2f}",
                        ]
                    )

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
                if col_idx == amount_col and value:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row_idx, col_idx, item)
            if style in {"doctor", "spacer"}:
                self.table.setSpan(row_idx, 0, 1, col_count)
            if style == "spacer":
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
        groups = list(report.get("groups") or [])
        for group_idx, group in enumerate(groups):
            if group_idx > 0:
                rows.append(([""] * col_count, False, "spacer"))

            header_cells = [f"Pathologist: {group.get('group_name') or '—'}"] + (
                [""] * (col_count - 1)
            )
            rows.append((header_cells, True, "doctor"))

            for row in group.get("rows") or []:
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

            column_totals = group.get("column_totals") or {}
            total_cells = ["", "", "", "", "Pathologist Total"]
            for service_id in service_ids:
                total_cells.append(f"{float(column_totals.get(service_id) or 0):.2f}")
            total_cells.append(f"{float(group.get('grand_total_amount') or 0):.2f}")
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
        report_type = self._selected_report_type()
        doctor_ids = None
        referral_names = None
        if report_type == self.REPORT_REFERRAL:
            referral_names = (
                None
                if self.select_all_referrals.isChecked()
                else self._selected_referral_names()
            )
        else:
            doctor_ids = (
                None if self.select_all_doctors.isChecked() else self._selected_doctor_ids()
            )
        endpoint = self.api.pathology_collection_report_endpoint(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            referral_names=referral_names,
            report_type=report_type,
        )
        if report_type == self.REPORT_COLUMN:
            title = "Pathology Doctor wise Collection Report (Column wise)"
        elif report_type == self.REPORT_REFERRAL:
            title = "Pathology Reference Doctor wise Collection Report"
        else:
            title = "Pathology Doctor wise Collection Report"
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title=title,
            report_code="DOCTOR_COLLECTION",
        )
