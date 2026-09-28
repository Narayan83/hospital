from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


class NotesMasterWidget(QWidget):
    """Maintain reusable report notes.

    A note with no service code is the general note shown for every bill; a note
    with a service code is tied to that single service.
    """

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._notes: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Notes Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)

        hint = QLabel(
            "Leave the Service Code blank (or 0) for a general note that applies to all"
            " services. Enter a service code to attach a note to that test only."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Note")
        form = QFormLayout(form_box)
        self.service_code = QLineEdit()
        self.service_code.setPlaceholderText("Optional — blank/0 = general (all services)")
        self.note_text = QTextEdit()
        self.note_text.setPlaceholderText("Enter the note that should print on the report...")
        self.note_text.setMinimumHeight(120)
        form.addRow("Service Code", self.service_code)
        form.addRow("Notes", self.note_text)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Save Note", clicked=self._save))
        btn_row.addWidget(QPushButton("Delete Selected", clicked=self._delete))
        btn_row.addWidget(QPushButton("Clear", clicked=self._clear))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Service Code", "Notes"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._notes = self.api.list_service_notes()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.table.setRowCount(len(self._notes))
        for row, item in enumerate(self._notes):
            code = item.get("service_code") or "General (all)"
            preview = " ".join((item.get("note_text") or "").split())
            self.table.setItem(row, 0, QTableWidgetItem(code))
            self.table.setItem(row, 1, QTableWidgetItem(preview))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _on_table_select(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        note_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        item = next((n for n in self._notes if n.get("id") == note_id), None)
        if not item:
            return
        self._selected_id = note_id
        self.service_code.setText(item.get("service_code") or "")
        self.note_text.setPlainText(item.get("note_text") or "")

    def _save(self) -> None:
        text = self.note_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Validation", "Enter the note text.")
            return
        payload = {
            "service_code": self.service_code.text().strip() or None,
            "note_text": text,
        }
        try:
            if self._selected_id:
                self.api.update_service_note(self._selected_id, payload)
            else:
                self.api.create_service_note(payload)
            self._clear()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Validation", "Select a note row.")
            return
        note_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        try:
            self.api.delete_service_note(note_id)
            self._clear()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _clear(self) -> None:
        self._selected_id = None
        self.service_code.clear()
        self.note_text.clear()
        self.table.clearSelection()
