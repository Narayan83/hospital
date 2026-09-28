from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError

EVENTS = [
    ("patient_registered", "Patient Registered"),
    ("op_bill_created", "OP Bill Created"),
    ("lab_result_ready", "Lab Result Ready"),
    ("low_stock_alert", "Low Stock Alert"),
]


class NotificationSetupWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._user_rows: list[dict] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Notification Setup")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.addWidget(QLabel("Event"))
        self.event_combo = QComboBox()
        for code, label in EVENTS:
            self.event_combo.addItem(label, code)
        self.event_combo.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.event_combo, stretch=1)
        layout.addLayout(row)

        self.select_all = QCheckBox("Select All Users")
        self.select_all.stateChanged.connect(self._toggle_all)
        layout.addWidget(self.select_all)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Select", "User", "Email"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        save_btn = QPushButton("Save Notification Setup")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def refresh(self) -> None:
        event_code = self.event_combo.currentData()
        if not event_code:
            return
        try:
            data = self.api.get_notification_setup(event_code)
            self._user_rows = data.get("users", [])
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.table.setRowCount(len(self._user_rows))
        enabled_count = 0
        for row, user in enumerate(self._user_rows):
            checkbox = QCheckBox()
            checkbox.setChecked(user.get("is_enabled", False))
            checkbox.stateChanged.connect(self._update_select_all_state)
            self.table.setCellWidget(row, 0, checkbox)
            self.table.setItem(row, 1, QTableWidgetItem(user.get("full_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(user.get("email", "")))
            if user.get("is_enabled"):
                enabled_count += 1

        self.select_all.blockSignals(True)
        self.select_all.setChecked(enabled_count == len(self._user_rows) and len(self._user_rows) > 0)
        self.select_all.blockSignals(False)

    def _toggle_all(self, state: int) -> None:
        checked = state == int(Qt.CheckState.Checked)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox):
                widget.setChecked(checked)

    def _update_select_all_state(self) -> None:
        if self.table.rowCount() == 0:
            return
        all_checked = True
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and not widget.isChecked():
                all_checked = False
                break
        self.select_all.blockSignals(True)
        self.select_all.setChecked(all_checked)
        self.select_all.blockSignals(False)

    def _save(self) -> None:
        event_code = self.event_combo.currentData()
        recipients = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            user = self._user_rows[row]
            if isinstance(checkbox, QCheckBox):
                recipients.append({
                    "user_id": user["user_id"],
                    "is_enabled": checkbox.isChecked(),
                })
        try:
            self.api.save_notification_setup({"event_code": event_code, "recipients": recipients})
            QMessageBox.information(self, "Success", "Notification setup saved.")
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
