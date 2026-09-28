from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
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
from app.session import get_session


class RoleManagementWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        layout = QVBoxLayout(self)
        heading = QLabel("Role Creation")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        form_box = QGroupBox("New Role")
        form = QFormLayout(form_box)
        self.role_name = QLineEdit()
        self.description = QLineEdit()
        form.addRow("Role Name *", self.role_name)
        form.addRow("Description", self.description)
        layout.addWidget(form_box)

        save_btn = QPushButton("Save Role")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Role Name", "Description", "Active"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loading or not cache.loaded:
            return
        roles = cache.roles
        self.table.setRowCount(len(roles))
        for row, role in enumerate(roles):
            self.table.setItem(row, 0, QTableWidgetItem(role.get("role_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(role.get("description") or ""))
            self.table.setItem(row, 2, QTableWidgetItem("Yes" if role.get("is_active") else "No"))

    def _save(self) -> None:
        if not self.role_name.text().strip():
            QMessageBox.warning(self, "Validation", "Role name is required.")
            return
        try:
            created = self.api.create_role({
                "role_name": self.role_name.text().strip(),
                "description": self.description.text().strip() or None,
            })
            get_session().cache.roles.append(created)
            self.role_name.clear()
            self.description.clear()
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
