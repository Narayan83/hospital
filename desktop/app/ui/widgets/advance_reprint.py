from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE


class AdvanceReprintWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._patient: dict | None = None
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Advance Reprint")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Search by Patient Id (lists advances) or Voucher No. "
            "Select a row and click Preview / Reprint — print preview opens first."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        search_box = QGroupBox("Find Advance")
        search_form = QFormLayout(search_box)

        patient_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient Id")
        self.patient_id.returnPressed.connect(self._search_by_patient)
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(HEADER_BTN_STYLE)
        search_btn.clicked.connect(self._search_by_patient)
        pick_btn = QPushButton("Pick Patient")
        pick_btn.setStyleSheet(HEADER_BTN_STYLE)
        pick_btn.clicked.connect(self._pick_patient)
        patient_row.addWidget(self.patient_id, stretch=1)
        patient_row.addWidget(search_btn)
        patient_row.addWidget(pick_btn)
        search_form.addRow("Patient Id", patient_row)

        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        search_form.addRow("Patient Name", self.patient_name)

        voucher_row = QHBoxLayout()
        self.voucher_no = QLineEdit()
        self.voucher_no.setPlaceholderText("ADV…")
        self.voucher_no.returnPressed.connect(self._search_by_voucher)
        load_btn = QPushButton("Load Voucher")
        load_btn.setStyleSheet(HEADER_BTN_STYLE)
        load_btn.clicked.connect(self._search_by_voucher)
        voucher_row.addWidget(self.voucher_no, stretch=1)
        voucher_row.addWidget(load_btn)
        search_form.addRow("Voucher No", voucher_row)

        layout.addWidget(search_box)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Voucher", "Date", "Amount", "Payment Mode", "Narration", "Id"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._reprint_selected)
        layout.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        reprint_btn = QPushButton("Reprint")
        reprint_btn.setStyleSheet(HEADER_BTN_STYLE)
        reprint_btn.clicked.connect(self._reprint_selected)
        preview_btn = QPushButton("Preview")
        preview_btn.setStyleSheet(HEADER_BTN_STYLE)
        preview_btn.clicked.connect(self._preview_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(HEADER_BTN_STYLE)
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(reprint_btn)
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        layout.addWidget(self.status)

    def refresh(self) -> None:
        pass

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, self)
        if patient:
            self._apply_patient(patient)
            self._load_for_patient()

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no") or "")
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))

    def _search_by_patient(self) -> None:
        patient_no = self.patient_id.text().strip()
        if not patient_no:
            QMessageBox.information(self, "Search", "Enter Patient Id.")
            return
        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                QMessageBox.warning(self, "Patient", f"No patient found: {patient_no}")
                return
            self._apply_patient(items[0])
            self._load_for_patient()
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))

    def _load_for_patient(self) -> None:
        if not self._patient:
            return
        try:
            self._rows = self.api.list_advances(patient_id=self._patient.get("id")) or []
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))
            return
        self._fill_table()
        self.status.setText(f"{len(self._rows)} advance receipt(s) found.")

    def _search_by_voucher(self) -> None:
        voucher_no = self.voucher_no.text().strip()
        if not voucher_no:
            QMessageBox.information(self, "Search", "Enter Voucher No.")
            return
        try:
            advance = self.api.get_advance_by_no(voucher_no)
        except ApiError as exc:
            QMessageBox.warning(self, "Search", str(exc))
            return
        self._rows = [advance]
        self._fill_table()
        self.table.selectRow(0)
        patient_id = advance.get("patient_id")
        if patient_id:
            try:
                patient = self.api.get_patient(patient_id)
                self._apply_patient(patient)
            except ApiError:
                self.patient_id.setText(advance.get("patient_no") or "")
                self.patient_name.setText(advance.get("patient_name") or "")
        self.status.setText(f"Loaded {advance.get('voucher_no', '')}")
        self._reprint_selected()

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for row, item in enumerate(self._rows):
            mode = " — ".join(
                p for p in (item.get("payment_mode_code"), item.get("payment_mode_name")) if p
            )
            values = [
                item.get("voucher_no") or "",
                str(item.get("voucher_date") or ""),
                f"{float(item.get('amount') or 0):,.2f}",
                mode,
                item.get("narration") or "",
                item.get("id") or "",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 2:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, cell)

    def _selected(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _reprint_selected(self) -> None:
        advance = self._selected()
        if not advance or not advance.get("id"):
            QMessageBox.information(self, "Reprint", "Select an advance receipt first.")
            return
        preview_report(
            self.api,
            f"/reports/advance/{advance['id']}",
            parent=self,
            report_code="ADVANCE_RECEIPT",
            title="Advance Receipt Preview",
            default_copies=1,
        )
        self.status.setText(f"Preview opened for {advance.get('voucher_no', '')}")

    def _preview_selected(self) -> None:
        advance = self._selected()
        if not advance or not advance.get("id"):
            QMessageBox.information(self, "Preview", "Select an advance receipt first.")
            return
        preview_report(
            self.api,
            f"/reports/advance/{advance['id']}",
            parent=self,
            report_code="ADVANCE_RECEIPT",
            title="Advance Receipt Preview",
            default_copies=1,
        )

    def _clear(self) -> None:
        self._patient = None
        self._rows = []
        self.patient_id.clear()
        self.patient_name.clear()
        self.voucher_no.clear()
        self.table.setRowCount(0)
        self.status.clear()
