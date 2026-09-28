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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


class LetterMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    PLACEHOLDER_HINT = (
        "Use placeholders like {{patient_name}}, {{patient_id}}, {{doctor_name}}, "
        "{{hospital_name}}, {{date}} — replaced when printing the letter."
    )

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Letter Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(self.PLACEHOLDER_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)

        self.letter_combo = QComboBox()
        self.letter_combo.setEnabled(False)
        self.letter_combo.currentIndexChanged.connect(self._on_letter_selected)
        top.addWidget(QLabel("Select Letter"))
        top.addWidget(self.letter_combo, stretch=1)
        layout.addLayout(top)

        form_box = QGroupBox("Letter Template")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.code.setPlaceholderText("e.g. DISCHARGE")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Discharge Summary Letter")
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("e.g. Discharge Summary - {{patient_name}}")
        self.body = QTextEdit()
        self.body.setPlaceholderText("Letter body text with {{placeholders}}...")
        self.body.setMinimumHeight(180)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Subject", self.subject)
        form.addRow("Body *", self.body)
        form.addRow("Sort Order", self.sort_order)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Subject", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._items = self.api.list_letter_templates()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._load_table()
        self._load_letter_combo()

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("subject") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_letter_combo(self) -> None:
        current = self.letter_combo.currentData()
        self.letter_combo.clear()
        self.letter_combo.addItem("— Select —", None)
        for item in self._items:
            self.letter_combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))
        if current:
            idx = self.letter_combo.findData(current)
            if idx >= 0:
                self.letter_combo.setCurrentIndex(idx)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.letter_combo.setEnabled(not is_create)
        self.code.setReadOnly(not is_create)
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        self.name.setEnabled(enabled)
        self.subject.setEnabled(enabled)
        self.body.setEnabled(enabled)
        self.sort_order.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_letter_selected(self) -> None:
        letter_id = self.letter_combo.currentData()
        if letter_id:
            self._load_item(letter_id)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        letter_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and letter_id:
            idx = self.letter_combo.findData(letter_id)
            if idx >= 0:
                self.letter_combo.setCurrentIndex(idx)

    def _load_item(self, letter_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == letter_id), None)
        if not item:
            try:
                item = self.api.get_letter_template(letter_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = letter_id
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        self.subject.setText(item.get("subject") or "")
        self.body.setPlainText(item.get("body") or "")
        self.sort_order.setValue(int(item.get("sort_order") or 0))

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.subject.clear()
        self.body.clear()
        self.sort_order.setValue(0)
        self.letter_combo.setCurrentIndex(0)
        self.table.clearSelection()

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            letter_id = self.letter_combo.currentData() or self._selected_id
            if not letter_id:
                QMessageBox.warning(self, "Validation", "Select a letter to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this letter template?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_letter_template(letter_id)
                QMessageBox.information(self, "Success", "Letter template deactivated.")
                self._clear_form()
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        code = self.code.text().strip()
        name = self.name.text().strip()
        body = self.body.toPlainText().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validation", "Code and name are required.")
            return
        if not body:
            QMessageBox.warning(self, "Validation", "Letter body is required.")
            return

        payload = {
            "code": code,
            "name": name,
            "subject": self.subject.text().strip() or None,
            "body": body,
            "sort_order": self.sort_order.value(),
        }
        try:
            if mode == self.MODE_CREATE:
                self.api.create_letter_template(payload)
                QMessageBox.information(self, "Success", "Letter template created.")
                self._clear_form()
            else:
                letter_id = self.letter_combo.currentData() or self._selected_id
                if not letter_id:
                    QMessageBox.warning(self, "Validation", "Select a letter to modify.")
                    return
                self.api.update_letter_template(
                    letter_id,
                    {
                        "name": name,
                        "subject": self.subject.text().strip() or None,
                        "body": body,
                        "sort_order": self.sort_order.value(),
                    },
                )
                QMessageBox.information(self, "Success", "Letter template updated.")
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
