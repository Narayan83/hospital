from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.patient_controller import PatientController
from app.ui.components.patient_registration_dialog import edit_patient_dialog
from app.ui.styles import BORDER, INPUT_BG, PRIMARY, SURFACE


class PatientListWidget(QWidget):
    PAGE_SIZE = 100

    def __init__(self, controller: PatientController):
        super().__init__()
        self.controller = controller
        self._page = 1
        self._pages = 1
        self._total = 0
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        from app.ui.responsive_layout import get_density

        d = get_density()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(d.content_margin, d.content_margin, d.content_margin, d.content_margin)
        layout.setSpacing(d.section_spacing)
        heading = QLabel("Patient List")
        heading.setStyleSheet(
            f"font-size: {d.title_font_size}px; font-weight: bold; color: #1e40af;"
        )
        layout.addWidget(heading)

        hint = QLabel(
            "Browse all registered patients sorted by patient ID. "
            "Use search to filter by patient ID, name, mobile, or aadhar. "
            "Select a row and press Ctrl+C, or right-click, to copy the Patient ID."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: #64748b; font-size: {d.font_size}px; margin-bottom: 4px;")
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Patient ID, name, mobile, aadhar...")
        self.search_input.returnPressed.connect(self._run_search)
        search_row.addWidget(self.search_input, stretch=1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._run_search)
        search_row.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Patient ID",
                "Name",
                "Age",
                "Sex",
                "Mobile",
                "Village",
                "Section",
                "Status",
                "Action",
            ]
        )
        self.table.setProperty(
            "hmsColumnKinds",
            ["code", "text", "number", "code", "phone", "text", "text", "code", "action"],
        )
        self.table.setProperty("hmsStretchColumn", 1)  # Name absorbs leftover width
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 120)  # Patient ID
        self.table.setColumnWidth(1, 200)  # Name
        self.table.setColumnWidth(2, 70)  # Age
        self.table.setColumnWidth(3, 60)  # Sex
        self.table.setColumnWidth(4, 120)  # Mobile
        self.table.setColumnWidth(5, 140)  # Village
        self.table.setColumnWidth(6, 100)  # Section
        self.table.setColumnWidth(7, 80)  # Status
        self.table.setColumnWidth(8, 72)  # Action
        self.table.doubleClicked.connect(self._edit_selected_row)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            f"""
            QTableWidget {{
                background: {SURFACE};
                alternate-background-color: {INPUT_BG};
                border: 1px solid {BORDER};
                gridline-color: {BORDER};
                font-size: {d.font_size}px;
            }}
            QHeaderView::section {{
                background: #dbeafe;
                border: 1px solid {BORDER};
                padding: 4px 6px;
                font-weight: 600;
                font-size: {d.font_size}px;
                color: {PRIMARY};
            }}
            """
        )
        layout.addWidget(self.table, stretch=1)

        pager = QHBoxLayout()
        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet(f"color: #64748b; font-size: {d.font_size}px;")
        pager.addWidget(self.status_label)
        pager.addStretch()

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self._prev_page)
        pager.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setStyleSheet(f"font-size: {d.font_size}px; color: #475569; padding: 0 8px;")
        pager.addWidget(self.page_label)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._next_page)
        pager.addWidget(self.next_btn)
        layout.addLayout(pager)

        QShortcut(QKeySequence("F5"), self, self.refresh)
        QShortcut(QKeySequence.StandardKey.Copy, self.table, self._copy_selected_patient_id)

    def refresh(self) -> None:
        self._load_page(self._page)

    def _clear_search(self) -> None:
        self.search_input.clear()
        self._page = 1
        self._load_page(1)

    def _run_search(self) -> None:
        self._page = 1
        self._load_page(1)

    def _prev_page(self) -> None:
        if self._page > 1:
            self._load_page(self._page - 1)

    def _next_page(self) -> None:
        if self._page < self._pages:
            self._load_page(self._page + 1)

    def _load_page(self, page: int) -> None:
        search = self.search_input.text().strip() or None
        try:
            result = self.controller.api.list_patients(
                page=page,
                page_size=self.PAGE_SIZE,
                search=search,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Patient List", str(exc))
            return

        items = result.get("items", [])
        self._page = int(result.get("page", page))
        self._pages = max(int(result.get("pages", 1)), 1)
        self._total = int(result.get("total", len(items)))

        self.table.setRowCount(len(items))
        for row, patient in enumerate(items):
            name = " ".join(
                part
                for part in (
                    patient.get("first_name"),
                    patient.get("middle_name"),
                    patient.get("last_name"),
                )
                if part
            ).strip()
            village = patient.get("village_code") or patient.get("contact_address1") or ""
            active = patient.get("is_active", True)
            values = (
                patient.get("patient_no", ""),
                name,
                str(patient.get("age") or ""),
                patient.get("gender") or "",
                patient.get("mobile") or patient.get("phone") or "",
                village,
                patient.get("hospital_section_name") or "",
                "Active" if active else "Inactive",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    # Display patient_no (e.g. P…), not DB/table UUID.
                    item.setData(Qt.ItemDataRole.UserRole, patient)
                self.table.setItem(row, col, item)

            edit_btn = QPushButton("Edit")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda _checked=False, p=patient: self._edit_patient(p))
            self.table.setCellWidget(row, 8, edit_btn)

        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.prev_btn.setEnabled(self._page > 1)
        self.next_btn.setEnabled(self._page < self._pages)
        if search:
            self.status_label.setText(f"{self._total} patient(s) matched — sorted by patient ID")
        else:
            self.status_label.setText(f"{self._total} patient(s) — sorted by patient ID")

    def _patient_at_row(self, row: int) -> dict | None:
        if row < 0:
            return None
        id_item = self.table.item(row, 0)
        if id_item is not None:
            patient = id_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(patient, dict):
                return patient
        return None

    def _selected_patient_no(self) -> str:
        row = self.table.currentRow()
        patient = self._patient_at_row(row)
        if patient:
            return (patient.get("patient_no") or "").strip()
        id_item = self.table.item(row, 0) if row >= 0 else None
        if id_item is not None:
            return id_item.text().strip()
        return ""

    def _copy_selected_patient_id(self) -> bool:
        patient_no = self._selected_patient_no()
        if not patient_no:
            return False
        QGuiApplication.clipboard().setText(patient_no)
        self.status_label.setText(f"Copied Patient ID: {patient_no}")
        return True

    def _show_table_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.setCurrentCell(index.row(), index.column())
        patient_no = self._selected_patient_no()
        if not patient_no:
            return
        menu = QMenu(self)
        copy_action = menu.addAction(f"Copy Patient ID ({patient_no})")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == copy_action:
            self._copy_selected_patient_id()

    def _edit_selected_row(self) -> None:
        row = self.table.currentRow()
        patient = self._patient_at_row(row)
        if patient:
            self._edit_patient(patient)

    def _edit_patient(self, patient: dict) -> None:
        patient_id = patient.get("id")
        record = patient
        if patient_id:
            full, error = self.controller.get_patient(patient_id)
            if error:
                QMessageBox.warning(self, "Edit Patient", error)
                return
            record = full or patient

        updated = edit_patient_dialog(self.controller.api, record, self)
        if updated:
            self._load_page(self._page)
            self.status_label.setText(
                f"Patient {updated.get('patient_no', '')} updated."
            )
