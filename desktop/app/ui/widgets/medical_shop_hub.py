from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.styles import BORDER, PANEL_CARD, TEXT_MUTED


class MedicalShopHubWidget(QWidget):
    def __init__(self, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self._on_navigate = on_navigate
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Medical Shop")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 20px; font-weight: bold; color: #1d4ed8; margin-bottom: 12px;")
        layout.addWidget(heading)

        subtitle = QLabel(
            "All medical shop masters, sale/purchase billing, and pharmacy reports are available below."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #475569; margin-bottom: 16px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        sections = [
            (
                "Item Masters",
                [
                    ("medicine_master", "Medicine Master", "Medicines and drugs", "#2563eb"),
                    ("surgicals_master", "Surgicals Master", "Surgical items", "#1d4ed8"),
                    ("disposables_master", "Disposables Master", "Disposable supplies", "#3b82f6"),
                    ("consumables_master", "Consumables Master", "Consumable items", "#0ea5e9"),
                    ("implants_master", "Implants Master", "Implant records", "#0284c7"),
                ],
            ),
            (
                "Reference Masters",
                [
                    ("manufacturer_master", "Manufacturer Master", "Drug manufacturers", "#7c3aed"),
                    ("marketing_agency_master", "Marketing Agency", "Marketing agencies", "#8b5cf6"),
                    ("distributors_master", "Distributors Master", "Distributors", "#a855f7"),
                    ("drug_category_master", "Drug Category Master", "Drug categories", "#9333ea"),
                    ("supplier_master", "Supplier Master", "Purchase suppliers", "#6d28d9"),
                    ("medicine_group_creation", "Medicine Group", "Group creation", "#5b21b6"),
                    ("assign_medicine_to_group", "Assign To Group", "Map medicines to groups", "#4c1d95"),
                ],
            ),
            (
                "Transactions & Reports",
                [
                    ("medicine_sale_bill", "Medicine Sale Bill", "Pharmacy sales billing", "#059669"),
                    ("medicine_indent", "Medicine Indent", "Issue stock to ward", "#0d9488"),
                    ("medicine_purchase_bill_109", "Medicine Purchase Bill", "Purchase entry", "#047857"),
                    ("medicine_purchase_return", "Medicine Purchase Return", "Return to supplier", "#b45309"),
                    ("sales_register", "Sales Register", "Sales register report", "#0f766e"),
                    ("sales_summary", "Sales Summary", "Sales summary report", "#115e59"),
                    ("schedule_h_drug_report", "Schedule H Report", "Schedule H drug report", "#134e4a"),
                    ("consolidated_stock_report", "Stock Report", "Consolidated stock report", "#14532d"),
                ],
            ),
        ]

        for section_title, cards in sections:
            section = QLabel(section_title)
            section.setStyleSheet("font-size: 15px; font-weight: 600; color: #334155; margin-top: 8px;")
            layout.addWidget(section)
            grid = QGridLayout()
            grid.setSpacing(12)
            for index, card in enumerate(cards):
                grid.addWidget(self._make_card(*card), index // 2, index % 2)
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
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
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
