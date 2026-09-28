from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session


class UserRoleMappingWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._users: list[dict] = []
        self._roles: list[dict] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Role Mapping to User")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        form_box = QGroupBox("Assign Role")
        form = QFormLayout(form_box)
        self.user_combo = QComboBox()
        self.role_combo = QComboBox()
        self.priority = QSpinBox()
        self.priority.setRange(1, 99)
        self.priority.setValue(1)
        form.addRow("User *", self.user_combo)
        form.addRow("Role *", self.role_combo)
        form.addRow("Priority", self.priority)
        layout.addWidget(form_box)

        assign_btn = QPushButton("Assign Role")
        assign_btn.clicked.connect(self._assign)
        layout.addWidget(assign_btn)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Role", "Priority", "Mapping Id", ""])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.user_combo.currentIndexChanged.connect(self._load_mappings)

    def refresh(self) -> None:
        cache = get_session().cache
        if not cache.loaded:
            return

        self._users = list(cache.users)
        self._roles = list(cache.roles)

        current_user = self.user_combo.currentData()
        self.user_combo.blockSignals(True)
        self.user_combo.clear()
        for user in self._users:
            if not user.get("is_active"):
                continue
            self.user_combo.addItem(f"{user.get('full_name')} ({user.get('email')})", user.get("id"))
        if current_user:
            idx = self.user_combo.findData(current_user)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        self.user_combo.blockSignals(False)

        self.role_combo.clear()
        for role in self._roles:
            self.role_combo.addItem(role["role_name"], role["id"])

        self._load_mappings()

    def _load_mappings(self) -> None:
        user_id = self.user_combo.currentData()
        if not user_id:
            self.table.setRowCount(0)
            return
        try:
            mappings = self.api.list_user_roles(user_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self.table.setRowCount(len(mappings))
        for row, mapping in enumerate(mappings):
            self.table.setItem(row, 0, QTableWidgetItem(mapping.get("role_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(mapping.get("priority", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(mapping.get("id", "")))

            remove_btn = QPushButton("Remove")
            mapping_id = mapping.get("id")
            remove_btn.clicked.connect(lambda _checked=False, mid=mapping_id: self._remove(mid))
            self.table.setCellWidget(row, 3, remove_btn)

    def _assign(self) -> None:
        user_id = self.user_combo.currentData()
        role_id = self.role_combo.currentData()
        if not user_id or not role_id:
            QMessageBox.warning(self, "Validation", "Select user and role.")
            return
        try:
            self.api.assign_user_role({
                "user_id": user_id,
                "role_id": role_id,
                "priority": self.priority.value(),
            })
            self._load_mappings()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _remove(self, mapping_id: str) -> None:
        if not mapping_id:
            return
        try:
            self.api.remove_user_role(mapping_id)
            self._load_mappings()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
