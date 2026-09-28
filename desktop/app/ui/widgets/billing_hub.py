from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from typing import Callable

from app.ui.styles import BORDER, PANEL_CARD, TEXT_MUTED


class BillingHubWidget(QWidget):
    def __init__(self, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self._on_navigate = on_navigate
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Billing")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 20px; font-weight: bold; color: #1d4ed8; margin-bottom: 12px;")
        layout.addWidget(heading)

        subtitle = QLabel(
            "OPD Bill, IPD Admission, IPD Discharge, and Pathology Bill are live. "
            "Configure categories and packages under Masters → Billing Setup."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #475569; margin-bottom: 16px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [
            ("opd_bill", "OPD Bill", "Outpatient billing with print", "#2563eb"),
            ("pathology_bill", "Pathology Bill", "Standalone lab billing & report", "#0f766e"),
            ("in_patient_discharge", "IPD Discharge Bill", "Discharge billing with print", "#7c3aed"),
            ("in_patient_admission", "IPD Admission", "Admit patient to ward", "#6d28d9"),
            ("pathology_work_list", "Pathology Work List", "Daily lab bills & print", "#14b8a6"),
            ("ipd_bill", "IPD Running Bill", "Inpatient running bill (coming soon)", "#8b5cf6"),
            ("service_category_master", "Service Categories", "Primary filter in billing", "#0d9488"),
            ("service_sub_category_master", "Sub Categories", "Second-level billing filter", "#059669"),
            ("package_creation_master", "Packages", "Procedure bundles e.g. delivery", "#d97706"),
            ("assign_services_to_package", "Package Services", "Map services to packages", "#dc2626"),
            ("bill_types_creation", "Bill Types", "OPD / IPD / Lab types", "#4b5563"),
        ]
        for index, (module_id, title, desc, color) in enumerate(cards):
            grid.addWidget(self._make_card(module_id, title, desc, color), index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch()

    def _make_card(self, module_id: str, title: str, desc: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"{PANEL_CARD}"
            f"QFrame:hover {{ border-color: {color}; border-width: 2px; }}"
        )
        box = QVBoxLayout(frame)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {color};")
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        btn = QPushButton("Open")
        btn.clicked.connect(lambda: self._navigate(module_id))
        box.addWidget(title_lbl)
        box.addWidget(desc_lbl)
        box.addWidget(btn)
        return frame

    def _navigate(self, module_id: str) -> None:
        if self._on_navigate:
            self._on_navigate(module_id)

    def refresh(self) -> None:
        pass
