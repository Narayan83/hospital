from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import BORDER, BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY, INPUT_BG, SURFACE, TEXT, TEXT_MUTED


class ClearDatabaseDialog(QDialog):
    """Admin tool to wipe selected tables when handing the app to a new hospital.

    All tables are shown grouped, with day-to-day transactional data pre-ticked.
    Master/setup tables stay unticked so they can be reused for a similar
    hospital. Hospital information is protected and can never be cleared.
    """

    def __init__(self, api: ApiClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._checks: dict[str, QCheckBox] = {}
        self.setWindowTitle("Reset Database — New Hospital Setup")
        self.setMinimumSize(640, 640)
        self.setStyleSheet(f"background: {SURFACE}; color: {TEXT};")
        self._build_ui()
        self._load_tables()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Reset Database")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #991b1b;")
        layout.addWidget(heading)

        warn = QLabel(
            "This permanently deletes all rows in the selected tables and resets "
            "their numbering. Use it to get a fresh database for a NEW hospital.\n"
            "Tick what to reset; UNTICK any master data you want to keep "
            "(for example services, lab tests, pharmacy items). Hospital "
            "information, users and menus are always kept."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(warn)

        # quick selection buttons
        tools = QHBoxLayout()
        tools.setSpacing(6)
        for text, handler in (
            ("Transactions only", self._select_defaults),
            ("Select all", self._select_all),
            ("Clear selection", self._select_none),
        ):
            btn = QPushButton(text)
            btn.setStyleSheet(BTN_SECONDARY)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            tools.addWidget(btn)
        tools.addStretch()
        layout.addLayout(tools)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.summary_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: 2px solid {BORDER}; border-radius: 8px; background: {INPUT_BG}; }}")
        self._list_host = QWidget()
        self._list_host.setStyleSheet(f"background: {INPUT_BG};")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(10, 10, 10, 10)
        self._list_layout.setSpacing(2)
        scroll.setWidget(self._list_host)
        layout.addWidget(scroll, stretch=1)

        pwd_row = QHBoxLayout()
        pwd_label = QLabel("Maintenance password:")
        pwd_label.setStyleSheet("font-weight: 600;")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Required to confirm")
        self.password.setStyleSheet(
            f"QLineEdit {{ background: {INPUT_BG}; border: 2px solid {BORDER};"
            " border-radius: 6px; padding: 6px 10px; }"
        )
        pwd_row.addWidget(pwd_label)
        pwd_row.addWidget(self.password, stretch=1)
        layout.addLayout(pwd_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(BTN_SECONDARY)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        self.clear_btn = QPushButton("Reset Selected Tables")
        self.clear_btn.setStyleSheet(BTN_PRIMARY)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._confirm_and_clear)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

    def _clear_list(self) -> None:
        self._checks.clear()
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _load_tables(self) -> None:
        try:
            tables = self.api.list_db_tables()
        except ApiError as exc:
            QMessageBox.warning(self, "Reset Database", str(exc))
            self.clear_btn.setEnabled(False)
            return

        self._clear_list()
        current_group: str | None = None
        for info in tables:
            group = info.get("group", "Other")
            if group != current_group:
                current_group = group
                header = QLabel(group)
                header.setStyleSheet(
                    f"font-weight: 700; color: {TEXT}; margin-top: 8px;"
                    f" border-bottom: 1px solid {BORDER}; padding-bottom: 2px;"
                )
                self._list_layout.addWidget(header)

            name = info["name"]
            rows = info.get("row_count", 0)
            rows_text = "n/a" if rows is None or rows < 0 else f"{rows:,} rows"
            label = f"{info.get('label', name)}  —  {rows_text}"
            cb = QCheckBox(label)
            cb.setProperty("table_name", name)
            cb.toggled.connect(self._update_summary)
            if info.get("protected"):
                cb.setChecked(False)
                cb.setEnabled(False)
                cb.setText(f"{label}   (protected — always kept)")
                cb.setStyleSheet(f"color: {TEXT_MUTED};")
            else:
                cb.setChecked(bool(info.get("default_selected")))
                self._checks[name] = cb
            self._list_layout.addWidget(cb)
        self._list_layout.addStretch()
        self._update_summary()

    def _select_all(self) -> None:
        for cb in self._checks.values():
            cb.setChecked(True)

    def _select_none(self) -> None:
        for cb in self._checks.values():
            cb.setChecked(False)

    def _select_defaults(self) -> None:
        # Re-fetch keeps it simple and reflects current default classification.
        try:
            tables = {t["name"]: t for t in self.api.list_db_tables()}
        except ApiError:
            return
        for name, cb in self._checks.items():
            info = tables.get(name, {})
            cb.setChecked(bool(info.get("default_selected")))

    def _selected_tables(self) -> list[str]:
        return [name for name, cb in self._checks.items() if cb.isChecked()]

    def _update_summary(self) -> None:
        selected = self._selected_tables()
        self.summary_label.setText(f"{len(selected)} table(s) selected for reset.")
        self.clear_btn.setEnabled(bool(selected))

    def _confirm_and_clear(self) -> None:
        selected = self._selected_tables()
        if not selected:
            QMessageBox.information(self, "Reset Database", "Select at least one table to reset.")
            return
        password = self.password.text()
        if not password:
            QMessageBox.warning(self, "Reset Database", "Enter the maintenance password to confirm.")
            self.password.setFocus()
            return

        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Confirm Reset")
        confirm.setText(
            f"You are about to permanently delete all data in "
            f"{len(selected)} table(s).\n\nThis cannot be undone. Continue?"
        )
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        self.clear_btn.setEnabled(False)
        try:
            result = self.api.clear_db_tables(password=password, tables=selected)
        except ApiError as exc:
            self.clear_btn.setEnabled(True)
            QMessageBox.critical(self, "Reset Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Database Reset",
            result.get("message", "Selected tables reset.")
            + "\n\nPlease log out and log in again to refresh all screens.",
        )
        self.accept()
