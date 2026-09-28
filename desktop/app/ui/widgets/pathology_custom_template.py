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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.pathology_display import pathology_item_label


class PathologyCustomTemplateWidget(QWidget):
    MODE_CREATE, MODE_MODIFY, MODE_DELETE = "Create", "Modify", "Delete"

    HINT = (
        "Save ready-made result text so you don't retype it for every patient. "
        "Example: a 'Normal Study' template for an Ultrasound test. While entering results "
        "in the Work List you pick the template and it fills the result box. "
        "Link it to a test to show only that test's templates."
    )

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._parameters: list[dict] = []
        self._services: list[dict] = []
        self._selected_id: str | None = None
        self._loading = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Result Templates")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)
        hint = QLabel(self.HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; margin-bottom: 8px;")
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        self.item_combo = QComboBox()
        self.item_combo.setEnabled(False)
        self.item_combo.currentIndexChanged.connect(self._on_item_selected)
        top.addWidget(QLabel("Select Template"))
        top.addWidget(self.item_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Result Template")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("(leave blank — created automatically)")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Template name, e.g. Ultrasound — Normal Study")
        self.parameter = QComboBox()
        self.service = QComboBox()
        self.body = QTextEdit()
        self.body.setMinimumHeight(140)
        self.body.setPlaceholderText("The result text that will be filled in for the patient...")
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        for combo in (self.parameter, self.service):
            combo.setMinimumWidth(260)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.service.currentIndexChanged.connect(self._on_service_changed)
        form.addRow("Code", self.code)
        form.addRow("Name *", self.name)
        form.addRow("For Test", self.service)
        form.addRow("For Parameter", self.parameter)
        form.addRow("Result Text *", self.body)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(QPushButton("Clear", clicked=self._clear_form))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Parameter", "Lab Test", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._items = self.api.list_pathology_result_templates()
            self._parameters = self.api.list_pathology_parameters()
            self._services = self.api.list_pathology_lab_services()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._loading = True
        self.service.clear()
        self.service.addItem("— Any Test —", None)
        for svc in self._services:
            self.service.addItem(pathology_item_label(svc), svc.get("id"))
        self._loading = False
        self._reload_parameters_for_service(None)
        self.item_combo.clear()
        self.item_combo.addItem("— Select —", None)
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("parameter_name") or "Any"))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("service_name") or "Any"))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.item_combo.addItem(item.get("name", ""), item.get("id"))

    def _on_service_changed(self, *_args) -> None:
        if self._loading:
            return
        self._reload_parameters_for_service(self.service.currentData())

    def _reload_parameters_for_service(
        self, service_id: str | None, *, keep_parameter_id: str | None = None
    ) -> None:
        """Show only the chosen test's components; or all parameters for 'Any Test'."""
        self._loading = True
        self.parameter.clear()
        if service_id:
            self.parameter.addItem("— Whole test (narrative) —", None)
            try:
                mappings = self.api.list_pathology_service_parameters(service_id=service_id)
            except ApiError:
                mappings = []
            seen: set[str] = set()
            for mapping in mappings:
                pid = mapping.get("parameter_id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                self.parameter.addItem(
                    pathology_item_label(
                        {
                            "name": mapping.get("parameter_name"),
                            "code": mapping.get("parameter_code"),
                        }
                    ),
                    pid,
                )
        else:
            self.parameter.addItem("— Any —", None)
            for param in self._parameters:
                self.parameter.addItem(pathology_item_label(param), param.get("id"))
        if keep_parameter_id is not None:
            idx = self.parameter.findData(keep_parameter_id)
            self.parameter.setCurrentIndex(idx if idx >= 0 else 0)
        self._loading = False

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.item_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        for widget in (self.name, self.parameter, self.service, self.body, self.sort_order):
            widget.setEnabled(not is_delete)
        if is_create:
            self._clear_form()

    def _on_item_selected(self) -> None:
        if self.item_combo.currentData():
            self._load_item(self.item_combo.currentData())

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if items and self.mode_combo.currentText() != self.MODE_CREATE:
            item_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            idx = self.item_combo.findData(item_id)
            if idx >= 0:
                self.item_combo.setCurrentIndex(idx)

    def _load_item(self, item_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == item_id), None)
        if not item:
            return
        self._selected_id = item_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.body.setPlainText(item.get("body") or "")
        self.sort_order.setValue(int(item.get("sort_order") or 0))
        self._loading = True
        sidx = self.service.findData(item.get("service_id"))
        self.service.setCurrentIndex(sidx if sidx >= 0 else 0)
        self._loading = False
        self._reload_parameters_for_service(
            item.get("service_id"), keep_parameter_id=item.get("parameter_id")
        )

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.body.clear()
        self.sort_order.setValue(0)
        self.parameter.setCurrentIndex(0)
        self.service.setCurrentIndex(0)

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            if not self._selected_id:
                QMessageBox.warning(self, "Validation", "Select a template to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Delete this template?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_pathology_result_template(self._selected_id)
                self.refresh()
                self._clear_form()
                QMessageBox.information(self, "Success", "Template deleted.")
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return
        if not self.name.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not self.body.toPlainText().strip():
            QMessageBox.warning(self, "Validation", "Result text is required.")
            return
        code = self.code.text().strip()
        if not code:
            import re

            code = re.sub(r"[^A-Z0-9]+", "", self.name.text().strip().upper())[:24] or "TMPL"
        payload = {
            "code": code,
            "name": self.name.text().strip(),
            "body": self.body.toPlainText().strip(),
            "parameter_id": self.parameter.currentData(),
            "service_id": self.service.currentData(),
            "sort_order": self.sort_order.value(),
        }
        try:
            if mode == self.MODE_CREATE:
                self.api.create_pathology_result_template(payload)
            else:
                if not self._selected_id:
                    QMessageBox.warning(self, "Validation", "Select a template to modify.")
                    return
                self.api.update_pathology_result_template(
                    self._selected_id,
                    {
                        "name": payload["name"],
                        "body": payload["body"],
                        "parameter_id": payload["parameter_id"],
                        "service_id": payload["service_id"],
                        "sort_order": payload["sort_order"],
                    },
                )
            self.refresh()
            self._clear_form()
            QMessageBox.information(self, "Success", "Template saved.")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
