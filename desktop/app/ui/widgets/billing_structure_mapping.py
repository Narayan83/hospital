from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_billing_structure_cache
from app.session import get_session


class BillingStructureMappingWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._mappings: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Billing Structure Mapping")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)
        hint = QLabel("Structure: Billing Type → Department → Procedure Type")
        hint.setStyleSheet("color: #475569; margin-bottom: 8px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Add Mapping")
        form = QFormLayout(form_box)
        self.billing_type = QComboBox()
        self.department = QComboBox()
        self.procedure_type = QComboBox()
        form.addRow("Billing Type *", self.billing_type)
        form.addRow("Department *", self.department)
        form.addRow("Procedure Type *", self.procedure_type)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Mapping")
        add_btn.clicked.connect(self._add_mapping)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        delete_btn = QPushButton("Remove Selected")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Billing Type", "Department", "Procedure Type", "Sort"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        layout.addWidget(QLabel("Hierarchy View"))
        self.tree_view = QTextEdit()
        self.tree_view.setReadOnly(True)
        self.tree_view.setMaximumHeight(180)
        layout.addWidget(self.tree_view)

    def refresh(self) -> None:
        cache = get_session().cache
        self._load_combos(cache)
        if cache.loaded:
            self._mappings = list(cache.billing_structure)
        else:
            try:
                self._mappings = self.api.list_billing_structure()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._load_table()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._load_tree)

    def _load_combos(self, cache) -> None:
        for combo, key in (
            (self.billing_type, "billing_types"),
            (self.department, "departments"),
            (self.procedure_type, "procedure_types"),
        ):
            combo.clear()
            combo.addItem("— Select —", None)
            for item in getattr(cache, key, []):
                combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _load_table(self) -> None:
        self.table.setRowCount(len(self._mappings))
        for row, item in enumerate(self._mappings):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("billing_type_name") or ""))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("department_name") or ""))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("procedure_type_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(str(item.get("sort_order", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _load_tree(self) -> None:
        try:
            tree = self.api.get_billing_structure_tree()
        except ApiError:
            self.tree_view.clear()
            return
        lines: list[str] = []
        for node in tree:
            bt = node.get("billing_type", {})
            lines.append(f"▶ {bt.get('name')} ({bt.get('code')})")
            for dept_node in node.get("departments", []):
                dept = dept_node.get("department", {})
                lines.append(f"   └ {dept.get('name')} ({dept.get('code')})")
                for proc in dept_node.get("procedure_types", []):
                    lines.append(f"      • {proc.get('name')} ({proc.get('code')})")
        self.tree_view.setPlainText("\n".join(lines) if lines else "No mappings yet.")

    def _add_mapping(self) -> None:
        bt_id = self.billing_type.currentData()
        dept_id = self.department.currentData()
        proc_id = self.procedure_type.currentData()
        if not bt_id or not dept_id or not proc_id:
            QMessageBox.warning(self, "Validation", "Select billing type, department, and procedure type.")
            return
        try:
            self.api.create_billing_structure({
                "billing_type_id": bt_id,
                "department_id": dept_id,
                "procedure_type_id": proc_id,
            })
            refresh_billing_structure_cache(self.api)
            self.refresh()
            QMessageBox.information(self, "Success", "Mapping added.")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _delete_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            QMessageBox.warning(self, "Validation", "Select a mapping to remove.")
            return
        mapping_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Confirm", "Remove this mapping?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_billing_structure(mapping_id)
            refresh_billing_structure_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
