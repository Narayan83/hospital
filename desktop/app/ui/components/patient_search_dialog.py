from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
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
from app.ui.responsive_layout import fit_dialog_size
from app.ui.styles import apply_form_field_style

GRID_STYLE = """
QTableWidget {
    gridline-color: #6aa84f;
    font-size: 11px;
}
QHeaderView::section {
    background: #d9ead3;
    border: 1px solid #6aa84f;
    padding: 4px;
    font-weight: bold;
}
"""


class PatientSearchDialog(QDialog):
    """Legacy-style Patient Master Search dialog."""

    def __init__(
        self,
        api: ApiClient,
        parent: QWidget | None = None,
        *,
        initial_patient_no: str = "",
        initial_name: str = "",
    ):
        super().__init__(parent)
        self.api = api
        self._selected: dict | None = None
        self.setWindowTitle("Patient Master Search")
        self.resize(*fit_dialog_size(820, 560))
        self._build_ui()
        self._apply_initial_values(
            patient_no=initial_patient_no,
            name=initial_name,
        )
        apply_form_field_style(self)
        QShortcut(QKeySequence("Alt+S"), self, self._run_search)

    def _looks_like_contact_number(self, text: str) -> bool:
        digits = "".join(ch for ch in text if ch.isdigit())
        return len(digits) >= 7 and sum(ch.isalpha() for ch in text) == 0

    def _looks_like_aadhar(self, text: str) -> bool:
        digits = "".join(ch for ch in text if ch.isdigit())
        return len(digits) >= 12

    def _apply_initial_values(self, *, patient_no: str = "", name: str = "") -> None:
        name_text = (name or "").strip()
        if name_text:
            parts = name_text.split()
            self.first_name.setText(parts[0])
            if len(parts) > 2:
                self.middle_name.setText(" ".join(parts[1:-1]))
                self.last_name.setText(parts[-1])
            elif len(parts) == 2:
                self.last_name.setText(parts[1])
            self._run_search()
            return

        text = (patient_no or "").strip()
        if not text:
            return
        if self._looks_like_aadhar(text):
            self.aadhar_no.setText(text)
        elif self._looks_like_contact_number(text):
            self.mobile.setText(text)
        else:
            self.patient_no.setText(text)
        self._run_search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Patient Master Search")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e40af;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Patient number")
        self.first_name = QLineEdit()
        self.middle_name = QLineEdit()
        self.last_name = QLineEdit()
        self.village = QLineEdit()
        self.post = QLineEdit()
        self.taluk = QLineEdit()
        self.district = QLineEdit()
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Searches phone, mobile 1 & 2")
        self.mobile = QLineEdit()
        self.mobile.setPlaceholderText("Searches all contact numbers")
        self.mobile2 = QLineEdit()
        self.pin_code = QLineEdit()
        self.old_id = QLineEdit()
        self.aadhar_no = QLineEdit()

        fields = (
            ("Patient Id", self.patient_no),
            ("First Name", self.first_name),
            ("Second Name", self.middle_name),
            ("Third Name", self.last_name),
            ("Village", self.village),
            ("Post", self.post),
            ("Taluk", self.taluk),
            ("District", self.district),
            ("Phone", self.phone),
            ("Mobile 1", self.mobile),
            ("Mobile 2", self.mobile2),
            ("Pin Code", self.pin_code),
            ("Old Id", self.old_id),
            ("Aadhar", self.aadhar_no),
        )
        for index, (label, field) in enumerate(fields):
            row, col = divmod(index, 4)
            grid.addWidget(QLabel(label), row * 2, col)
            grid.addWidget(field, row * 2 + 1, col)

        search_row = QHBoxLayout()
        search_row.addStretch()
        self.search_btn = QPushButton("&Search")
        self.search_btn.setDefault(True)
        self.search_btn.clicked.connect(self._run_search)
        search_row.addWidget(self.search_btn)
        grid.addLayout(search_row, 8, 2, 1, 2)
        layout.addLayout(grid)

        self.status_label = QLabel("Enter criteria and click Search.")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 8)
        self.table.setStyleSheet(GRID_STYLE)
        self.table.setHorizontalHeaderLabels(
            ["Pid", "First", "Second", "Third", "Village", "Mobile", "Aadhar", "Phone"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._accept_selection)
        layout.addWidget(self.table, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_patient(self) -> dict | None:
        return self._selected

    def _filters(self) -> dict[str, Any]:
        mapping = {
            "patient_no": self.patient_no,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "village": self.village,
            "post": self.post,
            "taluk": self.taluk,
            "district": self.district,
            "phone": self.phone,
            "mobile": self.mobile,
            "mobile2": self.mobile2,
            "pin_code": self.pin_code,
            "old_id": self.old_id,
            "aadhar_no": self.aadhar_no,
        }
        return {key: field.text().strip() or None for key, field in mapping.items()}

    def _has_criteria(self, filters: dict[str, Any]) -> bool:
        return any(value for value in filters.values())

    def _run_search(self) -> None:
        filters = self._filters()
        if not self._has_criteria(filters):
            QMessageBox.information(
                self,
                "Search",
                "Enter at least one search field (name, mobile, aadhar, patient id, etc.).",
            )
            return
        try:
            result = self.api.search_patients(**filters, page_size=100)
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))
            return
        items = result.get("items", [])
        total = result.get("total", len(items))
        self.table.setRowCount(len(items))
        for row, patient in enumerate(items):
            village = patient.get("village_code") or patient.get("contact_address1") or ""
            first = patient.get("first_name") or ""
            if not patient.get("is_active", True):
                first = f"{first} [Inactive]"
            self.table.setItem(row, 0, QTableWidgetItem(patient.get("patient_no", "")))
            self.table.setItem(row, 1, QTableWidgetItem(first))
            self.table.setItem(row, 2, QTableWidgetItem(patient.get("middle_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(patient.get("last_name") or ""))
            self.table.setItem(row, 4, QTableWidgetItem(village))
            self.table.setItem(row, 5, QTableWidgetItem(patient.get("mobile") or patient.get("phone") or ""))
            self.table.setItem(row, 6, QTableWidgetItem(patient.get("aadhar_no") or ""))
            self.table.setItem(row, 7, QTableWidgetItem(patient.get("phone") or ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, patient)
        self.status_label.setText(f"{total} patient(s) found. Double-click or Select to load.")
        if len(items) == 1:
            self.table.selectRow(0)

    def _accept_selection(self) -> None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Select", "Select a patient from the list.")
            return
        cell = self.table.item(sel[0].row(), 0)
        if not cell:
            return
        patient = cell.data(Qt.ItemDataRole.UserRole)
        if not patient:
            return
        self._selected = patient
        self.accept()


def pick_patient(
    api: ApiClient,
    parent: QWidget | None = None,
    *,
    initial_patient_no: str = "",
    initial_name: str = "",
) -> dict | None:
    dialog = PatientSearchDialog(
        api,
        parent,
        initial_patient_no=initial_patient_no,
        initial_name=initial_name,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_patient()
    return None
