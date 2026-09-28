from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
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


class DashboardShortcutSetupWidget(QWidget):
    """Configure which menus appear as dashboard shortcut buttons."""

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._menus: list[dict] = []
        self._host = "dashboard"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        heading = QLabel("Menu Shortcuts")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Each screen has its own shortcut buttons, saved for your login. "
                "Pick the screen, then choose which menus appear as buttons on it. "
                "Removing a shortcut only unpins the button — the menu stays in the sidebar."
            )
        )
        layout.addWidget(QLabel(""))
        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Shortcuts for"))
        self.host_combo = QComboBox()
        self.host_combo.setMinimumWidth(280)
        self.host_combo.currentIndexChanged.connect(self._on_host_changed)
        host_row.addWidget(self.host_combo, stretch=1)
        host_row.addStretch()
        layout.addLayout(host_row)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Menu"))
        self.menu_combo = QComboBox()
        self.menu_combo.setMinimumWidth(260)
        add_row.addWidget(self.menu_combo, stretch=2)
        add_row.addWidget(QLabel("Button name"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Shown on dashboard button")
        add_row.addWidget(self.label_edit, stretch=1)
        add_btn = QPushButton("Add to Shortcuts")
        add_btn.clicked.connect(self._add_shortcut)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["#", "Menu", "Button Name", "Description", "Active"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(4, 60)
        layout.addWidget(self.table, stretch=1)

        actions = QHBoxLayout()
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(lambda: self._move_row(-1))
        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(lambda: self._move_row(1))
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_row)
        save_btn = QPushButton("Save Shortcuts")
        save_btn.clicked.connect(self._save)
        actions.addWidget(up_btn)
        actions.addWidget(down_btn)
        actions.addWidget(remove_btn)
        actions.addStretch()
        actions.addWidget(save_btn)
        layout.addLayout(actions)

        self.menu_combo.currentIndexChanged.connect(self._on_menu_changed)
        self._load_hosts()
        self.refresh()

    def set_host(self, host_code: str) -> None:
        host = (host_code or "dashboard").strip().lower() or "dashboard"
        self._host = host
        index = self.host_combo.findData(host)
        self.host_combo.blockSignals(True)
        if index < 0:
            self.host_combo.addItem(host.replace("_", " ").title(), host)
            index = self.host_combo.findData(host)
        if index >= 0:
            self.host_combo.setCurrentIndex(index)
        self.host_combo.blockSignals(False)
        self.refresh()

    def _load_hosts(self) -> None:
        self.host_combo.blockSignals(True)
        self.host_combo.clear()
        self.host_combo.addItem("Dashboard", "dashboard")
        try:
            menus = self.api.list_dashboard_shortcut_menus(host_code="dashboard")
        except ApiError:
            menus = []
        for menu in menus:
            code = menu.get("code")
            if code:
                self.host_combo.addItem(menu.get("label") or code, code)
        index = self.host_combo.findData(self._host)
        self.host_combo.setCurrentIndex(index if index >= 0 else 0)
        self._host = self.host_combo.currentData() or "dashboard"
        self.host_combo.blockSignals(False)

    def _on_host_changed(self) -> None:
        host = self.host_combo.currentData()
        if not host or host == self._host:
            return
        self._host = host
        self.refresh()

    def refresh(self) -> None:
        try:
            self._menus = self.api.list_dashboard_shortcut_menus(host_code=self._host)
            shortcuts = self.api.list_dashboard_shortcuts(active_only=False, host_code=self._host)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.menu_combo.blockSignals(True)
        self.menu_combo.clear()
        for menu in self._menus:
            if menu.get("code") in {"dashboard", "dashboard_shortcut_setup"}:
                continue
            self.menu_combo.addItem(menu.get("label", ""), menu.get("code"))
        self.menu_combo.blockSignals(False)
        self._on_menu_changed()

        self.table.setRowCount(0)
        for item in shortcuts:
            self._append_row(
                module_code=item.get("module_code", ""),
                button_label=item.get("button_label", ""),
                description=item.get("description") or "",
                is_active=bool(item.get("is_active", True)),
            )
        self._renumber()

    def _on_menu_changed(self) -> None:
        label = self.menu_combo.currentText().strip()
        if label and not self.label_edit.text().strip():
            self.label_edit.setText(label)

    def _append_row(
        self,
        *,
        module_code: str,
        button_label: str,
        description: str = "",
        is_active: bool = True,
    ) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        order_item = QTableWidgetItem(str(row + 1))
        order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        order_item.setData(Qt.ItemDataRole.UserRole, module_code)
        self.table.setItem(row, 0, order_item)

        menu_label = next(
            (m.get("label", module_code) for m in self._menus if m.get("code") == module_code),
            module_code,
        )
        menu_item = QTableWidgetItem(str(menu_label))
        menu_item.setFlags(menu_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 1, menu_item)

        self.table.setItem(row, 2, QTableWidgetItem(button_label))
        self.table.setItem(row, 3, QTableWidgetItem(description))

        active = QCheckBox()
        active.setChecked(is_active)
        wrap = QWidget()
        wrap_layout = QHBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrap_layout.addWidget(active)
        self.table.setCellWidget(row, 4, wrap)

    def _add_shortcut(self) -> None:
        module_code = self.menu_combo.currentData()
        if not module_code:
            QMessageBox.warning(self, "Validation", "Select a menu to add.")
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == module_code:
                QMessageBox.information(self, "Already added", "That menu is already in shortcuts.")
                return
        label = self.label_edit.text().strip() or self.menu_combo.currentText().strip()
        if not label:
            QMessageBox.warning(self, "Validation", "Enter a button name.")
            return
        self._append_row(module_code=module_code, button_label=label)
        self._renumber()
        self.label_edit.clear()
        self._on_menu_changed()

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self._renumber()

    def _move_row(self, delta: int) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.table.rowCount():
            return
        self._swap_rows(row, target)
        self.table.selectRow(target)
        self._renumber()

    def _swap_rows(self, a: int, b: int) -> None:
        def cell_text(r: int, c: int) -> str:
            item = self.table.item(r, c)
            return item.text() if item else ""

        def cell_code(r: int) -> str:
            item = self.table.item(r, 0)
            return item.data(Qt.ItemDataRole.UserRole) if item else ""

        def cell_active(r: int) -> bool:
            wrap = self.table.cellWidget(r, 4)
            if wrap:
                checkbox = wrap.findChild(QCheckBox)
                if checkbox:
                    return checkbox.isChecked()
            return True

        a_data = (cell_code(a), cell_text(a, 1), cell_text(a, 2), cell_text(a, 3), cell_active(a))
        b_data = (cell_code(b), cell_text(b, 1), cell_text(b, 2), cell_text(b, 3), cell_active(b))

        for row, data in ((a, b_data), (b, a_data)):
            code, menu_label, button, desc, active = data
            order_item = QTableWidgetItem(str(row + 1))
            order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            order_item.setData(Qt.ItemDataRole.UserRole, code)
            self.table.setItem(row, 0, order_item)
            menu_item = QTableWidgetItem(menu_label)
            menu_item.setFlags(menu_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, menu_item)
            self.table.setItem(row, 2, QTableWidgetItem(button))
            self.table.setItem(row, 3, QTableWidgetItem(desc))
            checkbox = QCheckBox()
            checkbox.setChecked(active)
            wrap = QWidget()
            wrap_layout = QHBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wrap_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 4, wrap)

    def _renumber(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setText(str(row + 1))

    def _collect_items(self) -> list[dict]:
        items = []
        for row in range(self.table.rowCount()):
            order_item = self.table.item(row, 0)
            label_item = self.table.item(row, 2)
            desc_item = self.table.item(row, 3)
            if not order_item or not label_item:
                continue
            module_code = order_item.data(Qt.ItemDataRole.UserRole)
            button_label = label_item.text().strip()
            if not module_code or not button_label:
                continue
            active = True
            wrap = self.table.cellWidget(row, 4)
            if wrap:
                checkbox = wrap.findChild(QCheckBox)
                if checkbox:
                    active = checkbox.isChecked()
            items.append(
                {
                    "module_code": module_code,
                    "button_label": button_label,
                    "description": (desc_item.text().strip() if desc_item else "") or None,
                    "sort_order": row + 1,
                    "is_active": active,
                }
            )
        return items

    def _save(self) -> None:
        items = self._collect_items()
        try:
            self.api.save_dashboard_shortcuts({"host_code": self._host, "items": items})
            QMessageBox.information(self, "Success", "Shortcuts saved for this screen.")
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
