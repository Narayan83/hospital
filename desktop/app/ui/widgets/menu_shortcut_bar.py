"""Per-screen shortcut buttons, same idea as GenERP's menu shortcut bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session

_CHIP = """
QPushButton {
    background: #ffffff;
    color: #1a222a;
    border: 1px solid #d8dee6;
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
"""
_ADD = """
QPushButton {
    background: #0d9488;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover { background: #0f766e; }
"""


class _PinChip(QWidget):
    open_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, shortcut_id: str, module_code: str, label: str):
        super().__init__()
        self._module_code = module_code
        self._shortcut_id = shortcut_id
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        open_btn = QPushButton(label)
        open_btn.setStyleSheet(_CHIP + "QPushButton { border-top-right-radius: 0; border-bottom-right-radius: 0; }")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setToolTip(f"Open {label}")
        open_btn.clicked.connect(lambda: self.open_requested.emit(self._module_code))
        remove_btn = QPushButton("×")
        remove_btn.setFixedWidth(26)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setToolTip(f"Remove {label} shortcut. The menu stays in the sidebar.")
        remove_btn.setStyleSheet(
            _CHIP
            + "QPushButton { border-top-left-radius: 0; border-bottom-left-radius: 0;"
            + " color: #b91c1c; padding: 4px 0; }"
        )
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._shortcut_id))
        row.addWidget(open_btn)
        row.addWidget(remove_btn)


class MenuShortcutBar(QFrame):
    module_requested = Signal(str)
    configure_requested = Signal(str)

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._host = "dashboard"
        self._shortcuts: list[dict] = []
        self.setObjectName("menuShortcutBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Scope the rule to this bar. A bare QFrame rule also styles the combo
        # popup, which stops the menu list from accepting a selection.
        self.setStyleSheet("#menuShortcutBar { background: transparent; border: none; }")
        self._load_error = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 6)
        row.setSpacing(6)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(6)
        row.addLayout(self._chips, stretch=1)
        self._pick = QComboBox()
        self._pick.setObjectName("menuShortcutPick")
        self._pick.setMinimumWidth(220)
        self._pick.setMaxVisibleItems(18)
        self._pick.setStyleSheet(
            "QComboBox#menuShortcutPick {"
            " background: #ffffff; color: #1a222a; border: 1px solid #d8dee6;"
            " border-radius: 8px; padding: 4px 8px; min-height: 28px;"
            "}"
            "QComboBox#menuShortcutPick QAbstractItemView {"
            " background: #ffffff; color: #1a222a; selection-background-color: #dbeafe;"
            "}"
        )
        self._pick.activated.connect(self._pin)
        row.addWidget(self._pick)
        add_btn = QPushButton("Pin")
        add_btn.setStyleSheet(_ADD)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._pin)
        row.addWidget(add_btn)
        setup_btn = QPushButton("Edit shortcuts")
        setup_btn.setStyleSheet(_CHIP)
        setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setup_btn.clicked.connect(lambda: self.configure_requested.emit(self._host))
        row.addWidget(setup_btn)

    def set_host(self, host_code: str) -> None:
        self._host = (host_code or "dashboard").strip().lower() or "dashboard"
        self.reload()

    def reload(self) -> None:
        allowed = get_session().allowed_menu_codes()
        try:
            shortcuts = self.api.list_dashboard_shortcuts(active_only=True, host_code=self._host)
            menus = self.api.list_dashboard_shortcut_menus(host_code=self._host)
            self._load_error = ""
        except ApiError as exc:
            shortcuts, menus = [], []
            self._load_error = str(exc)
        self._shortcuts = [
            row
            for row in shortcuts
            if not str(row.get("module_code") or "").startswith("_")
            and (not allowed or row.get("module_code") in allowed)
        ]
        used = {row.get("module_code") for row in self._shortcuts}
        self._pick.blockSignals(True)
        self._pick.clear()
        for menu in menus:
            code = menu.get("code")
            if not code or code in used:
                continue
            if allowed and code not in allowed:
                continue
            self._pick.addItem(menu.get("label") or code, code)
        if self._pick.count() == 0:
            self._pick.addItem("No menus available to pin", None)
        else:
            self._pick.insertItem(0, "Choose a menu to pin", None)
        self._pick.setCurrentIndex(0)
        self._pick.blockSignals(False)
        self._rebuild_chips()

    def _rebuild_chips(self) -> None:
        while self._chips.count():
            item = self._chips.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._shortcuts:
            empty = QLabel("No shortcuts on this screen")
            empty.setStyleSheet("color: #6b7280; font-size: 12px;")
            self._chips.addWidget(empty)
            return
        for row in self._shortcuts:
            code = row.get("module_code") or ""
            shortcut_id = str(row.get("id") or "")
            chip = _PinChip(shortcut_id, code, row.get("button_label") or code)
            chip.open_requested.connect(self.module_requested.emit)
            chip.remove_requested.connect(self._unpin)
            self._chips.addWidget(chip)
        self._chips.addStretch(1)

    def _unpin(self, shortcut_id: str) -> None:
        if not shortcut_id:
            return
        try:
            self.api.delete_dashboard_shortcut(shortcut_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Shortcuts", str(exc))
            return
        self.reload()

    def _pin(self, index: int = -1) -> None:
        picked_from_list = index >= 0
        if not picked_from_list:
            index = self._pick.currentIndex()
        code = self._pick.itemData(index) if index >= 0 else None
        label = self._pick.itemText(index).strip() if index >= 0 else ""
        if not code:
            if picked_from_list:
                return
            if self._load_error:
                QMessageBox.warning(
                    self,
                    "Shortcuts",
                    f"Menus could not be loaded.\n\n{self._load_error}",
                )
            elif self._pick.count() <= 1:
                QMessageBox.information(
                    self,
                    "Shortcuts",
                    "Every menu you can open is already pinned on this screen.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Shortcuts",
                    "Open the menu list and choose the screen you want to pin.",
                )
            return
        if label.lower().startswith("choose a menu"):
            label = code
        try:
            self.api.create_dashboard_shortcut(
                {
                    "host_code": self._host,
                    "module_code": str(code),
                    "button_label": label or str(code),
                    "sort_order": len(self._shortcuts) + 1,
                    "is_active": True,
                }
            )
        except ApiError as exc:
            if exc.status_code in (404, 405):
                if self._pin_via_save(str(code), label or str(code)):
                    return
            QMessageBox.warning(self, "Shortcuts", str(exc) or "Could not pin that menu.")
            return
        self.reload()

    def _pin_via_save(self, code: str, label: str) -> bool:
        """Older servers only accept the full shortcut list, not a single pin."""
        try:
            current = self.api.list_dashboard_shortcuts(active_only=False, host_code=self._host)
        except ApiError:
            current = list(self._shortcuts)
        items = []
        for row in current:
            module_code = str(row.get("module_code") or "")
            if not module_code or module_code.startswith("_") or module_code == code:
                continue
            items.append(
                {
                    "module_code": module_code,
                    "button_label": row.get("button_label") or module_code,
                    "description": row.get("description"),
                    "sort_order": len(items) + 1,
                    "is_active": bool(row.get("is_active", True)),
                }
            )
        items.append(
            {
                "module_code": code,
                "button_label": label,
                "description": None,
                "sort_order": len(items) + 1,
                "is_active": True,
            }
        )
        try:
            self.api.save_dashboard_shortcuts({"host_code": self._host, "items": items})
        except ApiError as exc:
            QMessageBox.warning(self, "Shortcuts", str(exc) or "Could not pin that menu.")
            return True
        self.reload()
        return True
