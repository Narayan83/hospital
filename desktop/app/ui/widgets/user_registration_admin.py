from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
from app.services.master_cache import refresh_users_cache
from app.session import get_session


class UserRegistrationAdminWidget(QWidget):
    MODE_CREATE = "Create User"
    MODE_MODIFY = "Modify User"
    MODE_DELETE = "Delete User"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._users: list[dict] = []
        self._user_types: list[dict] = []
        self._doctors: list[dict] = []
        self._selected_user_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("User Addition / Modification")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        top_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top_row.addWidget(QLabel("Action"))
        top_row.addWidget(self.mode_combo, stretch=1)

        self.user_combo = QComboBox()
        self.user_combo.setEnabled(False)
        self.user_combo.currentIndexChanged.connect(self._on_user_selected)
        top_row.addWidget(QLabel("Select User"))
        top_row.addWidget(self.user_combo, stretch=2)
        layout.addLayout(top_row)

        form_box = QGroupBox("User Details")
        form = QFormLayout(form_box)

        self.full_name = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.user_type_combo = QComboBox()
        self.user_type_combo.currentIndexChanged.connect(self._on_user_type_changed)

        self.doctor_combo = QComboBox()
        self.doctor_row_label = QLabel("If Doctor, select doctor")

        form.addRow("Full Name *", self.full_name)
        form.addRow("Email (Login) *", self.email)
        form.addRow("Phone", self.phone)
        form.addRow("User Type *", self.user_type_combo)
        form.addRow(self.doctor_row_label, self.doctor_combo)
        form.addRow("Password", self.password)
        form.addRow("Confirm Password", self.confirm_password)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Email", "User Type", "Doctor", "Active", "Updated"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        layout.addWidget(self.table)

        self._on_mode_changed(self.mode_combo.currentText())

    def refresh(self) -> None:
        """Instant — reads from local cache (loaded in background after login)."""
        cache = get_session().cache
        if cache.loading:
            return
        if not cache.loaded:
            return

        self._user_types = list(cache.user_types)
        self._doctors = list(cache.doctors)
        self._users = list(cache.users)
        self._load_user_types()
        self._load_doctors()
        self._load_users_table()
        self._load_user_combo()
        self._on_user_type_changed()

    def _reload_users_from_server(self) -> None:
        try:
            refresh_users_cache(self.api)
            self._users = list(get_session().cache.users)
            self._load_users_table()
            self._load_user_combo()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _load_user_types(self) -> None:
        current_id = self.user_type_combo.currentData()
        self.user_type_combo.clear()
        for item in self._user_types:
            self.user_type_combo.addItem(item["name"], item["id"])
        if current_id:
            idx = self.user_type_combo.findData(current_id)
            if idx >= 0:
                self.user_type_combo.setCurrentIndex(idx)

    def _load_doctors(self) -> None:
        current_id = self.doctor_combo.currentData()
        self.doctor_combo.clear()
        self.doctor_combo.addItem("— Select doctor —", None)
        for doctor in self._doctors:
            label = f"{doctor.get('full_name', doctor.get('first_name', ''))} ({doctor['doctor_code']})"
            self.doctor_combo.addItem(label, doctor["id"])
        if current_id:
            idx = self.doctor_combo.findData(current_id)
            if idx >= 0:
                self.doctor_combo.setCurrentIndex(idx)

    def _load_users_table(self) -> None:
        self.table.setRowCount(len(self._users))
        for row, user in enumerate(self._users):
            self.table.setItem(row, 0, QTableWidgetItem(user.get("full_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(user.get("email", "")))
            self.table.setItem(row, 2, QTableWidgetItem(user.get("user_type_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(user.get("doctor_name") or ""))
            self.table.setItem(row, 4, QTableWidgetItem("Yes" if user.get("is_active") else "No"))
            updated = user.get("updated_at", "")
            self.table.setItem(row, 5, QTableWidgetItem(str(updated)[:19].replace("T", " ")))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, user.get("id"))

    def _load_user_combo(self) -> None:
        current_id = self.user_combo.currentData()
        self.user_combo.clear()
        self.user_combo.addItem("— Select user —", None)
        for user in self._users:
            if not user.get("is_active"):
                continue
            label = f"{user.get('full_name')} ({user.get('email')})"
            self.user_combo.addItem(label, user.get("id"))
        if current_id:
            idx = self.user_combo.findData(current_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)

    def _selected_user_type(self) -> dict | None:
        type_id = self.user_type_combo.currentData()
        return next((t for t in self._user_types if t["id"] == type_id), None)

    def _requires_doctor(self) -> bool:
        user_type = self._selected_user_type()
        return bool(user_type and user_type.get("maps_to_doctor"))

    def _on_user_type_changed(self) -> None:
        requires_doctor = self._requires_doctor()
        self.doctor_combo.setVisible(requires_doctor)
        self.doctor_row_label.setVisible(requires_doctor)
        if not requires_doctor:
            self.doctor_combo.setCurrentIndex(0)

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE

        self.user_combo.setEnabled(not is_create)
        self.full_name.setEnabled(not is_delete)
        self.email.setEnabled(not is_delete)
        self.phone.setEnabled(not is_delete)
        self.user_type_combo.setEnabled(not is_delete)
        self.doctor_combo.setEnabled(not is_delete)
        self.password.setEnabled(not is_delete)
        self.confirm_password.setEnabled(not is_delete)

        self.save_btn.setText("Delete User" if is_delete else "Save")
        if is_create:
            self._clear_form()
        elif self.user_combo.currentData():
            self._fill_form_from_user(self.user_combo.currentData())

    def _on_user_selected(self) -> None:
        user_id = self.user_combo.currentData()
        if user_id:
            self._fill_form_from_user(user_id)

    def _on_table_selection(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        user_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if self.mode_combo.currentText() != self.MODE_CREATE and user_id:
            idx = self.user_combo.findData(user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)

    def _fill_form_from_user(self, user_id: str) -> None:
        user = next((u for u in self._users if u["id"] == user_id), None)
        if not user:
            return
        self._selected_user_id = user_id
        self.full_name.setText(user.get("full_name", ""))
        self.email.setText(user.get("email", ""))
        self.phone.setText(user.get("phone") or "")
        self.password.clear()
        self.confirm_password.clear()

        type_idx = self.user_type_combo.findData(user.get("user_type_id"))
        if type_idx >= 0:
            self.user_type_combo.setCurrentIndex(type_idx)

        doctor_idx = self.doctor_combo.findData(user.get("doctor_id"))
        if doctor_idx >= 0:
            self.doctor_combo.setCurrentIndex(doctor_idx)
        else:
            self.doctor_combo.setCurrentIndex(0)

        self._on_user_type_changed()

    def _clear_form(self) -> None:
        self._selected_user_id = None
        self.full_name.clear()
        self.email.clear()
        self.phone.clear()
        self.password.clear()
        self.confirm_password.clear()
        if self.user_type_combo.count():
            self.user_type_combo.setCurrentIndex(0)
        self.doctor_combo.setCurrentIndex(0)
        self.user_combo.setCurrentIndex(0)
        self.table.clearSelection()
        self._on_user_type_changed()

    def _validate(self, *, is_create: bool) -> dict | None:
        full_name = self.full_name.text().strip()
        email = self.email.text().strip()
        user_type_id = self.user_type_combo.currentData()
        password = self.password.text()
        confirm = self.confirm_password.text()

        if not full_name or not email or not user_type_id:
            QMessageBox.warning(self, "Validation", "Full name, email and user type are required.")
            return None

        if self._requires_doctor() and not self.doctor_combo.currentData():
            QMessageBox.warning(self, "Validation", "Please select a doctor for doctor user type.")
            return None

        if is_create and not password:
            QMessageBox.warning(self, "Validation", "Password is required for new users.")
            return None

        if password and password != confirm:
            QMessageBox.warning(self, "Validation", "Password and confirm password do not match.")
            return None

        payload: dict = {
            "full_name": full_name,
            "email": email,
            "phone": self.phone.text().strip() or None,
            "user_type_id": user_type_id,
            "doctor_id": self.doctor_combo.currentData() if self._requires_doctor() else None,
        }
        if password:
            payload["password"] = password
        return payload

    def _save(self) -> None:
        mode = self.mode_combo.currentText()

        if mode == self.MODE_DELETE:
            user_id = self.user_combo.currentData() or self._selected_user_id
            if not user_id:
                QMessageBox.warning(self, "Validation", "Select a user to delete.")
                return
            user = next((u for u in self._users if u["id"] == user_id), None)
            name = user.get("full_name", "") if user else ""
            answer = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Deactivate user '{name}'?\nThey will no longer be able to log in.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_user(user_id)
                QMessageBox.information(self, "Success", "User deactivated successfully.")
                self._clear_form()
                self._reload_users_from_server()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        payload = self._validate(is_create=mode == self.MODE_CREATE)
        if not payload:
            return

        try:
            if mode == self.MODE_CREATE:
                self.api.create_user(payload)
                QMessageBox.information(self, "Success", "User created successfully.")
                self.mode_combo.setCurrentText(self.MODE_CREATE)
                self._clear_form()
            else:
                user_id = self.user_combo.currentData() or self._selected_user_id
                if not user_id:
                    QMessageBox.warning(self, "Validation", "Select a user to modify.")
                    return
                self.api.update_user(user_id, payload)
                QMessageBox.information(self, "Success", "User updated successfully.")
            self._reload_users_from_server()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
