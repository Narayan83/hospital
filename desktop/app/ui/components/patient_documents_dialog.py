from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.responsive_layout import fit_dialog_size
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE

VIEWED_ROW_COLOR = QColor("#dcfce7")


class PatientDocumentsDialog(QDialog):
    def __init__(
        self,
        api: ApiClient,
        *,
        patient_id: str,
        patient_no: str = "",
        patient_name: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.api = api
        self.patient_id = patient_id
        self._rows: list[dict] = []
        self.setWindowTitle("Patient Documents")
        self.resize(*fit_dialog_size(900, 520))
        self._build_ui(patient_no, patient_name)
        self.refresh()

    def _build_ui(self, patient_no: str, patient_name: str) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(f"Patient Documents — {patient_no} {patient_name}".strip())
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1e3a5f;")
        layout.addWidget(title)

        hint = QLabel("Green rows indicate documents you have already viewed.")
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(HEADER_BTN_STYLE)
        refresh_btn.clicked.connect(self.refresh)
        view_btn = QPushButton("View Selected")
        view_btn.setStyleSheet(HEADER_BTN_STYLE)
        view_btn.clicked.connect(self._view_selected)
        action_row.addWidget(refresh_btn)
        action_row.addWidget(view_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Document", "Pages", "Size (KB)", "Scanned By", "Scanner", "Viewed"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._view_selected)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status = QLabel()
        layout.addWidget(self.status)

    def refresh(self) -> None:
        try:
            self._rows = self.api.list_patient_documents(patient_id=self.patient_id)
        except ApiError as exc:
            self.status.setText(str(exc))
            self.table.setRowCount(0)
            return
        except Exception as exc:
            self.status.setText(f"Connection error: {exc}")
            self.table.setRowCount(0)
            return

        self.table.setRowCount(len(self._rows))
        for row_index, doc in enumerate(self._rows):
            viewed = doc.get("viewed_by_current_doctor")
            values = [
                str(doc.get("document_date") or ""),
                doc.get("original_name") or Path(doc.get("file_path", "")).name,
                str(doc.get("page_count") or ""),
                str((doc.get("file_size_bytes") or 0) // 1024),
                doc.get("scanned_by_name") or "—",
                doc.get("scanner_name") or "—",
                "Yes" if viewed else "No",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, doc.get("id"))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if viewed:
                    item.setBackground(VIEWED_ROW_COLOR)
                self.table.setItem(row_index, col, item)

        self.status.setText(f"{len(self._rows)} document(s) on file.")

    def _selected_document(self) -> dict | None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Select", "Select a document row first.")
            return None
        row = sel[0].row()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _view_selected(self) -> None:
        doc = self._selected_document()
        if not doc:
            return
        document_id = doc.get("id")
        if not document_id:
            return
        try:
            content = self.api.download_patient_document_file(document_id)
            temp_path = Path(tempfile.gettempdir()) / f"hms_doc_{document_id}.pdf"
            temp_path.write_bytes(content)
            self._open_pdf(temp_path)
            session = get_session()
            if session.maps_to_doctor and session.doctor_id:
                self.api.mark_patient_document_viewed(document_id)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "View Document", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "View Document", f"Could not open document: {exc}")

    @staticmethod
    def _open_pdf(path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
            return
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
            return
        subprocess.run(["xdg-open", str(path)], check=False)
