from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError


class PharmacyGroupMappingWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._groups: list[dict] = []
        self._medicines: list[dict] = []
        self._mappings: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Assign Medicine To Group")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.addWidget(QLabel("Medicine Group"))
        self.group_combo = QComboBox()
        self.group_combo.currentIndexChanged.connect(self._load_mappings)
        row.addWidget(self.group_combo, stretch=1)
        row.addWidget(QLabel("Medicine"))
        self.medicine_combo = QComboBox()
        row.addWidget(self.medicine_combo, stretch=1)
        add_btn = QPushButton("Assign")
        add_btn.clicked.connect(self._assign)
        row.addWidget(add_btn)
        layout.addLayout(row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Medicine Code", "Medicine Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        layout.addWidget(remove_btn)

    def refresh(self) -> None:
        try:
            self._groups = self.api.list_pharmacy_code_masters("MG")
            self._medicines = self.api.list_pharmacy_items("MD")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        current_group = self.group_combo.currentData()
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("— Select Group —", None)
        for group in self._groups:
            self.group_combo.addItem(f"{group.get('code')} — {group.get('name')}", group.get("id"))
        if current_group:
            idx = self.group_combo.findData(current_group)
            if idx >= 0:
                self.group_combo.setCurrentIndex(idx)
        self.group_combo.blockSignals(False)

        self.medicine_combo.clear()
        self.medicine_combo.addItem("— Select Medicine —", None)
        for medicine in self._medicines:
            self.medicine_combo.addItem(f"{medicine.get('code')} — {medicine.get('name')}", medicine.get("id"))
        self._load_mappings()

    def _load_mappings(self) -> None:
        group_id = self.group_combo.currentData()
        if not group_id:
            self.table.setRowCount(0)
            self._mappings = []
            return
        try:
            self._mappings = self.api.list_pharmacy_group_mappings(group_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        medicine_map = {item.get("id"): item for item in self._medicines}
        self.table.setRowCount(len(self._mappings))
        for row, mapping in enumerate(self._mappings):
            medicine = medicine_map.get(mapping.get("item_id"), {})
            self.table.setItem(row, 0, QTableWidgetItem(medicine.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(medicine.get("name", "")))
            self.table.item(row, 0).setData(0, mapping.get("id"))

    def _assign(self) -> None:
        group_id = self.group_combo.currentData()
        item_id = self.medicine_combo.currentData()
        if not group_id or not item_id:
            QMessageBox.warning(self, "Validation", "Select a group and medicine.")
            return
        try:
            self.api.create_pharmacy_group_mapping({"group_id": group_id, "item_id": item_id})
            self._load_mappings()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _remove_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            QMessageBox.warning(self, "Validation", "Select a mapping to remove.")
            return
        mapping_id = self.table.item(items[0].row(), 0).data(0)
        if not mapping_id:
            return
        try:
            self.api.delete_pharmacy_group_mapping(mapping_id)
            self._load_mappings()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
