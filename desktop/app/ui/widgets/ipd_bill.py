from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from app.ui.components.patient_registration_dialog import register_patient_dialog
from app.ui.styles import HEADER_BTN_STYLE

class IpdBillWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        info = QLabel(
            "Double-click an active admission to open it in IPD Discharge."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #475569; font-size: 12px; padding: 4px 0;")
        layout.addWidget(info)

        layout.addWidget(QLabel("Active Admissions"))
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Admission No",
                "Patient Id",
                "Patient",
                "Ward",
                "Bed",
                "Advance",
                "Status",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_discharge)
        layout.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open IPD Discharge")
        open_btn.clicked.connect(self._open_discharge)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        layout.addWidget(self.status)

    def build_header_actions(self) -> QWidget:
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("IPD Admission", lambda: self._navigate("in_patient_admission")),
                ("OPD Bill", lambda: self._navigate("opd_bill")),
                ("New Patient", self._open_patient_registration),
            ]
        )

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _open_patient_registration(self) -> None:
        patient = register_patient_dialog(self.api, self)
        if not patient:
            return
        patient_no = (patient.get("patient_no") or "").strip()
        if patient_no:
            self.status.setText(
                f"New patient saved: {patient_no} — admit the patient, then open IPD Discharge."
            )
        else:
            self.status.setText("New patient saved — admit the patient, then open IPD Discharge.")

    def refresh(self) -> None:
        try:
            rows = self.api.list_ipd_admissions(status="admitted")
        except ApiError as exc:
            self.status.setText(str(exc))
            return
        self.table.setRowCount(len(rows))
        for row_idx, item in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(item.get("admission_no", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(item.get("patient_no") or ""))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item.get("patient_name") or ""))
            self.table.setItem(row_idx, 3, QTableWidgetItem(item.get("ward_name") or ""))
            self.table.setItem(row_idx, 4, QTableWidgetItem(item.get("bed_no") or ""))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(item.get("advance_amount", ""))))
            self.table.setItem(row_idx, 6, QTableWidgetItem(item.get("status", "")))
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, item)
        self.status.setText(f"{len(rows)} active admission(s).")

    def _open_discharge(self, index=None) -> None:
        if index is not None and hasattr(index, "row"):
            row = index.row()
        else:
            row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "IPD Bill", "Select an active admission first.")
            return
        item = self.table.item(row, 0)
        if not item:
            return
        admission = item.data(Qt.ItemDataRole.UserRole) or {}
        if not admission:
            return
        from app.ui.widgets.ipd_discharge import IpdDischargeWidget

        IpdDischargeWidget.queue_admission(admission)
        if self._on_navigate:
            self._on_navigate("in_patient_discharge")
            return
        self._navigate("in_patient_discharge")
