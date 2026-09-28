from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.billing_catalog import (
    filter_catalog,
    load_pathology_catalog_from_api,
)
from app.session import get_session
from app.ui.bill_hold import (
    BillHoldMixin,
    date_iso,
    hold_label_from_patient,
    set_combo_value,
    set_date_iso,
)
from app.ui.components.patient_registration_dialog import register_patient_dialog
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.styles import (
    BTN_DANGER,
    BTN_PRIMARY,
    BTN_SECONDARY,
    TEXT_MUTED,
)
from app.ui.widgets.opd_bill import (
    CATALOG_CATEGORY_WIDTH,
    CATALOG_COL_RATE,
    CATALOG_RATE_WIDTH,
    CATALOG_SERVICE_WIDTH,
    FILTER_GROUP_STYLE,
    HEADER_BTN_STYLE,
    LEFT_PANE_WIDTH,
    SERVICE_TABLE_ROW_HEIGHT,
    SERVICE_TABLE_STYLE,
)

PATHOLOGY_CODE_WIDTH = 56


def _style_button(btn: QPushButton, style: str) -> QPushButton:
    btn.setStyleSheet(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn

PATHOLOGY_DEPARTMENT_CODE = "PATH"

# Bill-lines table column indices.
COL_CODE = 0
COL_GROUP = 1
COL_SUB = 2
COL_QTY = 3
COL_RATE = 4
COL_AMOUNT = 5
COL_RESULT = 6
COL_BOLD = 7
COL_REF = 8

BOLD_BTN_STYLE = (
    "QPushButton { border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc;"
    " color: #64748b; font-weight: bold; padding: 0; }"
    "QPushButton:checked { background: #b91c1c; color: white; border-color: #b91c1c; }"
)


class PathologyBillWidget(BillHoldMixin, QWidget):
    def __init__(
        self,
        api: ApiClient,
        on_navigate: Callable[[str], None] | None = None,
        *,
        modification_mode: bool = False,
    ):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._modification_mode = modification_mode
        self._patient: dict | None = None
        self._catalog: list[dict] = []
        self._catalog_all: list[dict] = []
        self._catalog_base: list[dict] | None = None
        self._catalog_checked_ids: set[str] = set()
        self._catalog_rate_overrides: dict[str, str] = {}
        self._catalog_table_updating = False
        self._bill_lines: list[dict] = []
        self._saved_bill_id: str | None = None
        self._path_dept_id: str | None = None
        self._splitter_sized = False
        self._lines_table_updating = False
        self._general_note = ""
        self._notes_by_code: dict[str, str] = {}
        self._inserted_note_texts: set[str] = set()
        self._build_ui()

    @staticmethod
    def _configure_service_table(table: QTableWidget) -> None:
        table.setStyleSheet(SERVICE_TABLE_STYLE)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        v_header = table.verticalHeader()
        v_header.setDefaultSectionSize(SERVICE_TABLE_ROW_HEIGHT)
        v_header.setMinimumSectionSize(SERVICE_TABLE_ROW_HEIGHT)
        v_header.setMaximumSectionSize(SERVICE_TABLE_ROW_HEIGHT)
        v_header.setFixedWidth(26)

    @staticmethod
    def _compact_table_item(text: str, *, editable: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _build_ui(self) -> None:
        from app.ui.responsive_layout import get_density, paint_page_surface

        d = get_density()
        paint_page_surface(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(d.section_spacing)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(5)
        self._splitter.setChildrenCollapsible(False)
        outer.addWidget(self._splitter, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(LEFT_PANE_WIDTH)
        left_host = QWidget()
        left_host.setMinimumWidth(LEFT_PANE_WIDTH - 24)
        left_scroll.setWidget(left_host)
        left = QVBoxLayout(left_host)

        patient_box = QGroupBox("Patient")
        patient_form = QFormLayout(patient_box)
        patient_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        # Keep ExpandingFieldsGrow — apply_responsive_layout would otherwise
        # force FieldsStayAtSizeHint and leave Patient Name at a short size hint.
        patient_form.setProperty("hmsResponsive", True)
        pid_row = QHBoxLayout()
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient No")
        self.patient_id.editingFinished.connect(self._on_patient_id_lookup)
        find_btn = QPushButton("Find Patient")
        _style_button(find_btn, BTN_SECONDARY)
        find_btn.clicked.connect(self._find_patient)
        pid_row.addWidget(self.patient_id, stretch=1)
        pid_row.addWidget(find_btn)
        patient_form.addRow("Patient Id", pid_row)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self.patient_name.setProperty("hmsAllowWide", True)
        self.patient_name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.mobile = QLineEdit()
        self.mobile.setReadOnly(True)
        self.mobile.setProperty("hmsAllowWide", True)
        self.mobile.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        patient_form.addRow("Patient Name", self.patient_name)
        patient_form.addRow("Mobile", self.mobile)
        left.addWidget(patient_box)

        bill_box = QGroupBox("Sample & Bill")
        bill_form = QFormLayout(bill_box)
        bill_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("Assigned on Save")
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        self.sample_no = QLineEdit()
        self.sample_no.setPlaceholderText("Sample / Lab ID (optional)")
        self.sample_date = QDateEdit()
        self.sample_date.setCalendarPopup(True)
        self.sample_date.setDisplayFormat("dd/MM/yyyy")
        self.sample_date.setDate(QDate.currentDate())
        self.order_status = QLineEdit()
        self.order_status.setReadOnly(True)
        self.order_status.setPlaceholderText("Created on Save")
        self.cash_credit = QComboBox()
        self.cash_credit.addItems(["1.CASH", "2.CREDIT"])
        self.payment_mode = QComboBox()
        self.doctor = QComboBox()
        self.department = QComboBox()
        for combo in (self.cash_credit, self.payment_mode, self.doctor, self.department):
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.setMinimumWidth(160)
        self.referring_doctor = QComboBox()
        self.referring_doctor.setEditable(True)
        self.referring_doctor.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.referring_doctor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.referring_doctor.setMinimumWidth(160)
        self.referring_doctor.lineEdit().setPlaceholderText("Select or type reference doctor")
        self.scheme = QLineEdit()
        self.scheme.setPlaceholderText("No Scheme")
        bill_form.addRow("Bill No", self.bill_no)
        bill_form.addRow("Bill Date", self.bill_date)
        bill_form.addRow("Sample No", self.sample_no)
        bill_form.addRow("Sample Date", self.sample_date)
        bill_form.addRow("Order Status", self.order_status)
        bill_form.addRow("Cash/Credit", self.cash_credit)
        bill_form.addRow("Payment Mode", self.payment_mode)
        bill_form.addRow("Department", self.department)
        bill_form.addRow("Scheme", self.scheme)
        left.addWidget(bill_box)

        charges_box = QGroupBox("Charges")
        charges_form = QFormLayout(charges_box)
        self.admin_charges = QLineEdit("0")
        self.scheme_discount = QLineEdit("0")
        self.adjust_advance = QLineEdit("0")
        charges_form.addRow("Admin Charges", self.admin_charges)
        charges_form.addRow("Scheme Discount", self.scheme_discount)
        charges_form.addRow("Adjust Advance", self.adjust_advance)
        left.addWidget(charges_box)

        net_card = QFrame()
        net_card.setStyleSheet(
            "QFrame { background: #ecfdf5; border: 2px solid #6ee7b7; border-radius: 10px; }"
        )
        net_layout = QHBoxLayout(net_card)
        net_layout.setContentsMargins(14, 10, 14, 10)
        net_caption = QLabel("NET AMOUNT")
        net_caption.setStyleSheet(
            "background: transparent; border: none; color: #047857; font-size: 12px;"
            " font-weight: 700; letter-spacing: 0.5px;"
        )
        self.net_amount = QLabel("0.00")
        self.net_amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.net_amount.setStyleSheet(
            "background: transparent; border: none; font-size: 26px; font-weight: 800;"
            " color: #065f46;"
        )
        net_layout.addWidget(net_caption)
        net_layout.addStretch()
        net_layout.addWidget(self.net_amount)
        left.addWidget(net_card)
        left.addStretch()
        self._splitter.addWidget(left_scroll)

        right_host = QWidget()
        from app.ui.responsive_layout import paint_page_surface as _paint
        from app.ui.styles import BG as _BG

        _paint(right_host, color=_BG)
        right = QVBoxLayout(right_host)
        right_host.setMinimumWidth(480)
        self._splitter.addWidget(right_host)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([LEFT_PANE_WIDTH, 900])

        doctor_box = QGroupBox("Pathologist")
        doctor_box.setStyleSheet(FILTER_GROUP_STYLE)
        doctor_form = QFormLayout(doctor_box)
        doctor_form.setContentsMargins(8, 6, 8, 6)
        doctor_form.setHorizontalSpacing(10)
        doctor_form.setVerticalSpacing(6)
        doctor_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        doctor_form.setProperty("hmsResponsive", True)
        self.doctor.setProperty("hmsAllowWide", True)
        self.referring_doctor.setProperty("hmsAllowWide", True)
        doctor_form.addRow("Pathologist", self.doctor)
        doctor_form.addRow("Reference Doctor", self.referring_doctor)
        doctor_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right.addWidget(doctor_box)

        self._catalog_search_timer = QTimer(self)
        self._catalog_search_timer.setSingleShot(True)
        self._catalog_search_timer.setInterval(200)
        self._catalog_search_timer.timeout.connect(self._apply_catalog_search)

        self.catalog_table = QTableWidget(0, 5)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Add", "Code", "Service", "Category", "Rate"]
        )
        self.catalog_table.setProperty(
            "hmsColumnKinds", ["checkbox", "code", "text", "short", "number"]
        )
        self.catalog_table.setProperty("hmsNoStretch", True)
        self._configure_service_table(self.catalog_table)
        catalog_header = self.catalog_table.horizontalHeader()
        catalog_header.setStretchLastSection(False)
        catalog_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.catalog_table.setColumnWidth(0, 34)
        catalog_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(1, PATHOLOGY_CODE_WIDTH)
        catalog_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(2, CATALOG_SERVICE_WIDTH)
        catalog_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(3, CATALOG_CATEGORY_WIDTH)
        catalog_header.setSectionResizeMode(CATALOG_COL_RATE, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(CATALOG_COL_RATE, CATALOG_RATE_WIDTH)
        self.catalog_table.itemChanged.connect(self._on_catalog_item_changed)

        self.lines_table = QTableWidget(0, 9)
        self.lines_table.setHorizontalHeaderLabels(
            [
                "Code",
                "Test / Bundle",
                "Sub-Test",
                "Qty",
                "Rate",
                "Amount",
                "Result",
                "B",
                "Reference Range",
            ]
        )
        self.lines_table.setProperty(
            "hmsColumnKinds",
            ["code", "text", "text", "number", "number", "number", "text", "code", "text"],
        )
        self.lines_table.setProperty("hmsNoStretch", True)
        self._configure_service_table(self.lines_table)
        lines_header = self.lines_table.horizontalHeader()
        lines_header.setStretchLastSection(False)
        lines_header.setSectionResizeMode(COL_CODE, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_GROUP, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_SUB, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_QTY, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_RATE, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_AMOUNT, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(COL_RESULT, QHeaderView.ResizeMode.Interactive)
        self.lines_table.setColumnWidth(COL_RESULT, 90)
        lines_header.setSectionResizeMode(COL_BOLD, QHeaderView.ResizeMode.Fixed)
        self.lines_table.setColumnWidth(COL_BOLD, 28)
        lines_header.setSectionResizeMode(COL_REF, QHeaderView.ResizeMode.Interactive)
        self.lines_table.setColumnWidth(COL_CODE, PATHOLOGY_CODE_WIDTH)
        self.lines_table.setColumnWidth(COL_GROUP, CATALOG_SERVICE_WIDTH)
        self.lines_table.setColumnWidth(COL_SUB, 180)
        self.lines_table.setColumnWidth(COL_QTY, 50)
        self.lines_table.setColumnWidth(COL_RATE, 80)
        self.lines_table.setColumnWidth(COL_AMOUNT, 90)
        self.lines_table.setColumnWidth(COL_REF, 180)
        self.lines_table.itemChanged.connect(self._on_line_item_changed)

        catalog_header_row = QHBoxLayout()
        catalog_header_row.addWidget(QLabel("Code"))
        self.service_code_entry = QLineEdit()
        self.service_code_entry.setPlaceholderText("e.g. 60")
        self.service_code_entry.setMaxLength(6)
        self.service_code_entry.setFixedWidth(60)
        self.service_code_entry.returnPressed.connect(self._add_by_code)
        add_code_btn = QPushButton("Add")
        _style_button(add_code_btn, BTN_PRIMARY)
        add_code_btn.clicked.connect(self._add_by_code)
        catalog_header_row.addWidget(self.service_code_entry)
        catalog_header_row.addWidget(add_code_btn)
        catalog_header_row.addSpacing(12)
        catalog_header_row.addWidget(QLabel("Search"))
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Search test name or code...")
        self.catalog_search.setClearButtonEnabled(True)
        self.catalog_search.textChanged.connect(self._debounce_catalog_search)
        show_btn = QPushButton("Show All")
        _style_button(show_btn, BTN_SECONDARY)
        show_btn.clicked.connect(self._show_all_services)
        catalog_header_row.addWidget(self.catalog_search, stretch=1)
        catalog_header_row.addWidget(show_btn)
        right.addLayout(catalog_header_row)
        self.catalog_table.setMinimumHeight(72)
        self.catalog_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right.addWidget(self.catalog_table, stretch=1)

        lines_header_row = QHBoxLayout()
        lines_lbl = QLabel("Bill Lines")
        lines_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        add_btn = QPushButton("Add Selected")
        _style_button(add_btn, BTN_PRIMARY)
        add_btn.clicked.connect(self._add_selected_services)
        remove_btn = QPushButton("Remove Line")
        _style_button(remove_btn, BTN_DANGER)
        remove_btn.clicked.connect(self._remove_selected_lines)
        lines_header_row.addWidget(lines_lbl)
        lines_header_row.addStretch()
        lines_header_row.addWidget(add_btn)
        lines_header_row.addWidget(remove_btn)
        right.addLayout(lines_header_row)
        self.lines_table.setMinimumHeight(72)
        self.lines_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right.addWidget(self.lines_table, stretch=1)

        notes_header = QLabel("Notes")
        notes_header.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        right.addWidget(notes_header)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "General note loads automatically; service notes are added when you pick tests."
            " Edit freely before printing."
        )
        self.notes_edit.setMinimumHeight(40)
        self.notes_edit.setMaximumHeight(max(56, d.field_min_height * 2))
        self.notes_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        right.addWidget(self.notes_edit)

        # Action bar lives in the page footer (not inside the right pane) so Save /
        # Print stay visible on short screens while tables shrink above.
        btn_host = QWidget()
        btn_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_row = QHBoxLayout(btn_host)
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(8)
        save_label = "Update Bill" if self._modification_mode else "Save Bill"
        self.save_btn = QPushButton(save_label)
        _style_button(self.save_btn, BTN_PRIMARY)
        self.save_btn.clicked.connect(self._save_bill)
        self.print_bill_btn = QPushButton("Print Bill")
        _style_button(self.print_bill_btn, BTN_SECONDARY)
        self.print_bill_btn.clicked.connect(self._print_bill)
        self.print_report_btn = QPushButton("Print Report")
        _style_button(self.print_report_btn, BTN_SECONDARY)
        self.print_report_btn.clicked.connect(self._print_report)
        self.preview_report_btn = QPushButton("Preview Report")
        _style_button(self.preview_report_btn, BTN_SECONDARY)
        self.preview_report_btn.clicked.connect(self._preview_report)
        clear_btn = QPushButton("Clear")
        _style_button(clear_btn, BTN_SECONDARY)
        clear_btn.clicked.connect(self._clear_bill)
        if self._modification_mode:
            clear_btn.hide()
        for btn in (
            self.save_btn,
            self.print_bill_btn,
            self.preview_report_btn,
            self.print_report_btn,
        ):
            btn_row.addWidget(btn)
        self._setup_bill_hold_buttons(
            btn_row,
            style_button=lambda btn: _style_button(btn, BTN_SECONDARY),
        )
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        outer.addWidget(btn_host)

        self.status = QLabel("")
        self.status.setStyleSheet(
            "QLabel { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;"
            f" color: {TEXT_MUTED}; padding: 4px 10px; font-size: {d.font_size}px; }}"
        )
        self.status.setMinimumHeight(max(26, d.field_min_height - 4))
        outer.addWidget(self.status)

        if self._modification_mode:
            self.patient_id.setReadOnly(True)
            self.bill_date.setEnabled(False)
            self.bill_no.setReadOnly(True)

    def load_bill_for_modification(self, bill: dict) -> None:
        self._load_saved_bill(bill)
        self._set_status(f"Editing bill {bill.get('bill_no', '')} — add/remove tests and update charges.")

    def build_header_actions(self) -> QWidget | None:
        if self._modification_mode:
            return None
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("New Patient", self._open_patient_registration),
                ("Create Service", lambda: self._navigate("service_creation_pathology")),
                ("Test Profiles", lambda: self._navigate("parameter_mapping")),
                ("Work List", self._open_work_list_modal),
                ("Reprint Bill", self._reprint_bill),
                ("Modify Bill", lambda: self._navigate("pathology_bill_modification")),
            ]
        )

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _open_patient_registration(self) -> None:
        patient = register_patient_dialog(self.api, self)
        if patient:
            self._apply_patient(patient)

    def _open_work_list_modal(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

        from app.ui.navigation import make_shortcut_navigator
        from app.ui.widgets.pathology_work_list import PathologyWorkListWidget

        dialog = QDialog(self)
        dialog.setWindowTitle("Pathology Work List")
        dialog.resize(1100, 720)
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        widget = PathologyWorkListWidget(self.api, on_navigate=make_shortcut_navigator(self))
        layout.addWidget(widget)
        widget.refresh()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _report_endpoint(self, *, report: bool = False) -> str | None:
        if self._saved_bill_id:
            kind = "pathology-report" if report else "pathology-bill"
            return f"/reports/{kind}/{self._saved_bill_id}"
        bill_no = self.bill_no.text().strip()
        if bill_no:
            kind = "pathology-report" if report else "pathology-bill"
            return f"/reports/{kind}/by-no/{bill_no}"
        return None

    def _preview_bill(self) -> None:
        endpoint = self._report_endpoint(report=False)
        if endpoint:
            preview_report(self.api, endpoint, parent=self, report_code="PATHOLOGY_BILL")

    def _print_bill(self) -> None:
        endpoint = self._report_endpoint(report=False)
        if not endpoint:
            QMessageBox.information(self, "Print", "Save or load a bill first.")
            return
        print_report(self.api, endpoint, parent=self, report_code="PATHOLOGY_BILL")

    def _preview_report(self) -> None:
        endpoint = self._report_endpoint(report=True)
        if not endpoint:
            QMessageBox.information(self, "Preview Report", "Save or load a bill first.")
            return
        preview_report(self.api, endpoint, parent=self, title="Pathology Report Preview", report_code="PATHOLOGY_REPORT")

    def _print_report(self) -> None:
        endpoint = self._report_endpoint(report=True)
        if not endpoint:
            QMessageBox.information(self, "Print Report", "Save or load a bill first.")
            return
        print_report(self.api, endpoint, parent=self, report_code="PATHOLOGY_REPORT")

    def _reprint_bill(self) -> None:
        from app.ui.widgets.pathology_bill_reprint import PathologyBillReprintWidget

        patient_no = self.patient_id.text().strip()
        PathologyBillReprintWidget.request_open(patient_no)
        self._navigate("pathology_bill_reprint")

    def _load_saved_bill(self, bill: dict) -> None:
        self._saved_bill_id = bill.get("id")
        self._patient = {"id": bill.get("patient_id"), "patient_no": bill.get("patient_no")}
        self.patient_id.setText(bill.get("patient_no") or "")
        self.patient_name.setText(bill.get("patient_name") or "")
        self.mobile.clear()
        self.bill_no.setText(bill.get("bill_no") or "")
        if bill.get("bill_date"):
            parts = str(bill["bill_date"]).split("-")
            if len(parts) == 3:
                self.bill_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        if bill.get("sample_date"):
            parts = str(bill["sample_date"]).split("-")
            if len(parts) == 3:
                self.sample_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self.sample_no.setText(bill.get("sample_no") or "")
        remarks = bill.get("remarks") or ""
        self.notes_edit.setPlainText(remarks)
        self._inserted_note_texts = {remarks} if remarks else set()
        self.order_status.setText((bill.get("order_status") or "").replace("_", " ").title())
        self.cash_credit.setCurrentIndex(0 if bill.get("is_cash", True) else 1)
        if bill.get("payment_mode_id"):
            idx = self.payment_mode.findData(bill["payment_mode_id"])
            if idx >= 0:
                self.payment_mode.setCurrentIndex(idx)
        if bill.get("doctor_id"):
            idx = self.doctor.findData(bill["doctor_id"])
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)
        if bill.get("department_id"):
            idx = self.department.findData(bill["department_id"])
            if idx >= 0:
                self.department.setCurrentIndex(idx)
        self._set_referring_doctor(bill.get("referring_doctor"))
        self.scheme.setText(bill.get("scheme") or "")
        self.admin_charges.setText(str(bill.get("admin_charges", "0")))
        self.scheme_discount.setText(str(bill.get("scheme_discount", "0")))
        self.adjust_advance.setText(str(bill.get("adjust_advance", "0")))
        saved_lines = sorted(
            bill.get("lines") or [],
            key=lambda line: int(line.get("sort_order") or 0),
        )
        self._bill_lines = [
            {
                "service_id": line.get("service_id"),
                "service_code": line.get("service_code"),
                "service_name": line.get("service_name"),
                "panel_service_id": line.get("panel_service_id"),
                "panel_name": line.get("panel_name"),
                "is_panel_parent": line.get("is_panel_parent", False),
                "reference_range_text": line.get("reference_range_text"),
                "result_value": line.get("result_value") or "",
                "is_abnormal": bool(line.get("is_abnormal", False)),
                "abnormal_manual": bool(line.get("is_abnormal", False)),
                "min_value": None,
                "max_value": None,
                "category_name": line.get("category_name"),
                "sub_category_name": line.get("sub_category_name"),
                "rate": float(line.get("rate", 0)),
                "quantity": int(line.get("quantity", 1)),
                "amount": float(line.get("amount", 0)),
                "line_source": line.get("line_source", "manual"),
                "package_id": line.get("package_id"),
                "sort_order": int(line.get("sort_order") or 0),
            }
            for line in saved_lines
        ]
        self._refresh_lines_table()
        self._calculate()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._splitter_sized:
            QTimer.singleShot(0, self._apply_splitter_sizes)

    def _apply_splitter_sizes(self) -> None:
        if self._splitter_sized:
            return
        total = self._splitter.width()
        if total <= 0:
            QTimer.singleShot(50, self._apply_splitter_sizes)
            return
        left_width = max(LEFT_PANE_WIDTH, min(LEFT_PANE_WIDTH + 40, int(total * 0.36)))
        self._splitter.setSizes([left_width, max(total - left_width, 480)])
        self._splitter_sized = True

    def refresh(self) -> None:
        cache = get_session().cache
        self._apply_splitter_sizes()
        self._load_combo(self.payment_mode, cache.payment_modes, "— Select —")
        self._load_combo(self.department, cache.departments, "— Select —")

        self._path_dept_id = None
        for dept in cache.departments if cache.loaded else []:
            if dept.get("code") == PATHOLOGY_DEPARTMENT_CODE:
                self._path_dept_id = dept.get("id")
                idx = self.department.findData(self._path_dept_id)
                if idx >= 0:
                    self.department.setCurrentIndex(idx)
                break

        self.doctor.clear()
        self.doctor.addItem("— Select Pathologist —", None)
        for doc in cache.doctors if cache.loaded else []:
            if doc.get("is_pathology_doctor"):
                label = f"{doc.get('doctor_code')} — {doc.get('full_name', '')}"
                self.doctor.addItem(label, doc.get("id"))

        self._load_reference_doctors()

        cash_modes = [m for m in (cache.payment_modes if cache.loaded else []) if m.get("is_cash")]
        if cash_modes:
            idx = self.payment_mode.findData(cash_modes[0].get("id"))
            if idx >= 0:
                self.payment_mode.setCurrentIndex(idx)

        # Lab tests live in PatientServiceMaster but are excluded from the shared
        # app_data cache (that cache feeds OPD/IPD screens and deliberately drops
        # LAB category rows). Fetch the pathology catalog once here instead and
        # filter/search it locally so typing in the search box stays instant.
        try:
            self._catalog_base = load_pathology_catalog_from_api(self.api)
        except ApiError:
            self._catalog_base = None
        self._on_catalog_filter_changed()
        self._load_service_notes()

    def _load_service_notes(self) -> None:
        self._general_note = ""
        self._notes_by_code = {}
        try:
            notes = self.api.list_service_notes()
        except ApiError:
            notes = []
        for note in notes:
            code = (note.get("service_code") or "").strip().upper()
            text = note.get("note_text") or ""
            if code:
                self._notes_by_code[code] = text
            else:
                self._general_note = text
        # Seed the general note for a fresh bill (don't clobber a loaded/edited one).
        if not self._saved_bill_id and not self.notes_edit.toPlainText().strip():
            self._inserted_note_texts = set()
            self._append_note(self._general_note)
            for line in self._bill_lines:
                self._apply_service_note(line.get("service_code"))

    def _append_note(self, text: str) -> None:
        text = (text or "").strip()
        if not text or text in self._inserted_note_texts:
            return
        current = self.notes_edit.toPlainText().strip()
        combined = f"{current}\n{text}".strip() if current else text
        self.notes_edit.setPlainText(combined)
        self._inserted_note_texts.add(text)

    def _apply_service_note(self, service_code: str | None) -> None:
        code = (service_code or "").strip().upper()
        if not code:
            return
        self._append_note(self._notes_by_code.get(code, ""))

    @staticmethod
    def _load_combo(combo: QComboBox, items: list[dict], placeholder: str) -> None:
        combo.clear()
        combo.addItem(placeholder, None)
        for item in items:
            combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _load_reference_doctors(self) -> None:
        """Fill Reference Doctor combo from doctors marked is_reference_doctor=Y."""
        cache = get_session().cache
        current = self.referring_doctor.currentText().strip()
        self.referring_doctor.blockSignals(True)
        self.referring_doctor.clear()
        self.referring_doctor.addItem("", None)
        for doc in cache.doctors if cache.loaded else []:
            if not doc.get("is_reference_doctor"):
                continue
            name = (doc.get("full_name") or "").strip()
            if not name:
                continue
            label = f"{doc.get('doctor_code')} — {name}"
            self.referring_doctor.addItem(label, doc.get("id"))
        self.referring_doctor.blockSignals(False)
        if current:
            self._set_referring_doctor(current)

    def _set_referring_doctor(self, name: str | None) -> None:
        """Select matching reference doctor or keep free-typed outsider name."""
        text = (name or "").strip()
        if not text:
            self.referring_doctor.setCurrentIndex(0)
            self.referring_doctor.setEditText("")
            return
        cache = get_session().cache
        name_by_id = {
            doc.get("id"): (doc.get("full_name") or "").strip()
            for doc in (cache.doctors if cache.loaded else [])
            if doc.get("is_reference_doctor")
        }
        for idx in range(self.referring_doctor.count()):
            data = self.referring_doctor.itemData(idx)
            if data is None:
                continue
            item_text = self.referring_doctor.itemText(idx)
            if item_text == text or item_text.endswith(f" — {text}"):
                self.referring_doctor.setCurrentIndex(idx)
                return
            if name_by_id.get(data) == text:
                self.referring_doctor.setCurrentIndex(idx)
                return
        self.referring_doctor.setCurrentIndex(0)
        self.referring_doctor.setEditText(text)

    def _referring_doctor_value(self) -> str | None:
        """Resolve selected master doctor name, or free-typed outsider name."""
        text = self.referring_doctor.currentText().strip()
        if not text:
            return None
        data = self.referring_doctor.currentData()
        if data is not None:
            cache = get_session().cache
            for doc in cache.doctors if cache.loaded else []:
                if doc.get("id") != data:
                    continue
                name = (doc.get("full_name") or "").strip()
                label = f"{doc.get('doctor_code')} — {name}"
                # Only use master name when the edit text still matches that doctor.
                if text in (name, label) or (name and text.endswith(f" — {name}")):
                    return name or None
                break
        if " — " in text:
            text = text.split(" — ", 1)[-1].strip()
        return text or None

    def _on_catalog_filter_changed(self) -> None:
        if self._catalog_base is not None:
            self._apply_catalog_search()
        else:
            self._load_catalog()

    def _debounce_catalog_search(self) -> None:
        self._collect_catalog_checked_ids()
        self._catalog_search_timer.start()

    def _collect_catalog_checked_ids(self) -> None:
        checked = set(self._catalog_checked_ids)
        for row in range(self.catalog_table.rowCount()):
            widget = self.catalog_table.cellWidget(row, 0)
            if not widget:
                continue
            chk = widget.findChild(QCheckBox)
            item = self.catalog_table.item(row, 1)
            if not chk or not item:
                continue
            service = item.data(Qt.ItemDataRole.UserRole)
            service_id = service.get("id") if service else None
            if not service_id:
                continue
            sid = str(service_id)
            if chk.isChecked():
                checked.add(sid)
            else:
                checked.discard(sid)
        self._catalog_checked_ids = checked

    def _show_all_services(self) -> None:
        self.catalog_search.clear()
        self._on_catalog_filter_changed()

    def _load_catalog(self) -> None:
        try:
            self._catalog_all = load_pathology_catalog_from_api(self.api)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._apply_catalog_search()

    def _apply_catalog_search(self) -> None:
        self._collect_catalog_rate_edits()
        search = self.catalog_search.text().strip()
        if self._catalog_base is not None:
            self._catalog = filter_catalog(
                self._catalog_base,
                search=search or None,
            )
        else:
            query = search.lower()
            if query:
                self._catalog = [
                    item
                    for item in self._catalog_all
                    if query in (item.get("name") or "").lower()
                    or query in (item.get("code") or "").lower()
                ]
            else:
                self._catalog = list(self._catalog_all)
            self._catalog = sorted(self._catalog, key=lambda x: (x.get("name") or "").casefold())
        self._populate_catalog_table(self._catalog)

    def _populate_catalog_table(self, items: list[dict]) -> None:
        checked_ids = self._catalog_checked_ids
        rate_overrides = self._catalog_rate_overrides
        self._catalog_table_updating = True
        try:
            self.catalog_table.setRowCount(len(items))
            for row, item in enumerate(items):
                chk = QCheckBox()
                service_id = item.get("id")
                sid = str(service_id) if service_id else ""
                if service_id:
                    chk.blockSignals(True)
                    chk.setChecked(sid in checked_ids)
                    chk.blockSignals(False)
                    chk.stateChanged.connect(
                        lambda state, sid=sid: self._on_catalog_checkbox_changed(sid, state)
                    )
                chk_widget = QWidget()
                chk_layout = QHBoxLayout(chk_widget)
                chk_layout.addWidget(chk)
                chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk_layout.setContentsMargins(0, 0, 0, 0)
                self.catalog_table.setCellWidget(row, 0, chk_widget)
                self.catalog_table.setItem(row, 1, self._compact_table_item(item.get("code", "")))
                self.catalog_table.setItem(row, 2, self._compact_table_item(item.get("name", "")))
                self.catalog_table.setItem(
                    row, 3, self._compact_table_item(item.get("category_name") or "")
                )
                rate_text = rate_overrides.get(sid, str(item.get("rate", "")))
                self.catalog_table.setItem(
                    row, CATALOG_COL_RATE, self._compact_table_item(rate_text, editable=True)
                )
                self.catalog_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, item)
        finally:
            self._catalog_table_updating = False

    def _collect_catalog_rate_edits(self) -> None:
        for row in range(self.catalog_table.rowCount()):
            id_item = self.catalog_table.item(row, 1)
            rate_item = self.catalog_table.item(row, CATALOG_COL_RATE)
            if not id_item or not rate_item:
                continue
            service = id_item.data(Qt.ItemDataRole.UserRole)
            if not service or not service.get("id"):
                continue
            sid = str(service.get("id"))
            text = rate_item.text().strip()
            if text:
                self._catalog_rate_overrides[sid] = text

    def _on_catalog_item_changed(self, item: QTableWidgetItem) -> None:
        if self._catalog_table_updating or item.column() != CATALOG_COL_RATE:
            return
        id_item = self.catalog_table.item(item.row(), 1)
        if not id_item:
            return
        service = id_item.data(Qt.ItemDataRole.UserRole)
        if not service or not service.get("id"):
            return
        sid = str(service.get("id"))
        text = item.text().strip()
        if text:
            self._catalog_rate_overrides[sid] = text

    def _service_with_catalog_rate(self, service: dict) -> dict:
        sid = str(service.get("id", ""))
        override = self._catalog_rate_overrides.get(sid)
        if override is None:
            return service
        merged = dict(service)
        merged["rate"] = override
        return merged

    @staticmethod
    def _is_checkbox_checked(state: object) -> bool:
        try:
            return Qt.CheckState(state) == Qt.CheckState.Checked
        except (TypeError, ValueError):
            return state == Qt.CheckState.Checked

    def _on_catalog_checkbox_changed(self, service_id: str, state: object) -> None:
        if self._is_checkbox_checked(state):
            self._catalog_checked_ids.add(service_id)
        else:
            self._catalog_checked_ids.discard(service_id)

    def _service_lookup(self) -> dict[str, dict]:
        source = self._catalog_base if self._catalog_base is not None else self._catalog_all
        return {str(item.get("id")): item for item in source if item.get("id")}

    def _apply_patient(self, patient: dict) -> None:
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no", ""))
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self.mobile.setText(patient.get("mobile") or patient.get("phone") or "")
        self._set_status(f"Patient loaded: {patient.get('patient_no')}")

    def _load_patient_by_no(self, patient_no: str, *, show_errors: bool = True) -> dict | None:
        patient_no = patient_no.strip()
        if not patient_no:
            self._patient = None
            self.patient_name.clear()
            self.mobile.clear()
            return None

        if self._patient and (self._patient.get("patient_no") or "").strip().upper() == patient_no.upper():
            return self._patient

        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                result = self.api.list_patients(search=patient_no, page_size=20)
                items = [
                    item
                    for item in (result.get("items") or [])
                    if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
                ]
            if not items:
                self._patient = None
                self.patient_name.clear()
                self.mobile.clear()
                if show_errors:
                    QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
                else:
                    self._set_status(f"Patient not found: {patient_no}")
                return None
            self._apply_patient(items[0])
            return items[0]
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Patient", str(exc))
            else:
                self._set_status(str(exc))
            return None

    def _on_patient_id_lookup(self) -> None:
        self._load_patient_by_no(self.patient_id.text().strip(), show_errors=False)

    def _find_patient(self) -> None:
        patient = pick_patient(self.api, self, initial_patient_no=self.patient_id.text().strip())
        if not patient:
            return
        self._apply_patient(patient)

    def _add_by_code(self) -> None:
        code = self.service_code_entry.text().strip()
        if not code:
            return
        patient_id = self._patient.get("id") if self._patient else None
        try:
            rows = self.api.expand_pathology_service(code, patient_id=patient_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Service", str(exc))
            return
        if not rows:
            QMessageBox.information(self, "Service", f"No lines for code: {code}")
            return
        for row in rows:
            self._add_line_from_expand(row)
        self.service_code_entry.clear()
        self._refresh_lines_table()
        self._calculate()
        self._set_status(f"Added {len(rows)} line(s) for code {code}")

    def _add_line_from_expand(self, row: dict, *, rate_override: float | None = None) -> None:
        is_parent = bool(row.get("is_panel_parent"))
        is_bundle_member = bool(row.get("panel_service_id")) and not is_parent
        if is_bundle_member:
            rate = 0.0
        else:
            rate = float(rate_override if rate_override is not None else row.get("rate", 0))
        qty = int(row.get("quantity", 1))
        self._bill_lines.append(
            {
                "service_id": row.get("service_id"),
                "service_code": row.get("service_code"),
                "service_name": row.get("service_name"),
                "panel_service_id": row.get("panel_service_id"),
                "panel_name": row.get("panel_name"),
                "is_panel_parent": is_parent,
                "reference_range_text": row.get("reference_range_text"),
                "min_value": row.get("min_value"),
                "max_value": row.get("max_value"),
                "result_value": "",
                "is_abnormal": False,
                "abnormal_manual": False,
                "category_name": None,
                "sub_category_name": None,
                "rate": rate,
                "quantity": qty,
                "amount": float(rate * qty),
                "line_source": "panel" if row.get("panel_service_id") else "manual",
                "package_id": None,
            }
        )
        self._apply_service_note(row.get("service_code"))

    def _add_line_from_service(self, service: dict) -> None:
        patient_id = self._patient.get("id") if self._patient else None
        override_rate = float(service.get("rate", 0))
        try:
            rows = self.api.expand_pathology_service(
                service.get("code") or "", patient_id=patient_id
            )
        except ApiError:
            rows = []
        if rows:
            parent_added = False
            for row in rows:
                rate_override = None
                if row.get("is_panel_parent"):
                    rate_override = override_rate
                    parent_added = True
                elif not parent_added and len(rows) == 1:
                    rate_override = override_rate
                self._add_line_from_expand(row, rate_override=rate_override)
            self._refresh_lines_table()
            self._calculate()
            return
        rate = float(service.get("rate", 0))
        for line in self._bill_lines:
            if line.get("service_id") == service.get("id"):
                line["quantity"] = int(line.get("quantity", 1)) + 1
                line["amount"] = rate * line["quantity"]
                self._refresh_lines_table()
                self._calculate()
                return
        self._bill_lines.append(
            {
                "service_id": service.get("id"),
                "service_code": service.get("code"),
                "service_name": service.get("name"),
                "category_name": service.get("category_name"),
                "sub_category_name": service.get("sub_category_name"),
                "result_value": "",
                "is_abnormal": False,
                "abnormal_manual": False,
                "min_value": None,
                "max_value": None,
                "rate": rate,
                "quantity": 1,
                "amount": rate,
                "line_source": "manual",
                "package_id": None,
            }
        )
        self._apply_service_note(service.get("code"))
        self._refresh_lines_table()
        self._calculate()

    def _add_selected_services(self) -> None:
        self._collect_catalog_checked_ids()
        if not self._catalog_checked_ids:
            return
        lookup = self._service_lookup()
        for service_id in list(self._catalog_checked_ids):
            service = lookup.get(str(service_id))
            if service:
                self._add_line_from_service(self._service_with_catalog_rate(service))
                self._catalog_checked_ids.discard(service_id)
                self._catalog_rate_overrides.pop(str(service_id), None)
        self._apply_catalog_search()

    def _remove_selected_lines(self) -> None:
        rows = sorted({i.row() for i in self.lines_table.selectedItems()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._bill_lines):
                self._bill_lines.pop(row)
        self._refresh_lines_table()
        self._calculate()

    def _refresh_lines_table(self) -> None:
        self._lines_table_updating = True
        try:
            self.lines_table.setRowCount(len(self._bill_lines))
            shown_panel: str | None = None
            for row, line in enumerate(self._bill_lines):
                name = line.get("service_name") or ""
                panel_name = line.get("panel_name")
                panel_id = line.get("panel_service_id")
                if line.get("is_panel_parent"):
                    # Bundle header row — name once, no sub-test.
                    group = name
                    sub = ""
                    shown_panel = panel_id or line.get("service_id")
                elif panel_name:
                    # Member of a bundle — show the bundle name only the first time.
                    sub = name
                    group = "" if panel_id == shown_panel else panel_name
                    shown_panel = panel_id
                else:
                    group = name
                    sub = ""
                    shown_panel = None
                is_parent = bool(line.get("is_panel_parent"))
                is_bundle_member = bool(panel_id) and not is_parent
                if is_bundle_member:
                    # Sub-tests of a bundle never carry price — only the parent does.
                    line["rate"] = 0
                    line["amount"] = 0
                self.lines_table.setItem(row, COL_CODE, self._compact_table_item(line.get("service_code", "")))
                self.lines_table.setItem(row, COL_GROUP, self._compact_table_item(group))
                self.lines_table.setItem(
                    row, COL_SUB, self._compact_table_item(sub, editable=bool(panel_name))
                )
                self.lines_table.setItem(
                    row,
                    COL_QTY,
                    self._compact_table_item(str(line.get("quantity", 1)), editable=not is_bundle_member),
                )
                rate_text = "" if is_bundle_member else f"{float(line.get('rate', 0)):.2f}"
                amount_text = "" if is_bundle_member else f"{float(line.get('amount', 0)):.2f}"
                self.lines_table.setItem(
                    row,
                    COL_RATE,
                    self._compact_table_item(rate_text, editable=not is_bundle_member),
                )
                self.lines_table.setItem(row, COL_AMOUNT, self._compact_table_item(amount_text))
                result_item = self._compact_table_item(
                    line.get("result_value") or "", editable=not is_parent
                )
                if line.get("is_abnormal"):
                    font = result_item.font()
                    font.setBold(True)
                    result_item.setFont(font)
                self.lines_table.setItem(row, COL_RESULT, result_item)
                if is_parent:
                    self.lines_table.removeCellWidget(row, COL_BOLD)
                    self.lines_table.setItem(row, COL_BOLD, self._compact_table_item(""))
                else:
                    self.lines_table.setCellWidget(row, COL_BOLD, self._make_bold_button(row, line))
                self.lines_table.setItem(
                    row, COL_REF, self._compact_table_item(line.get("reference_range_text") or "")
                )
        finally:
            self._lines_table_updating = False

    def _make_bold_button(self, row: int, line: dict) -> QPushButton:
        btn = QPushButton("B")
        btn.setCheckable(True)
        btn.setChecked(bool(line.get("is_abnormal")))
        btn.setFixedSize(22, 22)
        btn.setToolTip("Mark this result abnormal (print in bold)")
        btn.setStyleSheet(BOLD_BTN_STYLE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked, r=row: self._toggle_bold(r))
        return btn

    def _toggle_bold(self, row: int) -> None:
        if row < 0 or row >= len(self._bill_lines):
            return
        line = self._bill_lines[row]
        line["is_abnormal"] = not bool(line.get("is_abnormal"))
        line["abnormal_manual"] = True
        self._apply_abnormal_visual(row)

    def _recompute_abnormal(self, row: int) -> None:
        """Auto-flag a numeric result as abnormal against its reference range."""
        line = self._bill_lines[row]
        if line.get("abnormal_manual"):
            return
        value = (line.get("result_value") or "").strip()
        low = line.get("min_value")
        high = line.get("max_value")
        abnormal = False
        if value and (low is not None or high is not None):
            try:
                num = float(value)
                if low is not None and num < float(low):
                    abnormal = True
                if high is not None and num > float(high):
                    abnormal = True
            except ValueError:
                abnormal = False
        line["is_abnormal"] = abnormal

    def _apply_abnormal_visual(self, row: int) -> None:
        line = self._bill_lines[row]
        self._lines_table_updating = True
        try:
            item = self.lines_table.item(row, COL_RESULT)
            if item is not None:
                font = item.font()
                font.setBold(bool(line.get("is_abnormal")))
                item.setFont(font)
            btn = self.lines_table.cellWidget(row, COL_BOLD)
            if isinstance(btn, QPushButton):
                btn.setChecked(bool(line.get("is_abnormal")))
        finally:
            self._lines_table_updating = False

    def _on_line_item_changed(self, item: QTableWidgetItem) -> None:
        if self._lines_table_updating:
            return
        row = item.row()
        if row < 0 or row >= len(self._bill_lines):
            return
        column = item.column()
        line = self._bill_lines[row]
        if column == COL_SUB:
            name = item.text().strip()
            if name:
                line["service_name"] = name
        elif column == COL_RESULT:
            line["result_value"] = item.text().strip()
            self._recompute_abnormal(row)
            self._apply_abnormal_visual(row)
        elif column in (COL_RATE, COL_QTY):
            is_bundle_member = bool(line.get("panel_service_id")) and not line.get("is_panel_parent")
            if is_bundle_member:
                line["rate"] = 0
                line["amount"] = 0
                return
            try:
                from decimal import Decimal

                rate = Decimal(str(line.get("rate", 0)))
                qty = int(line.get("quantity", 1))
                if column == COL_RATE:
                    rate = Decimal(item.text().strip() or "0")
                    line["rate"] = float(rate)
                else:
                    qty = max(int(item.text().strip() or "1"), 1)
                    line["quantity"] = qty
                amount = float(rate * qty)
                line["amount"] = amount
                self._lines_table_updating = True
                try:
                    amount_item = self.lines_table.item(row, COL_AMOUNT)
                    if amount_item:
                        amount_item.setText(f"{amount:.2f}")
                finally:
                    self._lines_table_updating = False
                self._calculate()
            except (ArithmeticError, ValueError):
                pass

    def _parse_amount(self, field: QLineEdit):
        from decimal import Decimal

        text = field.text().strip() or "0"
        return Decimal(text)

    def _calculate(self) -> None:
        from decimal import Decimal

        gross = sum(Decimal(str(line.get("amount", 0))) for line in self._bill_lines)
        net = (
            gross
            + self._parse_amount(self.admin_charges)
            - self._parse_amount(self.scheme_discount)
            - self._parse_amount(self.adjust_advance)
        )
        if net < 0:
            net = Decimal("0")
        self.net_amount.setText(f"{net:.2f}")

    def _save_bill(self) -> None:
        if not self._patient:
            QMessageBox.warning(self, "Validation", "Find and load a patient first.")
            return
        if not self._bill_lines:
            QMessageBox.warning(self, "Validation", "Add at least one lab test.")
            return
        qd = self.bill_date.date()
        bill_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        sq = self.sample_date.date()
        sample_date = date(sq.year(), sq.month(), sq.day()).isoformat()
        payload = {
            "doctor_id": self.doctor.currentData(),
            "referring_doctor": self._referring_doctor_value(),
            "payment_mode_id": self.payment_mode.currentData(),
            "department_id": self.department.currentData() or self._path_dept_id,
            "is_cash": self.cash_credit.currentIndex() == 0,
            "scheme": self.scheme.text().strip() or None,
            "admin_charges": str(self._parse_amount(self.admin_charges)),
            "scheme_discount": str(self._parse_amount(self.scheme_discount)),
            "adjust_advance": str(self._parse_amount(self.adjust_advance)),
            "sample_date": sample_date,
            "sample_no": self.sample_no.text().strip() or None,
            "remarks": self.notes_edit.toPlainText().strip() or None,
            "lines": [
                {
                    "service_id": line["service_id"],
                    "quantity": line["quantity"],
                    "rate": str(line["rate"]),
                    "service_name": line.get("service_name"),
                    "line_source": line.get("line_source", "manual"),
                    "package_id": line.get("package_id"),
                    "panel_service_id": line.get("panel_service_id"),
                    "panel_name": line.get("panel_name"),
                    "is_panel_parent": line.get("is_panel_parent", False),
                    "reference_range_text": line.get("reference_range_text"),
                    "result_value": (line.get("result_value") or "").strip() or None,
                    "is_abnormal": bool(line.get("is_abnormal", False)),
                }
                for line in self._bill_lines
            ],
        }
        if not self._modification_mode:
            payload["patient_id"] = self._patient.get("id")
            payload["bill_date"] = bill_date
        try:
            if self._modification_mode:
                if not self._saved_bill_id:
                    QMessageBox.warning(self, "Validation", "Load a bill to modify first.")
                    return
                bill = self.api.update_pathology_bill(self._saved_bill_id, payload)
                action = "updated"
            else:
                bill = self.api.create_pathology_bill(payload)
                action = "saved"
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        # Keep the editor in sync with what the server persisted (esp. after modify).
        self._load_saved_bill(bill)
        bill_no = bill.get("bill_no", "")
        if bill_no:
            QGuiApplication.clipboard().setText(bill_no)
        self._set_status(f"Pathology bill {action}: {bill_no} — opening preview.")
        title = "Updated" if self._modification_mode else "Saved"
        QMessageBox.information(self, title, f"Pathology Bill {bill_no} {action} successfully.")
        self._preview_bill()

    def on_module_deactivated(self) -> None:
        if not self._modification_mode:
            self._clear_bill()
            self._refresh_hold_buttons()

    def _capture_hold_state(self) -> dict:
        return {
            "hold_label": hold_label_from_patient(self._patient),
            "patient": dict(self._patient) if self._patient else None,
            "bill_lines": [dict(line) for line in self._bill_lines],
            "bill_date": date_iso(self.bill_date),
            "sample_date": date_iso(self.sample_date),
            "sample_no": self.sample_no.text(),
            "scheme": self.scheme.text(),
            "admin_charges": self.admin_charges.text(),
            "scheme_discount": self.scheme_discount.text(),
            "adjust_advance": self.adjust_advance.text(),
            "cash_credit_index": self.cash_credit.currentIndex(),
            "payment_mode_id": self.payment_mode.currentData(),
            "doctor_id": self.doctor.currentData(),
            "department_id": self.department.currentData(),
            "referring_doctor": self._referring_doctor_value(),
            "notes": self.notes_edit.toPlainText(),
            "inserted_note_texts": list(self._inserted_note_texts),
            "catalog_checked_ids": list(self._catalog_checked_ids),
            "catalog_rate_overrides": dict(self._catalog_rate_overrides),
        }

    def _restore_hold_state(self, state: dict) -> None:
        self._clear_bill()
        patient = state.get("patient")
        if patient:
            self._apply_patient(patient)
        set_date_iso(self.bill_date, state.get("bill_date"))
        set_date_iso(self.sample_date, state.get("sample_date"))
        self.sample_no.setText(state.get("sample_no") or "")
        self.scheme.setText(state.get("scheme") or "")
        self.admin_charges.setText(state.get("admin_charges") or "0")
        self.scheme_discount.setText(state.get("scheme_discount") or "0")
        self.adjust_advance.setText(state.get("adjust_advance") or "0")
        cash_idx = state.get("cash_credit_index")
        if isinstance(cash_idx, int) and 0 <= cash_idx < self.cash_credit.count():
            self.cash_credit.setCurrentIndex(cash_idx)
        set_combo_value(self.payment_mode, state.get("payment_mode_id"))
        set_combo_value(self.doctor, state.get("doctor_id"))
        set_combo_value(self.department, state.get("department_id"))
        self._set_referring_doctor(state.get("referring_doctor"))
        self.notes_edit.setPlainText(state.get("notes") or "")
        self._inserted_note_texts = set(state.get("inserted_note_texts") or [])
        self._catalog_checked_ids = {str(sid) for sid in (state.get("catalog_checked_ids") or [])}
        self._catalog_rate_overrides = dict(state.get("catalog_rate_overrides") or {})
        self._bill_lines = [dict(line) for line in (state.get("bill_lines") or [])]
        self._on_catalog_filter_changed()
        self._refresh_lines_table()
        self._calculate()

    def _clear_bill(self) -> None:
        self._patient = None
        self._bill_lines = []
        self._saved_bill_id = None
        self.patient_id.clear()
        self.patient_name.clear()
        self.mobile.clear()
        self.bill_no.clear()
        self.sample_no.clear()
        self.sample_date.setDate(QDate.currentDate())
        self.order_status.clear()
        self._set_referring_doctor(None)
        self.scheme.clear()
        self.admin_charges.setText("0")
        self.scheme_discount.setText("0")
        self.adjust_advance.setText("0")
        self.net_amount.setText("0.00")
        self.notes_edit.clear()
        self._inserted_note_texts = set()
        self._append_note(self._general_note)
        self._refresh_lines_table()
        self._refresh_hold_buttons()
        self._set_status("Ready for new pathology bill.")

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
