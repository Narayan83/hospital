from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session

PERM_KEYS = ("can_view", "can_create", "can_update", "can_delete")
PERM_COLUMNS = {1: "can_view", 2: "can_create", 3: "can_update", 4: "can_delete"}


class RoleMenuPermissionsWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._menus: list[dict] = []
        self._perm_by_menu: dict[str, dict] = {}
        self._permissions_role_id: str | None = None

        # Lookups built while constructing the tree.
        self._all_menu_ids: list[str] = []
        self._cbs: dict[str, dict[str, QCheckBox]] = {}
        self._parent_of: dict[str, str | None] = {}
        self._children_of: dict[str, list[str]] = {}
        self._descendants: dict[str, list[str]] = {}
        self._item_button: dict[QTreeWidgetItem, QToolButton] = {}
        self._tree_built = False
        self._updating = False

        layout = QVBoxLayout(self)
        heading = QLabel("Role Menu Permissions")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.addWidget(QLabel("Role"))
        self.role_combo = QComboBox()
        self.role_combo.currentIndexChanged.connect(self._load_role_permissions)
        row.addWidget(self.role_combo, stretch=1)

        expand_btn = QPushButton("Expand All")
        expand_btn.clicked.connect(lambda: self.tree.expandAll())
        collapse_btn = QPushButton("Collapse All")
        collapse_btn.clicked.connect(lambda: self.tree.collapseAll())
        row.addWidget(expand_btn)
        row.addWidget(collapse_btn)
        layout.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Menu", "View", "Create", "Update", "Delete"])
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(26)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.tree.setColumnWidth(col, 90)
        for col in (1, 2, 3, 4):
            self.tree.headerItem().setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)
        self.tree.itemExpanded.connect(lambda it: self._set_button_glyph(it, "−"))
        self.tree.itemCollapsed.connect(lambda it: self._set_button_glyph(it, "+"))
        layout.addWidget(self.tree)

        save_btn = QPushButton("Save Permissions")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loading or not cache.loaded:
            return

        if not self._tree_built:
            self._menus = self._load_menu_tree()
            if self._menus:
                self._build_tree()

        roles = cache.roles
        current_role = self.role_combo.currentData()
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        for role in roles:
            self.role_combo.addItem(role["role_name"], role["id"])
        if current_role:
            idx = self.role_combo.findData(current_role)
            if idx >= 0:
                self.role_combo.setCurrentIndex(idx)
        self.role_combo.blockSignals(False)
        role_id = self.role_combo.currentData()
        if role_id and (role_id != self._permissions_role_id or not self._tree_built):
            self._load_role_permissions()

    # ----- tree construction -------------------------------------------------
    def _load_menu_tree(self) -> list[dict]:
        """Fetch ALL active menus so any menu can be granted to a role.

        Falls back to the logged-in user's permitted menu tree if the API call
        fails for any reason.
        """
        try:
            flat = self.api.list_menus()
        except ApiError:
            return list(get_session().menus)

        by_parent: dict[str | None, list[dict]] = {}
        for menu in flat:
            by_parent.setdefault(menu.get("parent_id"), []).append(menu)

        def build(parent_id: str | None) -> list[dict]:
            children = sorted(
                by_parent.get(parent_id, []),
                key=lambda m: (m.get("sort_order") or 0, m.get("label") or ""),
            )
            return [
                {
                    "id": menu["id"],
                    "code": menu.get("code"),
                    "label": menu.get("label"),
                    "children": build(menu["id"]),
                }
                for menu in children
            ]

        return build(None)

    def _build_tree(self) -> None:
        self.tree.clear()
        self._all_menu_ids.clear()
        self._cbs.clear()
        self._parent_of.clear()
        self._children_of.clear()
        self._descendants.clear()
        self._item_button.clear()

        for node in self._menus:
            self._add_item(None, None, node)

        # Pre-compute descendants for fast cascade.
        for menu_id in self._all_menu_ids:
            self._descendants[menu_id] = self._collect_descendants(menu_id)

        # Start collapsed: each main menu shows a "+" button to expand.
        self.tree.collapseAll()
        self._tree_built = True

    def _add_item(
        self,
        parent_item: QTreeWidgetItem | None,
        parent_menu_id: str | None,
        node: dict,
    ) -> None:
        menu_id = node["id"]
        label = node.get("label") or node.get("code") or ""
        children = node.get("children") or []

        item = QTreeWidgetItem()
        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        if children:
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            btn = QToolButton()
            btn.setText("+")
            btn.setFixedSize(20, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, it=item: it.setExpanded(not it.isExpanded()))
            lbl = QLabel(label)
            lbl.setStyleSheet("font-weight: 600;")
            h.addWidget(btn)
            h.addWidget(lbl)
            h.addStretch()
            self.tree.setItemWidget(item, 0, container)
            self._item_button[item] = btn
        else:
            item.setText(0, label)

        self._cbs[menu_id] = {}
        for col, key in PERM_COLUMNS.items():
            holder, cb = self._make_checkbox(menu_id, key)
            self.tree.setItemWidget(item, col, holder)
            self._cbs[menu_id][key] = cb

        self._all_menu_ids.append(menu_id)
        self._parent_of[menu_id] = parent_menu_id
        self._children_of.setdefault(menu_id, [])
        if parent_menu_id is not None:
            self._children_of.setdefault(parent_menu_id, []).append(menu_id)

        for child in children:
            self._add_item(item, menu_id, child)

    def _make_checkbox(self, menu_id: str, key: str) -> tuple[QWidget, QCheckBox]:
        cb = QCheckBox()
        cb.toggled.connect(
            lambda checked, m=menu_id, k=key: self._on_toggle(m, k, checked)
        )
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        lay.addWidget(cb)
        lay.addStretch()
        return holder, cb

    def _collect_descendants(self, menu_id: str) -> list[str]:
        result: list[str] = []
        for child in self._children_of.get(menu_id, []):
            result.append(child)
            result.extend(self._collect_descendants(child))
        return result

    def _set_button_glyph(self, item: QTreeWidgetItem, glyph: str) -> None:
        btn = self._item_button.get(item)
        if btn is not None:
            btn.setText(glyph)

    # ----- cascade behaviour -------------------------------------------------
    def _on_toggle(self, menu_id: str, key: str, checked: bool) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            # Checking/unchecking a main menu cascades to all its sub-menus.
            for child_id in self._descendants.get(menu_id, []):
                cb = self._cbs[child_id][key]
                if cb.isChecked() != checked:
                    cb.setChecked(checked)

            # A selected sub-menu auto-selects its parent chain; clearing the
            # last selected sub-menu clears the parent again.
            parent = self._parent_of.get(menu_id)
            while parent is not None:
                any_child = any(
                    self._cbs[c][key].isChecked()
                    for c in self._children_of.get(parent, [])
                )
                pcb = self._cbs[parent][key]
                if pcb.isChecked() != any_child:
                    pcb.setChecked(any_child)
                parent = self._parent_of.get(parent)
        finally:
            self._updating = False

    # ----- load / save -------------------------------------------------------
    def _load_role_permissions(self) -> None:
        role_id = self.role_combo.currentData()
        if not role_id:
            self._permissions_role_id = None
            self._clear_all_checks()
            return
        try:
            existing = self.api.get_role_permissions(role_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self._permissions_role_id = role_id
        self._perm_by_menu = {row["menu_id"]: row for row in existing}

        self._updating = True
        try:
            for menu_id in self._all_menu_ids:
                perms = self._perm_by_menu.get(menu_id, {})
                for key in PERM_KEYS:
                    cb = self._cbs[menu_id][key]
                    cb.setChecked(bool(perms.get(key, False)))
        finally:
            self._updating = False

    def _clear_all_checks(self) -> None:
        self._updating = True
        try:
            for menu_id in self._all_menu_ids:
                for key in PERM_KEYS:
                    self._cbs[menu_id][key].setChecked(False)
        finally:
            self._updating = False

    def _save(self) -> None:
        role_id = self.role_combo.currentData()
        if not role_id:
            QMessageBox.warning(self, "Validation", "Select a role.")
            return

        permissions = []
        for menu_id in self._all_menu_ids:
            row_perms = {"menu_id": menu_id}
            for key in PERM_KEYS:
                cb = self._cbs[menu_id][key]
                row_perms[key] = cb.isChecked()
            permissions.append(row_perms)

        try:
            self.api.set_role_permissions(role_id, permissions)
            QMessageBox.information(
                self,
                "Saved",
                "Permissions saved. Affected users should log in again to refresh menus.",
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
