"""Bundle / Panel master — group lab tests (and other bundles) under one service.

Clean two-list design: the left list shows every bundle with its members; the
right side shows the members already in the selected bundle and a search box to
add more. Billing the bundle expands to all member tests automatically.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session
from app.ui.pathology_display import pathology_item_label
from app.ui.styles import (
    BTN_DANGER,
    BTN_PRIMARY,
    BTN_SECONDARY,
    LABEL,
    PAGE_TITLE,
    SUBTITLE,
    TEXT_MUTED,
)


def _service_label(info: dict) -> str:
    return pathology_item_label(info)


def _type_item(is_bundle: bool) -> QTableWidgetItem:
    """A small colored pill-like cell to tell Test vs Bundle apart at a glance."""
    item = QTableWidgetItem("Bundle" if is_bundle else "Test")
    if is_bundle:
        item.setForeground(Qt.GlobalColor.darkMagenta)
    else:
        item.setForeground(Qt.GlobalColor.darkGreen)
    return item


class PathologyTestProfileWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._profiles: list[dict] = []
        self._tests: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self._member_ids: list[str] = []
        self._selected_id: str | None = None
        self._build_ui()

    # ----- UI -----------------------------------------------------------
    def _build_ui(self) -> None:
        from app.ui.responsive_layout import configure_splitter, get_density, paint_page_surface

        d = get_density()
        paint_page_surface(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(d.content_margin, d.content_margin, d.content_margin, d.content_margin)
        layout.setSpacing(d.section_spacing)

        heading = QLabel("Bundle / Panel")
        heading.setStyleSheet(PAGE_TITLE)
        layout.addWidget(heading)
        hint = QLabel(
            "A bundle groups several lab tests (e.g. Thyroid Profile = T3 + T4 + TSH) and may "
            "also contain other bundles. Set a fixed Price (members bill at 0), or leave Price 0 "
            "to bill the sum of members."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(SUBTITLE)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        configure_splitter(splitter, left_ratio=0.28)
        layout.addWidget(splitter, stretch=1)

        # ===== left: bundles list =====
        left_box = QGroupBox("Bundles")
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(8)
        self.bundle_search = QLineEdit()
        self.bundle_search.setPlaceholderText("🔍  Search bundle name or code...")
        self.bundle_search.setClearButtonEnabled(True)
        self.bundle_search.textChanged.connect(self._render_profiles)
        left_layout.addWidget(self.bundle_search)
        self.profile_list = QTableWidget(0, 3)
        self.profile_list.setHorizontalHeaderLabels(["Bundle", "Code", "Members"])
        self.profile_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.profile_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.profile_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tune_table(self.profile_list)
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profile_list.itemSelectionChanged.connect(self._on_select_profile)
        left_layout.addWidget(self.profile_list, stretch=1)
        new_btn = QPushButton("+  New Bundle")
        new_btn.setStyleSheet(BTN_SECONDARY)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._clear)
        left_layout.addWidget(new_btn)
        splitter.addWidget(left_box)

        # ===== right: editor =====
        from app.ui.styles import BG

        right = QWidget()
        paint_page_surface(right, color=BG)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(d.section_spacing)

        # --- bundle details (compact single row) ---
        form_box = QGroupBox("Bundle Details")
        form_row = QHBoxLayout(form_box)
        form_row.setSpacing(10)
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Thyroid Profile")
        self.price = QLineEdit("0")
        self.price.setPlaceholderText("0 = sum of members")
        self.price.setToolTip("0 = bill the sum of member prices.  >0 = one fixed bundle price.")
        self.price.setFixedWidth(140)
        self.sub_category = QComboBox()
        self.sub_category.setMinimumWidth(200)
        self.sub_category.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form_row.addWidget(self._field_label("Bundle Name *"))
        form_row.addWidget(self.name, stretch=2)
        form_row.addWidget(self._field_label("Price"))
        form_row.addWidget(self.price)
        form_row.addWidget(self._field_label("Sub Category"))
        form_row.addWidget(self.sub_category, stretch=1)
        right_layout.addWidget(form_box)

        # --- transfer area: available  [→ / ←]  members ---
        transfer = QHBoxLayout()
        transfer.setSpacing(8)

        # available (left of transfer)
        add_box = QGroupBox("Available — tests & bundles")
        add_layout = QVBoxLayout(add_box)
        add_layout.setSpacing(8)
        self.add_search = QLineEdit()
        self.add_search.setPlaceholderText("🔍  Search to add...")
        self.add_search.setClearButtonEnabled(True)
        self.add_search.textChanged.connect(self._render_add_list)
        add_layout.addWidget(self.add_search)
        self.add_table = QTableWidget(0, 4)
        self.add_table.setHorizontalHeaderLabels(["Name", "Code", "Type", "Price"])
        self.add_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.add_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.add_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.add_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tune_table(self.add_table)
        self.add_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.add_table.doubleClicked.connect(lambda *_: self._add_selected_member())
        add_layout.addWidget(self.add_table, stretch=1)
        transfer.addWidget(add_box, stretch=1)

        # transfer buttons (center)
        btn_col = QVBoxLayout()
        btn_col.addStretch()
        add_btn = QPushButton("Add  →")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedWidth(96)
        add_btn.setToolTip("Add the selected rows to this bundle (or double-click a row)")
        add_btn.clicked.connect(self._add_selected_member)
        remove_btn = QPushButton("←  Remove")
        remove_btn.setStyleSheet(BTN_SECONDARY)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setFixedWidth(96)
        remove_btn.setToolTip("Remove the selected members from this bundle")
        remove_btn.clicked.connect(self._remove_selected_member)
        btn_col.addWidget(add_btn)
        btn_col.addSpacing(8)
        btn_col.addWidget(remove_btn)
        btn_col.addStretch()
        transfer.addLayout(btn_col)

        # members (right of transfer)
        self.members_box = QGroupBox("In this bundle (0)")
        members_layout = QVBoxLayout(self.members_box)
        members_layout.setSpacing(8)
        self.members_table = QTableWidget(0, 5)
        self.members_table.setHorizontalHeaderLabels(["Order", "Member", "Code", "Type", "Price"])
        self.members_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.members_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.members_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.members_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.members_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._tune_table(self.members_table)
        self.members_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.members_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.members_table.itemChanged.connect(self._on_member_order_changed)
        members_layout.addWidget(self.members_table, stretch=1)
        order_row = QHBoxLayout()
        up_btn = QPushButton("Move Up")
        up_btn.setStyleSheet(BTN_SECONDARY)
        up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        up_btn.clicked.connect(lambda: self._move_member(-1))
        down_btn = QPushButton("Move Down")
        down_btn.setStyleSheet(BTN_SECONDARY)
        down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        down_btn.clicked.connect(lambda: self._move_member(1))
        order_row.addWidget(up_btn)
        order_row.addWidget(down_btn)
        order_row.addStretch()
        members_layout.addLayout(order_row)
        self.members_hint = QLabel(
            "Set Order (1, 2, 3…) or use Move Up/Down. Saved order is used on bills and reports."
        )
        self.members_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        members_layout.addWidget(self.members_hint)
        transfer.addWidget(self.members_box, stretch=1)

        right_layout.addLayout(transfer, stretch=1)

        # --- action bar ---
        action_row = QHBoxLayout()
        self.status = QLabel("Ready for a new bundle.")
        self.status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        action_row.addWidget(self.status, stretch=1)
        save_btn = QPushButton("Save Bundle")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(BTN_DANGER)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._delete)
        action_row.addWidget(delete_btn)
        action_row.addWidget(save_btn)
        right_layout.addLayout(action_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 820])

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(LABEL)
        return lbl

    @staticmethod
    def _tune_table(table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setDefaultSectionSize(30)

    # ----- data ---------------------------------------------------------
    def refresh(self) -> None:
        cache = get_session().cache
        self.sub_category.clear()
        self.sub_category.addItem("— None —", None)
        lab_id = None
        for cat in cache.service_categories if cache.loaded else []:
            if cat.get("code") == "LAB":
                lab_id = cat.get("id")
                break
        for sub in cache.service_sub_categories if cache.loaded else []:
            if not lab_id or sub.get("category_id") == lab_id:
                self.sub_category.addItem(sub.get("name", ""), sub.get("id"))

        try:
            self._tests = self.api.list_lab_tests()
            self._profiles = self.api.list_lab_profiles()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self._by_id = {}
        for test in self._tests:
            self._by_id[test.get("id")] = {**test, "is_bundle": False}
        for profile in self._profiles:
            self._by_id[profile.get("id")] = {**profile, "is_bundle": True}

        self._render_profiles()
        self._render_members()
        self._render_add_list()

    def _render_profiles(self) -> None:
        query = self.bundle_search.text().strip().lower()
        rows = [
            p
            for p in self._profiles
            if not query
            or query in (p.get("name") or "").lower()
            or query in (p.get("code") or "").lower()
        ]
        self.profile_list.setRowCount(len(rows))
        for row, profile in enumerate(rows):
            name_item = QTableWidgetItem(profile.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, profile.get("id"))
            self.profile_list.setItem(row, 0, name_item)
            self.profile_list.setItem(row, 1, QTableWidgetItem(profile.get("code") or ""))
            members = profile.get("members") or []
            names = ", ".join(_service_label(m) for m in members)
            members_item = QTableWidgetItem(names or "—")
            members_item.setToolTip(names)
            self.profile_list.setItem(row, 2, members_item)

    def _render_members(self) -> None:
        self.members_table.blockSignals(True)
        try:
            self.members_table.setRowCount(len(self._member_ids))
            for row, member_id in enumerate(self._member_ids):
                info = self._by_id.get(member_id, {})
                order_item = QTableWidgetItem(str(row + 1))
                order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                order_item.setData(Qt.ItemDataRole.UserRole, member_id)
                order_item.setFlags(
                    order_item.flags()
                    | Qt.ItemFlag.ItemIsEditable
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                self.members_table.setItem(row, 0, order_item)
                name_item = QTableWidgetItem(_service_label(info))
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item.setData(Qt.ItemDataRole.UserRole, member_id)
                self.members_table.setItem(row, 1, name_item)
                code_item = QTableWidgetItem(info.get("code") or "")
                code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.members_table.setItem(row, 2, code_item)
                type_item = _type_item(bool(info.get("is_bundle")))
                type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.members_table.setItem(row, 3, type_item)
                price_item = QTableWidgetItem(str(info.get("price", "")))
                price_item.setFlags(price_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.members_table.setItem(row, 4, price_item)
        finally:
            self.members_table.blockSignals(False)
        if hasattr(self, "members_box"):
            self.members_box.setTitle(f"In this bundle ({len(self._member_ids)})")

    def _on_member_order_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        try:
            new_order = int(item.text().strip())
        except ValueError:
            self._render_members()
            return
        if new_order < 1:
            new_order = 1
        row = item.row()
        if row < 0 or row >= len(self._member_ids):
            return
        member_id = self._member_ids.pop(row)
        target = min(max(new_order - 1, 0), len(self._member_ids))
        self._member_ids.insert(target, member_id)
        self._render_members()

    def _move_member(self, delta: int) -> None:
        rows = sorted({i.row() for i in self.members_table.selectedItems()})
        if len(rows) != 1:
            return
        row = rows[0]
        target = row + delta
        if target < 0 or target >= len(self._member_ids):
            return
        self._member_ids[row], self._member_ids[target] = (
            self._member_ids[target],
            self._member_ids[row],
        )
        self._render_members()
        self.members_table.selectRow(target)

    def _render_add_list(self) -> None:
        query = self.add_search.text().strip().lower()
        rows = []
        for info in self._by_id.values():
            if info.get("id") in self._member_ids:
                continue
            if info.get("id") == self._selected_id:
                continue  # a bundle can't contain itself
            if query and query not in (info.get("name") or "").lower():
                if query not in (info.get("code") or "").lower():
                    continue
            rows.append(info)
        rows.sort(key=lambda x: (not x.get("is_bundle"), (x.get("name") or "").casefold()))
        self.add_table.setRowCount(len(rows))
        for row, info in enumerate(rows):
            name_item = QTableWidgetItem(_service_label(info))
            name_item.setData(Qt.ItemDataRole.UserRole, info.get("id"))
            self.add_table.setItem(row, 0, name_item)
            self.add_table.setItem(row, 1, QTableWidgetItem(info.get("code") or ""))
            self.add_table.setItem(row, 2, _type_item(bool(info.get("is_bundle"))))
            self.add_table.setItem(row, 3, QTableWidgetItem(str(info.get("price", ""))))

    # ----- actions ------------------------------------------------------
    def _on_select_profile(self) -> None:
        items = self.profile_list.selectedItems()
        if not items:
            return
        profile_id = self.profile_list.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._profiles if p.get("id") == profile_id), None)
        if not profile:
            return
        self._selected_id = profile_id
        self.name.setText(profile.get("name", ""))
        self.price.setText(str(profile.get("price", "0")))
        sidx = self.sub_category.findData(profile.get("sub_category_id"))
        self.sub_category.setCurrentIndex(sidx if sidx >= 0 else 0)
        self._member_ids = [m.get("id") for m in (profile.get("members") or [])]
        self.add_search.clear()
        self._render_members()
        self._render_add_list()
        self.status.setText(f"Editing bundle: {profile.get('name')}")

    def _add_selected_member(self) -> None:
        rows = sorted({i.row() for i in self.add_table.selectedItems()})
        if not rows:
            return
        for r in rows:
            item = self.add_table.item(r, 0)
            if not item:
                continue
            member_id = item.data(Qt.ItemDataRole.UserRole)
            if member_id and member_id not in self._member_ids:
                self._member_ids.append(member_id)
        self._render_members()
        self._render_add_list()

    def _remove_selected_member(self) -> None:
        rows = sorted({i.row() for i in self.members_table.selectedItems()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self._member_ids):
                self._member_ids.pop(r)
        self._render_members()
        self._render_add_list()

    def _save(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Validation", "Bundle name is required.")
            return
        if not self._member_ids:
            QMessageBox.warning(self, "Validation", "Add at least one member to the bundle.")
            return
        payload = {
            "name": self.name.text().strip(),
            "price": self.price.text().strip() or "0",
            "sub_category_id": self.sub_category.currentData(),
            "member_test_ids": list(self._member_ids),
        }
        try:
            if self._selected_id:
                self.api.update_lab_profile(self._selected_id, payload)
            else:
                self.api.create_lab_profile(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.status.setText(f"Saved bundle: {payload['name']}")
        self._clear()
        self.refresh()

    def _delete(self) -> None:
        if not self._selected_id:
            QMessageBox.warning(self, "Validation", "Select a bundle to delete.")
            return
        if QMessageBox.question(self, "Confirm", "Delete this bundle?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_lab_profile(self._selected_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._clear()
        self.refresh()

    def _clear(self) -> None:
        self._selected_id = None
        self._member_ids = []
        self.profile_list.clearSelection()
        self.name.clear()
        self.price.setText("0")
        self.sub_category.setCurrentIndex(0)
        self.add_search.clear()
        self._render_members()
        self._render_add_list()
        self.status.setText("Ready for a new bundle.")
