from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from app.session import get_session, hospital_display_name

EXPANDED_WIDTH = 260
COLLAPSED_WIDTH = 60

MENU_ICONS = {
    "dashboard": "📊",
    "masters": "📁",
    "transactions": "💳",
    "ward_management": "🛏",
    "medical_records": "📋",
    "reports": "📈",
    "medical_shop": "💊",
    "medicine_master": "💊",
    "medicine_sale_bill": "🧾",
    "surgicals_master": "🔪",
    "disposables_master": "🧤",
    "consumables_master": "📦",
    "implants_master": "🦴",
    "manufacturer_master": "🏭",
    "marketing_agency_master": "📣",
    "distributors_master": "🚚",
    "drug_category_master": "🏷",
    "sales_register": "📒",
    "sales_summary": "📊",
    "medicine_purchase_bill_109": "🛒",
    "supplier_master": "🏪",
    "schedule_h_drug_report": "⚠",
    "consolidated_stock_report": "📈",
    "medicine_group_creation": "🗂",
    "assign_medicine_to_group": "🔗",
    "pathology": "🔬",
    "pathology_bill": "🧾",
    "pathology_bill_reprint": "🖨",
    "pathology_bill_cancel": "✖",
    "pathology_bill_modification": "✏",
    "pathology_work_list": "📋",
    "user_management": "👥",
    "patient_master": "👤",
    "patient_list": "📋",
    "patient_service_creation": "🧾",
    "doctor_master": "🩺",
    "department_master": "🏢",
    "procedure_type_master": "🧪",
    "billing_structure_mapping": "🗂",
    "bill_types_creation": "🧾",
    "authority_creation_master": "🪪",
    "hospital_profile": "⚙️",
    "dashboard_shortcut_setup": "⚡",
    "print_template_designer": "🖨",
    "database_migration": "🗄",
    "hospital_sections": "🏥",
    "prefix_creation": "🔤",
    "patient_id_format": "🆔",
    "payment_mode_creation": "💳",
    "cashbook": "📒",
    "ledger_master": "📚",
    "ward_master": "🛏",
    "billing": "💰",
    "bill_modification": "✏",
    "opd_bill_modification": "✏",
    "ipd_bill_modification": "✏",
    "billing_setup": "🧩",
    "service_category_master": "🏷",
    "service_sub_category_master": "🔖",
    "package_creation_master": "📦",
    "assign_services_to_package": "🔗",
    "opd_bill": "🧾",
    "opd_bill_reprint": "🖨",
    "ipd_bill": "🏥",
    "ipd_bill_reprint": "🖨",
    "in_patient_admission": "🛏",
    "in_patient_discharge": "🚪",
    "diagnose_management": "📄",
    "user_registration": "➕",
    "user_addition_modification": "➕",
    "role_management": "🔑",
    "role_menu_permissions": "📋",
    "user_role_mapping": "🔗",
    "notification_setup": "🔔",
    "settings": "⚙",
    "profile": "👤",
}

GROUP_ICONS = {
    "masters": "📁",
    "transactions": "💳",
    "ward_management": "🛏",
    "medical_records": "📋",
    "reports": "📈",
    "medical_shop": "💊",
    "pathology": "🔬",
    "user_management": "👥",
}


def _menu_count(menus: list[dict]) -> int:
    total = 0
    for menu in menus:
        total += 1
        total += _menu_count(menu.get("children") or [])
    return total


def _menu_matches(menu: dict, query: str) -> bool:
    label = (menu.get("label") or "").lower()
    code = (menu.get("code") or "").lower().replace("_", " ")
    return query in label or query in code


def _filter_menus(menus: list[dict], query: str) -> list[dict]:
    text = query.strip().lower()
    if not text:
        return menus

    filtered: list[dict] = []
    for menu in menus:
        children = menu.get("children") or []
        if children:
            if _menu_matches(menu, text):
                filtered.append(menu)
                continue
            matched_children = _filter_menus(children, text)
            if matched_children:
                filtered.append({**menu, "children": matched_children})
        elif _menu_matches(menu, text):
            filtered.append(menu)
    return filtered


class Sidebar(QFrame):
    module_selected = Signal(str)
    module_opening = Signal(str)

    def __init__(self):
        super().__init__()
        self._collapsed = False
        self.setFixedWidth(EXPANDED_WIDTH)
        self.setStyleSheet("QFrame { background: #0f172a; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand_frame = QFrame()
        brand_frame.setStyleSheet("background: #1e293b; border: none;")
        brand_layout = QVBoxLayout(brand_frame)
        brand_layout.setContentsMargins(14, 14, 14, 12)
        brand_layout.setSpacing(2)

        brand_row = QHBoxLayout()
        self.brand_icon = QLabel("🏥")
        self.brand_icon.setStyleSheet("font-size: 20px; background: transparent;")
        brand_row.addWidget(self.brand_icon)
        self.brand_text = QLabel("HMS")
        self.brand_text.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: #93c5fd;"
            " letter-spacing: 1px; background: transparent;"
        )
        brand_row.addWidget(self.brand_text)
        brand_row.addStretch()
        brand_layout.addLayout(brand_row)

        self.brand_sub = QLabel("Hospital Management")
        self.brand_sub.setStyleSheet(
            "font-size: 10px; color: #64748b; background: transparent; padding-left: 28px;"
        )
        brand_layout.addWidget(self.brand_sub)
        self.apply_hospital_branding()

        # Menu search sits directly under the logo in the left sidebar only.
        self.search_box = QLineEdit()
        self.search_box.setObjectName("sidebarSearch")
        self.search_box.setProperty("hmsSkipFormStyle", True)
        self.search_box.setPlaceholderText("Search menu...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedHeight(32)
        self.search_box.setStyleSheet(
            """
            QLineEdit#sidebarSearch {
                background-color: #fef3c7;
                color: #0f172a;
                border: 1px solid #f59e0b;
                border-radius: 6px;
                padding: 4px 10px;
                margin: 8px 0 2px 0;
                font-size: 13px;
                font-weight: 500;
                selection-background-color: #1e40af;
                selection-color: #ffffff;
            }
            QLineEdit#sidebarSearch:focus {
                border-color: #d97706;
                background-color: #fffbeb;
                color: #0f172a;
            }
            """
        )
        search_palette = self.search_box.palette()
        search_palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
        search_palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
        search_palette.setColor(QPalette.ColorRole.Base, QColor("#fef3c7"))
        search_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#92400e"))
        self.search_box.setPalette(search_palette)
        self.search_box.setAutoFillBackground(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        brand_layout.addWidget(self.search_box)

        layout.addWidget(brand_frame)

        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedHeight(36)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(
            """
            QPushButton {
                background: #1e293b; color: #94a3b8; border: none;
                font-size: 16px; text-align: left; padding-left: 18px;
            }
            QPushButton:hover { background: #334155; color: white; }
            """
        )
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tree.setAnimated(False)
        self.tree.setStyleSheet(
            """
            QTreeWidget {
                background: #0f172a; border: none; color: #cbd5e1;
                font-size: 13px; outline: none;
            }
            QTreeWidget::item {
                padding: 7px 6px; border-radius: 6px; margin: 1px 6px;
            }
            QTreeWidget::item:selected { background: #1e40af; color: white; }
            QTreeWidget::item:hover { background: #1e293b; }
            QTreeWidget::branch { background: #0f172a; }
            """
        )
        self.tree.itemPressed.connect(self._on_item_pressed)
        layout.addWidget(self.tree, stretch=1)

        self.load_menus()

    def apply_hospital_branding(self) -> None:
        name = hospital_display_name()
        short = name if len(name) <= 18 else f"{name[:16]}…"
        self.brand_text.setText(short)
        self.brand_sub.setText(name)
        self.brand_sub.setToolTip(name)

    def load_menus(self) -> None:
        from app.perf_log import step

        menus = get_session().menus
        query = self.search_box.text().strip() if not self._collapsed else ""
        if query:
            menus = _filter_menus(menus, query)
        step("Sidebar.load_menus start", menu_nodes=_menu_count(menus))
        self.tree.clear()
        if not menus:
            step("Sidebar.load_menus done (empty)")
            return

        for menu in menus:
            self._add_menu_item(None, menu)
        if query:
            self.tree.expandAll()
        step("Sidebar tree items built (collapsed)")

    def _on_search_changed(self, _text: str) -> None:
        if self._collapsed:
            return
        self.load_menus()

    def _icon_for(self, menu: dict) -> str:
        code = menu.get("code", "")
        if code in MENU_ICONS:
            return MENU_ICONS[code]
        if menu.get("children"):
            return GROUP_ICONS.get(code, "📂")
        if menu.get("legacy_form"):
            return "📄"
        return "•"

    def _add_menu_item(self, parent: QTreeWidgetItem | None, menu: dict) -> QTreeWidgetItem:
        icon = self._icon_for(menu)
        display_label = menu.get("label") or ""
        # Legacy menu code (created earlier as "diagnose_management") should show as Discharge Summary.
        if (menu.get("code") or "") == "diagnose_management":
            display_label = "Discharge Summary"
        label = f"{icon}  {display_label}" if not self._collapsed else icon
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, menu["code"])

        children = menu.get("children") or []
        if children:
            item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
            for child in children:
                self._add_menu_item(item, child)
        else:
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)

        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)
        return item

    def _on_item_pressed(self, item: QTreeWidgetItem, _column: int) -> None:
        is_group = item.data(0, Qt.ItemDataRole.UserRole + 1)
        code = item.data(0, Qt.ItemDataRole.UserRole)
        if is_group and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
            return
        if code:
            self.module_opening.emit(code)
            self.module_selected.emit(code)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self.setFixedWidth(COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH)
        self.toggle_btn.setText("➕" if self._collapsed else "☰")
        self.search_box.setVisible(not self._collapsed)
        self.brand_text.setVisible(not self._collapsed)
        self.brand_sub.setVisible(not self._collapsed)
        if self._collapsed:
            self.search_box.clear()
        self.load_menus()

    def ensure_expanded(self) -> None:
        if not self._collapsed:
            return
        self._collapsed = False
        self.setFixedWidth(EXPANDED_WIDTH)
        self.toggle_btn.setText("☰")
        self.search_box.setVisible(True)
        self.brand_text.setVisible(True)
        self.brand_sub.setVisible(True)
        self.load_menus()

    def reveal_module(self, module_code: str) -> None:
        """Keep sidebar wide; highlight active module and expand its branch."""
        self.ensure_expanded()

        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            code = item.data(0, Qt.ItemDataRole.UserRole)
            if code == module_code:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found:
                    return found
            return None

        for index in range(self.tree.topLevelItemCount()):
            found = walk(self.tree.topLevelItem(index))
            if not found:
                continue
            self.tree.setCurrentItem(found)
            parent = found.parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()
            break
