"""Lab Test Master — create a lab test with its reference ranges in one screen."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.pathology_display import pathology_item_label

GENDER_OPTIONS = [("All", "A"), ("Male", "M"), ("Female", "F")]
AGE_UNITS = ["years", "months", "weeks", "days"]


class PathologyServiceMasterWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._tests: list[dict] = []
        self._units: list[dict] = []
        self._selected_id: str | None = None
        self._selected_is_panel = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Pathology Services (Tests & Panels)")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)
        hint = QLabel(
            "All pathology services are listed here — single Tests and Panels (bundles). "
            "Tests are edited here with their ranges; Panels are managed on the Bundle / Panel screen."
        )
        hint.setStyleSheet("color: #64748b; margin-bottom: 6px;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left — existing tests
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel("All Pathology Services")
        self.count_label.setStyleSheet("font-weight: bold; color: #334155;")
        left_layout.addWidget(self.count_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or code...")
        self.search.textChanged.connect(self._render_test_list)
        left_layout.addWidget(self.search)
        filter_row = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItem("All", "all")
        self.type_filter.addItem("Tests only", "test")
        self.type_filter.addItem("Panels only", "panel")
        self.type_filter.currentIndexChanged.connect(self._render_test_list)
        filter_row.addWidget(QLabel("Show"))
        filter_row.addWidget(self.type_filter, stretch=1)
        left_layout.addLayout(filter_row)
        self.test_list = QTableWidget(0, 4)
        self.test_list.setHorizontalHeaderLabels(["Name", "Code", "Type", "Price"])
        self.test_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.test_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.test_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.test_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.test_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.test_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.test_list.itemSelectionChanged.connect(self._on_select_test)
        left_layout.addWidget(self.test_list, stretch=1)
        splitter.addWidget(left)

        # Right — form + ranges
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form_box = QGroupBox("Test Details")
        form = QFormLayout(form_box)
        self.name = QLineEdit()
        self.price = QLineEdit("0")
        self.unit = QComboBox()
        self.result_type = QComboBox()
        self.result_type.addItem("Numeric", "numeric")
        self.result_type.addItem("Text", "text")
        self.sub_category = QComboBox()
        for combo in (self.unit, self.result_type, self.sub_category):
            combo.setMinimumWidth(260)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("Name *", self.name)
        form.addRow("Price", self.price)
        form.addRow("Unit", self.unit)
        form.addRow("Result Type", self.result_type)
        form.addRow("Sub Category", self.sub_category)
        right_layout.addWidget(form_box)

        range_box = QGroupBox("Reference Ranges (normal ranges by gender / age)")
        range_layout = QVBoxLayout(range_box)
        self.range_table = QTableWidget(0, 7)
        self.range_table.setHorizontalHeaderLabels(
            ["Gender", "Age From", "Age To", "Age Unit", "Low", "High", "Text Range"]
        )
        rheader = self.range_table.horizontalHeader()
        for col in range(7):
            rheader.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        range_layout.addWidget(self.range_table)
        range_btns = QHBoxLayout()
        range_btns.addWidget(QPushButton("Add Range", clicked=lambda: self._add_range_row()))
        range_btns.addWidget(QPushButton("Remove Range", clicked=self._remove_range_row))
        range_btns.addStretch()
        range_layout.addLayout(range_btns)
        right_layout.addWidget(range_box, stretch=1)

        action_row = QHBoxLayout()
        action_row.addWidget(QPushButton("Save Test", clicked=self._save))
        action_row.addWidget(QPushButton("New", clicked=self._clear))
        action_row.addWidget(QPushButton("Delete", clicked=self._delete))
        action_row.addStretch()
        right_layout.addLayout(action_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 760])

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(26)
        layout.addWidget(self.status)

    # ----- data ----------------------------------------------------------
    def refresh(self) -> None:
        cache = get_session().cache
        self.unit.clear()
        self.unit.addItem("— None —", None)
        try:
            self._units = self.api.list_pathology_units()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            self._units = []
        for unit in self._units:
            self.unit.addItem(unit.get("name", ""), unit.get("id"))

        self.sub_category.clear()
        self.sub_category.addItem("— None —", None)
        lab_id = None
        for cat in cache.service_categories if cache.loaded else []:
            if cat.get("code") == "LAB":
                lab_id = cat.get("id")
                break
        for sub in cache.service_sub_categories if cache.loaded else []:
            if not lab_id or sub.get("category_id") == lab_id:
                self.sub_category.addItem(sub.get("name", ""), sub.get("id"))

        try:
            tests = self.api.list_lab_tests()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            tests = []
        try:
            panels = self.api.list_lab_profiles()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            panels = []
        self._tests = [{**t, "_kind": "test"} for t in tests] + [
            {**p, "_kind": "panel"} for p in panels
        ]
        n_tests = len(tests)
        n_panels = len(panels)
        self.count_label.setText(
            f"All Pathology Services — {n_tests + n_panels}  "
            f"(Tests: {n_tests} | Panels: {n_panels})"
        )
        self._render_test_list()

    def _render_test_list(self) -> None:
        query = self.search.text().strip().lower()
        type_filter = self.type_filter.currentData() if hasattr(self, "type_filter") else "all"
        rows = []
        for t in self._tests:
            if type_filter != "all" and t.get("_kind") != type_filter:
                continue
            if query:
                kind = "panel" if t.get("_kind") == "panel" else "test"
                haystack = " ".join(
                    [
                        str(t.get("name") or ""),
                        str(t.get("code") or ""),
                        kind,
                        str(t.get("price") or ""),
                    ]
                ).lower()
                if query not in haystack:
                    continue
            rows.append(t)
        self.test_list.setRowCount(len(rows))
        for row, test in enumerate(rows):
            is_panel = test.get("_kind") == "panel"
            name_item = QTableWidgetItem(test.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, test.get("id"))
            self.test_list.setItem(row, 0, name_item)
            self.test_list.setItem(row, 1, QTableWidgetItem(test.get("code") or ""))
            type_item = QTableWidgetItem("Panel" if is_panel else "Test")
            self.test_list.setItem(row, 2, type_item)
            self.test_list.setItem(row, 3, QTableWidgetItem(str(test.get("price", ""))))

    def _on_select_test(self) -> None:
        items = self.test_list.selectedItems()
        if not items:
            return
        test_id = self.test_list.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        test = next((t for t in self._tests if t.get("id") == test_id), None)
        if not test:
            return
        self._selected_id = test_id
        self._selected_is_panel = test.get("_kind") == "panel"
        self.name.setText(test.get("name", ""))
        self.price.setText(str(test.get("price", "0")))
        sidx = self.sub_category.findData(test.get("sub_category_id"))
        self.sub_category.setCurrentIndex(sidx if sidx >= 0 else 0)

        if self._selected_is_panel:
            members = ", ".join(
                (m.get("name") or "") for m in (test.get("members") or [])
            )
            self.unit.setCurrentIndex(0)
            self.result_type.setCurrentIndex(0)
            self.range_table.setRowCount(0)
            self._set_test_fields_enabled(False)
            self.status.setText(
                f"Panel: {test.get('name')} — members: {members or 'none'}. "
                "Edit members on the Bundle / Panel screen."
            )
            return

        self._set_test_fields_enabled(True)
        uidx = self.unit.findData(test.get("unit_id"))
        self.unit.setCurrentIndex(uidx if uidx >= 0 else 0)
        ridx = self.result_type.findData(test.get("result_type", "numeric"))
        self.result_type.setCurrentIndex(ridx if ridx >= 0 else 0)
        self.range_table.setRowCount(0)
        for rng in test.get("ranges") or []:
            self._add_range_row(rng)
        self.status.setText(f"Editing: {test.get('name')}")

    def _set_test_fields_enabled(self, enabled: bool) -> None:
        """Panels have no unit/result-type/ranges; disable those when a panel is shown."""
        self.unit.setEnabled(enabled)
        self.result_type.setEnabled(enabled)
        self.range_table.setEnabled(enabled)

    # ----- ranges grid ---------------------------------------------------
    def _add_range_row(self, data: dict | None = None) -> None:
        data = data or {}
        row = self.range_table.rowCount()
        self.range_table.insertRow(row)

        gender_combo = QComboBox()
        for label, value in GENDER_OPTIONS:
            gender_combo.addItem(label, value)
        gidx = gender_combo.findData(data.get("gender", "A"))
        gender_combo.setCurrentIndex(gidx if gidx >= 0 else 0)
        self.range_table.setCellWidget(row, 0, gender_combo)

        self.range_table.setItem(row, 1, QTableWidgetItem(str(data.get("age_from", 0))))
        self.range_table.setItem(row, 2, QTableWidgetItem(str(data.get("age_to", 120))))

        unit_combo = QComboBox()
        unit_combo.addItems(AGE_UNITS)
        unit_combo.setCurrentText(data.get("age_unit", "years"))
        self.range_table.setCellWidget(row, 3, unit_combo)

        self.range_table.setItem(row, 4, QTableWidgetItem(self._fmt(data.get("low"))))
        self.range_table.setItem(row, 5, QTableWidgetItem(self._fmt(data.get("high"))))
        self.range_table.setItem(row, 6, QTableWidgetItem(data.get("text_range") or ""))

    @staticmethod
    def _fmt(value: object) -> str:
        return "" if value is None else str(value)

    def _remove_range_row(self) -> None:
        row = self.range_table.currentRow()
        if row >= 0:
            self.range_table.removeRow(row)

    def _collect_ranges(self) -> list[dict]:
        ranges: list[dict] = []
        for row in range(self.range_table.rowCount()):
            gender = self.range_table.cellWidget(row, 0).currentData()
            age_from = self._int(self.range_table.item(row, 1), 0)
            age_to = self._int(self.range_table.item(row, 2), 120)
            age_unit = self.range_table.cellWidget(row, 3).currentText()
            low = self._text(self.range_table.item(row, 4))
            high = self._text(self.range_table.item(row, 5))
            text_range = self._text(self.range_table.item(row, 6))
            if not low and not high and not text_range:
                continue
            ranges.append(
                {
                    "gender": gender,
                    "age_from": age_from,
                    "age_to": age_to,
                    "age_unit": age_unit,
                    "low": low or None,
                    "high": high or None,
                    "text_range": text_range or None,
                }
            )
        return ranges

    @staticmethod
    def _int(item: QTableWidgetItem | None, default: int) -> int:
        if not item:
            return default
        try:
            return int(float(item.text().strip()))
        except ValueError:
            return default

    @staticmethod
    def _text(item: QTableWidgetItem | None) -> str:
        return item.text().strip() if item else ""

    # ----- save / delete -------------------------------------------------
    def _save(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Validation", "Test name is required.")
            return
        if self._selected_is_panel:
            try:
                self.api.update_lab_profile(
                    self._selected_id,
                    {
                        "name": self.name.text().strip(),
                        "price": self.price.text().strip() or "0",
                        "sub_category_id": self.sub_category.currentData(),
                        "member_test_ids": [
                            m.get("id")
                            for t in self._tests
                            if t.get("id") == self._selected_id
                            for m in (t.get("members") or [])
                        ],
                    },
                )
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
            self.status.setText(f"Saved panel: {self.name.text().strip()}")
            self._clear()
            self.refresh()
            return
        payload = {
            "name": self.name.text().strip(),
            "price": self.price.text().strip() or "0",
            "unit_id": self.unit.currentData(),
            "result_type": self.result_type.currentData(),
            "sub_category_id": self.sub_category.currentData(),
            "ranges": self._collect_ranges(),
        }
        try:
            if self._selected_id:
                self.api.update_lab_test(self._selected_id, payload)
            else:
                self.api.create_lab_test(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.status.setText(f"Saved: {payload['name']}")
        self._clear()
        self.refresh()

    def _delete(self) -> None:
        if not self._selected_id:
            QMessageBox.warning(self, "Validation", "Select a test to delete.")
            return
        kind = "panel" if self._selected_is_panel else "lab test"
        if QMessageBox.question(self, "Confirm", f"Delete this {kind}?") != QMessageBox.StandardButton.Yes:
            return
        try:
            if self._selected_is_panel:
                self.api.delete_lab_profile(self._selected_id)
            else:
                self.api.delete_lab_test(self._selected_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._clear()
        self.refresh()

    def _clear(self) -> None:
        self._selected_id = None
        self._selected_is_panel = False
        self._set_test_fields_enabled(True)
        self.test_list.clearSelection()
        self.name.clear()
        self.price.setText("0")
        self.unit.setCurrentIndex(0)
        self.result_type.setCurrentIndex(0)
        self.sub_category.setCurrentIndex(0)
        self.range_table.setRowCount(0)
        self.status.setText("Ready for a new test.")
