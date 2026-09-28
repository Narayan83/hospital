from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
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


class UserTypeMasterWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        layout = QVBoxLayout(self)

        heading = QLabel("User Type Master")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)

        form_box = QGroupBox("New User Type")
        form = QFormLayout(form_box)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 999)
        self.maps_to_doctor = QCheckBox("Maps to doctor (user must select a doctor)")
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Sort Order", self.sort_order)
        form.addRow("", self.maps_to_doctor)
        layout.addWidget(form_box)

        save_btn = QPushButton("Save User Type")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Maps Doctor", "Sort"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        cache = get_session().cache
        if cache.loading or not cache.loaded:
            return
        items = cache.user_types
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem("Yes" if item.get("maps_to_doctor") else "No"))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("sort_order", 0))))

    def _save(self) -> None:
        code = self.code.text().strip().lower()
        name = self.name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validation", "Code and name are required.")
            return
        try:
            created = self.api.create_user_type({
                "code": code,
                "name": name,
                "sort_order": self.sort_order.value(),
                "maps_to_doctor": self.maps_to_doctor.isChecked(),
            })
            get_session().cache.user_types.append(created)
            self.code.clear()
            self.name.clear()
            self.sort_order.setValue(0)
            self.maps_to_doctor.setChecked(False)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
