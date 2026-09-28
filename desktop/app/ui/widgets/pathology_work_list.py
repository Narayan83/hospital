from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from app.ui.print_utils import preview_report, print_report
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE


class PathologyWorkListWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Pathology Work List")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Bill Date"))
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        filter_row.addWidget(self.bill_date)
        filter_row.addStretch()
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        action_row = QHBoxLayout()
        for label, handler in (
            ("New Bill", lambda: self._navigate("pathology_bill")),
            ("Enter Results", self._enter_results),
            ("Mark Report Ready", self._authorize_selected),
            ("Preview Report", self._preview_report),
            ("Print Report", self._print_report),
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(HEADER_BTN_STYLE)
            btn.clicked.connect(handler)
            action_row.addWidget(btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Bill No",
                "Sample No",
                "Patient",
                "Tests",
                "Pending",
                "Status",
                "Net",
                "Referring Dr",
                "Bill Date",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._enter_results)
        layout.addWidget(self.table, stretch=1)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

    def build_header_actions(self) -> QWidget:
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("Pathology Bill", lambda: self._navigate("pathology_bill")),
                ("Lab Tests", lambda: self._navigate("service_creation_pathology")),
                ("Test Profiles", lambda: self._navigate("parameter_mapping")),
                ("Templates", lambda: self._navigate("custom_template_creation")),
                ("Reference Ranges", lambda: self._navigate("normal_range_creation")),
            ]
        )

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _selected_row(self) -> dict | None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Select", "Select a work list row first.")
            return None
        cell = self.table.item(sel[0].row(), 0)
        if not cell:
            return None
        return cell.data(Qt.ItemDataRole.UserRole)

    @staticmethod
    def _sort_result_rows(results: list[dict]) -> list[dict]:
        """Same order everywhere: bundle group, then member order inside the bundle."""
        return sorted(
            results or [],
            key=lambda item: (
                int(item.get("panel_group_order") if item.get("panel_group_order") is not None else 10**9),
                int(item.get("bill_line_sort_order") if item.get("bill_line_sort_order") is not None else 10**9),
                int(item.get("sort_order") if item.get("sort_order") is not None else 10**9),
                str(item.get("id") or ""),
            ),
        )

    def _enter_results(self) -> None:
        row = self._selected_row()
        if not row or not row.get("bill_id"):
            return
        try:
            order = self.api.get_pathology_order(row["bill_id"])
        except ApiError as exc:
            QMessageBox.warning(self, "Results", str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Enter Results — {row.get('bill_no')}")
        dialog.resize(900, 520)
        vbox = QVBoxLayout(dialog)
        info = QFormLayout()
        patient_lbl = QLabel(order.get("patient_name") or "")
        sample_lbl = QLabel(order.get("sample_no") or "—")
        status_lbl = QLabel((order.get("status") or "").replace("_", " ").title())
        info.addRow("Patient", patient_lbl)
        info.addRow("Sample No", sample_lbl)
        info.addRow("Status", status_lbl)
        vbox.addLayout(info)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Test / Parameter", "Result", "Unit", "Ref. Range", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(True)

        template_row = QHBoxLayout()
        template_row.addWidget(QLabel("Custom Template"))
        template_combo = QComboBox()
        template_combo.addItem("— Select template —", None)
        template_row.addWidget(template_combo, stretch=1)
        apply_btn = QPushButton("Apply to Selected Row")
        apply_btn.setEnabled(False)
        template_row.addWidget(apply_btn)
        vbox.addLayout(template_row)

        row_meta: list[dict] = []

        def _fill_table(order_data: dict) -> None:
            """Always rebuild rows in bundle/member order (open, save, reopen)."""
            results = self._sort_result_rows(order_data.get("results") or [])
            row_meta.clear()
            table.clearContents()
            table.setRowCount(len(results))
            for idx, item in enumerate(results):
                label = item.get("parameter_name") or item.get("service_name") or ""
                if item.get("service_name") and item.get("parameter_name"):
                    label = f"{item.get('service_name')} — {item.get('parameter_name')}"
                meta = {
                    "id": item.get("id"),
                    "parameter_id": item.get("parameter_id"),
                    "service_id": item.get("service_id"),
                }
                row_meta.append(meta)
                name_item = QTableWidgetItem(label)
                name_item.setData(Qt.ItemDataRole.UserRole, meta["id"])
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 0, name_item)
                table.setItem(idx, 1, QTableWidgetItem(item.get("result_value") or ""))
                unit_item = QTableWidgetItem(item.get("unit_name") or "")
                unit_item.setFlags(unit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 2, unit_item)
                range_item = QTableWidgetItem(item.get("reference_range_text") or "")
                range_item.setFlags(range_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 3, range_item)
                status_item = QTableWidgetItem(item.get("status") or "pending")
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 4, status_item)
                table.setVerticalHeaderItem(idx, QTableWidgetItem(str(idx + 1)))
            status_lbl.setText((order_data.get("status") or "").replace("_", " ").title())
            dialog.setWindowTitle(
                f"Enter Results — {row.get('bill_no')} ({order_data.get('status') or ''})"
            )

        def _load_templates_for_row(row_index: int) -> None:
            template_combo.clear()
            template_combo.addItem("— Select template —", None)
            if row_index < 0 or row_index >= len(row_meta):
                apply_btn.setEnabled(False)
                return
            meta = row_meta[row_index]
            try:
                templates = self.api.list_pathology_result_templates(
                    parameter_id=meta.get("parameter_id"),
                    service_id=meta.get("service_id"),
                )
            except ApiError:
                templates = []
            for tmpl in templates:
                template_combo.addItem(f"{tmpl.get('code')} — {tmpl.get('name')}", tmpl)
            apply_btn.setEnabled(bool(templates))

        def _apply_template() -> None:
            sel = table.selectionModel().selectedRows()
            if not sel:
                QMessageBox.information(dialog, "Select Row", "Select a result row first.")
                return
            tmpl = template_combo.currentData()
            if not tmpl:
                QMessageBox.information(dialog, "Select Template", "Choose a template to apply.")
                return
            row_index = sel[0].row()
            table.setItem(row_index, 1, QTableWidgetItem(tmpl.get("body") or ""))

        apply_btn.clicked.connect(_apply_template)
        _fill_table(order)

        table.selectionModel().selectionChanged.connect(
            lambda *_args: _load_templates_for_row(
                table.selectionModel().selectedRows()[0].row()
                if table.selectionModel().selectedRows()
                else -1
            )
        )
        if table.rowCount():
            table.selectRow(0)
            _load_templates_for_row(0)
        vbox.addWidget(table, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )

        def _save_results() -> None:
            payload = {"results": []}
            for r in range(table.rowCount()):
                result_id = row_meta[r]["id"]
                value = table.item(r, 1).text().strip() if table.item(r, 1) else ""
                payload["results"].append({"id": result_id, "result_value": value or None})
            try:
                updated = self.api.update_pathology_results(row["bill_id"], payload)
                # Rebuild from server order — never map by response index alone.
                _fill_table(updated)
                if table.rowCount():
                    table.selectRow(0)
                    _load_templates_for_row(0)
                self.refresh()
                preview_report(
                    self.api,
                    f"/reports/pathology-report/{row['bill_id']}",
                    parent=dialog,
                    title=f"Pathology Report Preview — {row.get('bill_no')} (Saved)",
                    report_code="PATHOLOGY_REPORT",
                )
            except ApiError as exc:
                QMessageBox.warning(dialog, "Error", str(exc))

        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(_save_results)
        buttons.rejected.connect(dialog.reject)
        vbox.addWidget(buttons)
        dialog.exec()

    def _authorize_selected(self) -> None:
        row = self._selected_row()
        if not row or not row.get("bill_id"):
            return
        if QMessageBox.question(
            self,
            "Mark Report Ready",
            f"Mark report ready for bill {row.get('bill_no')}?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.authorize_pathology_order(row["bill_id"])
            self.refresh()
            QMessageBox.information(self, "Report Ready", "Report marked ready.")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _preview_report(self) -> None:
        row = self._selected_row()
        if row and row.get("bill_id"):
            preview_report(
                self.api,
                f"/reports/pathology-report/{row['bill_id']}",
                parent=self,
                report_code="PATHOLOGY_REPORT",
            )

    def _print_report(self) -> None:
        row = self._selected_row()
        if row and row.get("bill_id"):
            print_report(
                self.api,
                f"/reports/pathology-report/{row['bill_id']}",
                parent=self,
                report_code="PATHOLOGY_REPORT",
            )

    def refresh(self) -> None:
        qd = self.bill_date.date()
        bill_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        try:
            self._rows = self.api.list_pathology_work_list(bill_date=bill_date)
        except ApiError as exc:
            QMessageBox.warning(self, "Work List", str(exc))
            return
        self.table.setRowCount(len(self._rows))
        for row_idx, item in enumerate(self._rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(item.get("bill_no", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(item.get("sample_no") or ""))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item.get("patient_name") or ""))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(item.get("test_count", ""))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(item.get("result_pending", ""))))
            self.table.setItem(
                row_idx,
                5,
                QTableWidgetItem((item.get("order_status") or "").replace("_", " ").title()),
            )
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(item.get("net_amount", ""))))
            self.table.setItem(row_idx, 7, QTableWidgetItem(item.get("referring_doctor") or ""))
            self.table.setItem(row_idx, 8, QTableWidgetItem(str(item.get("bill_date", ""))))
            cell = self.table.item(row_idx, 0)
            if cell:
                cell.setData(Qt.ItemDataRole.UserRole, item)
        self.status.setText(f"{len(self._rows)} pathology order(s) for {bill_date}.")
