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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.pathology_display import pathology_item_label


class PathologyNormalRangeMasterWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._parameters: list[dict] = []
        self._units: list[dict] = []
        self._ranges: list[dict] = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Reference Ranges")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)

        form_box = QGroupBox("Reference Range")
        form = QFormLayout(form_box)
        self.parameter = QComboBox()
        self.gender = QComboBox()
        self.gender.addItem("All", "A")
        self.gender.addItem("Male", "M")
        self.gender.addItem("Female", "F")
        self.age_from = QSpinBox()
        self.age_from.setRange(0, 120)
        self.age_to = QSpinBox()
        self.age_to.setRange(0, 120)
        self.age_to.setValue(120)
        self.min_value = QLineEdit()
        self.max_value = QLineEdit()
        self.text_range = QLineEdit()
        self.text_range.setPlaceholderText("Optional text range e.g. Negative")
        self.unit = QComboBox()
        for combo in (self.parameter, self.gender, self.unit):
            combo.setMinimumWidth(260)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("Test *", self.parameter)
        form.addRow("Gender", self.gender)
        form.addRow("Age From (Years)", self.age_from)
        form.addRow("Age To (Years)", self.age_to)
        form.addRow("Min Value", self.min_value)
        form.addRow("Max Value", self.max_value)
        form.addRow("Text Range", self.text_range)
        form.addRow("Unit Override", self.unit)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Save Range", clicked=self._save))
        btn_row.addWidget(QPushButton("Delete Selected", clicked=self._delete))
        btn_row.addWidget(QPushButton("Clear", clicked=self._clear))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Parameter", "Gender", "Age From", "Age To", "Min", "Max", "Text"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._parameters = self.api.list_pathology_parameters()
            self._units = self.api.list_pathology_units()
            self._ranges = self.api.list_pathology_normal_ranges()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.parameter.clear()
        self.parameter.addItem("— Select Test —", None)
        for param in self._parameters:
            self.parameter.addItem(pathology_item_label(param), param.get("id"))
        self.unit.clear()
        self.unit.addItem("— Default —", None)
        for unit in self._units:
            self.unit.addItem(f"{unit.get('code')} — {unit.get('name')}", unit.get("id"))
        self.table.setRowCount(len(self._ranges))
        for row, item in enumerate(self._ranges):
            age_from_y = int(item.get("age_from_days", 0) // 365)
            age_to_y = int(item.get("age_to_days", 0) // 365)
            self.table.setItem(row, 0, QTableWidgetItem(item.get("parameter_name") or ""))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("gender", "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(age_from_y)))
            self.table.setItem(row, 3, QTableWidgetItem(str(age_to_y)))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("min_value") or "")))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.get("max_value") or "")))
            self.table.setItem(row, 6, QTableWidgetItem(item.get("text_range") or ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _on_table_select(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        range_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        item = next((r for r in self._ranges if r.get("id") == range_id), None)
        if not item:
            return
        self._selected_id = range_id
        pidx = self.parameter.findData(item.get("parameter_id"))
        self.parameter.setCurrentIndex(pidx if pidx >= 0 else 0)
        gidx = self.gender.findData(item.get("gender"))
        self.gender.setCurrentIndex(gidx if gidx >= 0 else 0)
        self.age_from.setValue(int(item.get("age_from_days", 0) // 365))
        self.age_to.setValue(int(item.get("age_to_days", 0) // 365))
        self.min_value.setText(str(item.get("min_value") or ""))
        self.max_value.setText(str(item.get("max_value") or ""))
        self.text_range.setText(item.get("text_range") or "")
        uidx = self.unit.findData(item.get("unit_id"))
        self.unit.setCurrentIndex(uidx if uidx >= 0 else 0)

    def _save(self) -> None:
        param_id = self.parameter.currentData()
        if not param_id:
            QMessageBox.warning(self, "Validation", "Select a parameter.")
            return
        payload = {
            "parameter_id": param_id,
            "gender": self.gender.currentData(),
            "age_from_days": self.age_from.value() * 365,
            "age_to_days": self.age_to.value() * 365,
            "min_value": self.min_value.text().strip() or None,
            "max_value": self.max_value.text().strip() or None,
            "text_range": self.text_range.text().strip() or None,
            "unit_id": self.unit.currentData(),
        }
        try:
            if self._selected_id:
                self.api.update_pathology_normal_range(self._selected_id, payload)
            else:
                self.api.create_pathology_normal_range(payload)
            self._clear()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Validation", "Select a range row.")
            return
        range_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            self.api.delete_pathology_normal_range(range_id)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _clear(self) -> None:
        self._selected_id = None
        self.parameter.setCurrentIndex(0)
        self.gender.setCurrentIndex(0)
        self.age_from.setValue(0)
        self.age_to.setValue(120)
        self.min_value.clear()
        self.max_value.clear()
        self.text_range.clear()
