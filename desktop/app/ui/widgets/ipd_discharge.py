from collections.abc import Callable
from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.billing_catalog import (
    catalog_from_cache,
    filter_catalog,
    load_ipd_catalog_from_api,
)
from app.services.billing_sharing import build_bill_line_amounts, sharing_fields_for_payload
from app.session import get_session
from app.services.master_cache import refresh_patient_services_cache
from app.ui.bill_hold import (
    BillHoldMixin,
    date_iso,
    hold_label_from_patient,
    set_combo_value,
    set_date_iso,
)
from app.ui.components.date_edit import style_date_field
from app.ui.components.multi_payment_panel import MultiPaymentPanel
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.styles import HEADER_BTN_STYLE, TABLE_COMPACT_STYLE as SERVICE_TABLE_STYLE

LEFT_PANE_WIDTH = 500
SERVICE_TABLE_ROW_HEIGHT = 26
CATALOG_COL_RATE = 4
CATALOG_CODE_WIDTH = 70
CATALOG_SERVICE_WIDTH = 260
CATALOG_CATEGORY_WIDTH = 90
CATALOG_RATE_WIDTH = 90
FILTER_GROUP_STYLE = """
QGroupBox {
    margin-top: 4px;
    padding: 3px 6px 2px 6px;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""
LEFT_GROUP_STYLE = """
QGroupBox {
    margin-top: 4px;
    padding: 4px 6px 2px 6px;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""
LEFT_LABEL_STYLE = "font-size: 12px; padding: 1px 0; margin: 0;"


def _left_field_style() -> str:
    from app.ui.styles import compact_field_style, form_field_style

    return form_field_style() + compact_field_style()


def _left_field_height() -> int:
    from app.ui.styles import left_pane_field_height

    return left_pane_field_height()


def _left_form_spacing() -> int:
    from app.ui.responsive_layout import get_density

    return max(2, get_density().form_v_spacing - 4)


LEFT_FIELD_STYLE = _left_field_style()
LEFT_FIELD_HEIGHT = _left_field_height()
LEFT_FORM_SPACING = _left_form_spacing()
LEFT_SECTION_SPACING = 2
LEFT_LABEL_WIDTH = 92

class IpdDischargeWidget(BillHoldMixin, QWidget):
    pending_admission: dict | None = None
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
        self._admission: dict | None = None
        self._catalog: list[dict] = []
        self._catalog_all: list[dict] = []
        self._catalog_base: list[dict] | None = None
        self._catalog_checked_ids: set[str] = set()
        self._catalog_rate_overrides: dict[str, str] = {}
        self._catalog_table_updating = False
        self._bill_lines: list[dict] = []
        self._saved_bill_id: str | None = None
        self._splitter_sized = False
        self._lines_table_updating = False
        self._adjust_advance = Decimal("0")
        self._bill_prior_adjust = Decimal("0")
        self._patient_deposit_balance = Decimal("0")
        self._patient_id_enter = False
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

    @staticmethod
    def _grid_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LEFT_LABEL_STYLE)
        label.setFixedWidth(LEFT_LABEL_WIDTH)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    @classmethod
    def queue_admission(cls, admission: dict | None) -> None:
        cls.pending_admission = admission

    def _style_left_field(self, field, *, min_width: int = 90) -> None:
        if isinstance(field, QDateEdit):
            style_date_field(
                field,
                compact=True,
                fixed_height=LEFT_FIELD_HEIGHT,
                min_width=min_width,
                extra_style=LEFT_FIELD_STYLE,
            )
            field.setProperty("hmsAllowWide", True)
            field.setMaximumWidth(16777215)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return
        field.setStyleSheet(LEFT_FIELD_STYLE)
        field.setFixedHeight(LEFT_FIELD_HEIGHT)
        field.setProperty("hmsAllowWide", True)
        field.setMaximumWidth(16777215)
        field.setMinimumWidth(min_width)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(5)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setCollapsible(0, False)
        outer.addWidget(self._splitter, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setMinimumWidth(LEFT_PANE_WIDTH)

        left_host = QWidget()
        left_host.setMinimumWidth(LEFT_PANE_WIDTH - 24)
        left_scroll.setWidget(left_host)
        left = QVBoxLayout(left_host)
        left.setContentsMargins(2, 2, 2, 2)
        left.setSpacing(LEFT_SECTION_SPACING)

        admission_box = QGroupBox("Patient / Admission")
        admission_box.setStyleSheet(LEFT_GROUP_STYLE)
        admission_box.setProperty("hmsSkipResponsive", True)
        admission_grid = QGridLayout(admission_box)
        admission_grid.setVerticalSpacing(LEFT_FORM_SPACING)
        admission_grid.setHorizontalSpacing(8)
        admission_grid.setContentsMargins(6, 8, 6, 4)
        admission_grid.setColumnStretch(1, 1)
        admission_grid.setColumnStretch(3, 1)
        admission_grid.setColumnMinimumWidth(0, LEFT_LABEL_WIDTH)
        admission_grid.setColumnMinimumWidth(2, LEFT_LABEL_WIDTH)

        self.patient_id_input = QLineEdit()
        self.patient_id_input.setPlaceholderText("Patient No")
        self.patient_id_input.editingFinished.connect(self._on_patient_id_lookup)
        self.patient_id_input.returnPressed.connect(self._on_patient_id_enter)
        find_btn = QPushButton("Find Patient")
        find_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        find_btn.clicked.connect(self._find_patient)
        pid_row = QHBoxLayout()
        pid_row.setContentsMargins(0, 0, 0, 0)
        pid_row.setSpacing(6)
        pid_row.addWidget(self.patient_id_input, stretch=1)
        pid_row.addWidget(find_btn)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self.admission_no = QLineEdit()
        self.admission_no.setReadOnly(True)
        self.admission_no.setPlaceholderText("Optional")
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("On Discharge")
        self.ward = QComboBox()
        self.bed_no = QComboBox()
        self.bed_no.setEditable(True)
        self.bed_no.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        bed_edit = self.bed_no.lineEdit()
        if bed_edit is not None:
            bed_edit.setPlaceholderText("Select or type")
        self.doctor = QComboBox()
        self.admission_date = QDateEdit()
        self.admission_date.setCalendarPopup(True)
        self.admission_date.setDisplayFormat("dd/MM/yyyy")
        self.admission_date.setDate(QDate.currentDate())
        self.admission_date.dateChanged.connect(self._update_stay_days)
        self.discharge_date = QDateEdit()
        self.discharge_date.setCalendarPopup(True)
        self.discharge_date.setDisplayFormat("dd/MM/yyyy")
        self.discharge_date.setDate(QDate.currentDate())
        self.discharge_date.dateChanged.connect(self._update_stay_days)
        self.stay_days = QLineEdit()
        self.stay_days.setReadOnly(True)
        self.scheme = QLineEdit()
        self.scheme.setPlaceholderText("No Scheme")

        admission_grid.addWidget(self._grid_label("Patient Id"), 0, 0)
        admission_grid.addLayout(pid_row, 0, 1, 1, 3)
        admission_grid.addWidget(self._grid_label("Patient Name"), 1, 0)
        admission_grid.addWidget(self.patient_name, 1, 1, 1, 3)
        admission_grid.addWidget(self._grid_label("Admission No"), 2, 0)
        admission_grid.addWidget(self.admission_no, 2, 1)
        admission_grid.addWidget(self._grid_label("Bill No"), 2, 2)
        admission_grid.addWidget(self.bill_no, 2, 3)
        admission_grid.addWidget(self._grid_label("Ward"), 3, 0)
        admission_grid.addWidget(self.ward, 3, 1)
        admission_grid.addWidget(self._grid_label("Bed No"), 3, 2)
        admission_grid.addWidget(self.bed_no, 3, 3)
        admission_grid.addWidget(self._grid_label("Doctor"), 4, 0)
        admission_grid.addWidget(self.doctor, 4, 1, 1, 3)
        admission_grid.addWidget(self._grid_label("Admit Date"), 5, 0)
        admission_grid.addWidget(self.admission_date, 5, 1)
        admission_grid.addWidget(self._grid_label("Discharge"), 5, 2)
        admission_grid.addWidget(self.discharge_date, 5, 3)
        admission_grid.addWidget(self._grid_label("Stay Days"), 6, 0)
        admission_grid.addWidget(self.stay_days, 6, 1)
        admission_grid.addWidget(self._grid_label("Scheme"), 6, 2)
        admission_grid.addWidget(self.scheme, 6, 3)
        left.addWidget(admission_box)

        totals_box = QGroupBox("Advance / Net")
        totals_box.setStyleSheet(LEFT_GROUP_STYLE)
        totals_box.setProperty("hmsSkipResponsive", True)
        totals_layout = QVBoxLayout(totals_box)
        totals_layout.setContentsMargins(6, 8, 6, 4)
        totals_layout.setSpacing(4)
        self.advance_on_admission = QLineEdit()
        self.advance_on_admission.setReadOnly(True)
        self.advance_on_admission.setPlaceholderText("0.00")
        self.adjust_advance_chk = QCheckBox("Adjust to bill")
        self.adjust_advance_chk.setEnabled(False)
        self.adjust_advance_chk.setToolTip(
            "Apply patient advance against this receivable bill. "
            "Posts to deposit ledger and reduces patient advance balance."
        )
        self.adjust_advance_chk.toggled.connect(self._on_adjust_advance_toggled)
        self.hide_advance_chk = QCheckBox("Don't show advance on bill")
        self.hide_advance_chk.setToolTip(
            "Omits the advance line from the printed bill only. "
            "Accounts still record the advance adjustment."
        )
        advance_row = QHBoxLayout()
        advance_row.setContentsMargins(0, 0, 0, 0)
        advance_row.setSpacing(8)
        advance_lbl = QLabel("Advance")
        advance_lbl.setFixedWidth(LEFT_LABEL_WIDTH)
        advance_lbl.setStyleSheet("font-weight: bold; color: #334155; font-size: 12px;")
        advance_row.addWidget(advance_lbl)
        advance_row.addWidget(self.advance_on_admission, stretch=1)
        totals_layout.addLayout(advance_row)
        chk_row = QHBoxLayout()
        chk_row.setContentsMargins(LEFT_LABEL_WIDTH + 8, 0, 0, 0)
        chk_row.setSpacing(12)
        chk_row.addWidget(self.adjust_advance_chk)
        chk_row.addWidget(self.hide_advance_chk)
        chk_row.addStretch(1)
        totals_layout.addLayout(chk_row)

        net_row = QHBoxLayout()
        net_row.setContentsMargins(0, 0, 0, 0)
        net_row.setSpacing(8)
        net_label = QLabel("Net Amount")
        net_label.setFixedWidth(LEFT_LABEL_WIDTH)
        net_label.setStyleSheet("font-weight: bold; color: #334155; font-size: 12px;")
        self.net_amount = QLineEdit("0.00")
        self.net_amount.setReadOnly(True)
        self.net_amount.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.net_amount.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #b91c1c; padding: 2px 6px;"
            "background: #ffffff; border: 2px solid #94a3b8; border-radius: 4px;"
        )
        net_row.addWidget(net_label)
        net_row.addWidget(self.net_amount, stretch=1)
        totals_layout.addLayout(net_row)
        self.advance_adjusted_label = QLabel("")
        self.advance_adjusted_label.setStyleSheet(
            "color: #166534; font-size: 11px; font-weight: 600;"
        )
        self.advance_adjusted_label.setVisible(False)
        totals_layout.addWidget(self.advance_adjusted_label)
        left.addWidget(totals_box)

        self.payment_panel = MultiPaymentPanel(
            "Payments",
            compact=True,
            group_style=LEFT_GROUP_STYLE,
        )
        left.addWidget(self.payment_panel)
        left.addStretch(1)
        self._splitter.addWidget(left_scroll)

        right = QVBoxLayout()
        right_host = QWidget()
        right_host.setLayout(right)
        right_host.setMinimumWidth(480)
        self._splitter.addWidget(right_host)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([LEFT_PANE_WIDTH, 900])

        filter_box = QGroupBox("Service Filters")
        filter_box.setStyleSheet(FILTER_GROUP_STYLE)
        filter_row = QHBoxLayout(filter_box)
        filter_row.setContentsMargins(8, 2, 8, 2)
        filter_row.setSpacing(8)
        self.category = QComboBox()
        self.category.setMinimumWidth(140)
        self.package = QComboBox()
        self.package.setMinimumWidth(180)
        show_btn = QPushButton("Show All")
        show_btn.clicked.connect(self._show_all_services)
        apply_pkg_btn = QPushButton("Apply Package")
        apply_pkg_btn.clicked.connect(self._apply_package)
        self.category.currentIndexChanged.connect(self._on_catalog_filter_changed)
        self._catalog_search_timer = QTimer(self)
        self._catalog_search_timer.setSingleShot(True)
        self._catalog_search_timer.setInterval(200)
        self._catalog_search_timer.timeout.connect(self._apply_catalog_search)
        filter_row.addWidget(QLabel("Category"))
        filter_row.addWidget(self.category)
        filter_row.addWidget(QLabel("Package"))
        filter_row.addWidget(self.package)
        filter_row.addStretch()
        filter_row.addWidget(show_btn)
        filter_row.addWidget(apply_pkg_btn)
        right.addWidget(filter_box)

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
        self.catalog_table.setColumnWidth(1, CATALOG_CODE_WIDTH)
        catalog_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(2, CATALOG_SERVICE_WIDTH)
        catalog_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(3, CATALOG_CATEGORY_WIDTH)
        catalog_header.setSectionResizeMode(CATALOG_COL_RATE, QHeaderView.ResizeMode.Interactive)
        self.catalog_table.setColumnWidth(CATALOG_COL_RATE, CATALOG_RATE_WIDTH)
        self.catalog_table.itemChanged.connect(self._on_catalog_item_changed)

        self.lines_table = QTableWidget(0, 6)
        self.lines_table.setHorizontalHeaderLabels(
            ["Code", "Service", "Category", "Rate", "Qty", "Amount"]
        )
        self.lines_table.setProperty(
            "hmsColumnKinds", ["code", "text", "short", "number", "number", "number"]
        )
        self.lines_table.setProperty("hmsNoStretch", True)
        self._configure_service_table(self.lines_table)
        lines_header = self.lines_table.horizontalHeader()
        lines_header.setStretchLastSection(False)
        lines_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        lines_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.lines_table.setColumnWidth(0, CATALOG_CODE_WIDTH)
        self.lines_table.setColumnWidth(1, CATALOG_SERVICE_WIDTH)
        self.lines_table.setColumnWidth(2, CATALOG_CATEGORY_WIDTH)
        self.lines_table.setColumnWidth(3, 80)
        self.lines_table.setColumnWidth(4, 50)
        self.lines_table.setColumnWidth(5, 90)

        catalog_header_row = QHBoxLayout()
        catalog_header_row.setSpacing(8)
        catalog_lbl = QLabel("Available Services")
        catalog_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Search service name or code...")
        self.catalog_search.setMinimumWidth(180)
        self.catalog_search.setClearButtonEnabled(True)
        self.catalog_search.textChanged.connect(self._debounce_catalog_search)
        catalog_header_row.addWidget(catalog_lbl)
        catalog_header_row.addWidget(self.catalog_search, stretch=1)
        right.addLayout(catalog_header_row)
        right.addWidget(self.catalog_table, stretch=1)

        lines_header_row = QHBoxLayout()
        lines_header_row.setSpacing(8)
        lines_lbl = QLabel("Bill Lines")
        lines_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        add_btn = QPushButton("Add Selected")
        add_btn.clicked.connect(self._add_selected_services)
        remove_btn = QPushButton("Remove Line")
        remove_btn.clicked.connect(self._remove_selected_lines)
        lines_header_row.addWidget(lines_lbl)
        lines_header_row.addStretch()
        lines_header_row.addWidget(add_btn)
        lines_header_row.addWidget(remove_btn)
        right.addLayout(lines_header_row)
        right.addWidget(self.lines_table, stretch=1)
        self.lines_table.itemChanged.connect(self._on_line_item_changed)

        btn_row = QHBoxLayout()
        save_label = "Update Bill" if self._modification_mode else "Discharge & Save Bill"
        self.save_btn = QPushButton(save_label)
        self.save_btn.clicked.connect(self._save_discharge)
        self.print_bill_btn = QPushButton("Print Bill")
        self.print_bill_btn.clicked.connect(self._print_bill)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        if self._modification_mode:
            clear_btn.hide()
        hint = QLabel(
            "Modify services and payments, then click Update Bill."
            if self._modification_mode
            else "Bill No uses IPDB financial-year series (resets 1 April). Preview opens after save."
        )
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.print_bill_btn)
        self._setup_bill_hold_buttons(btn_row)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(hint)
        right.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        outer.addWidget(self.status)

        if self._modification_mode:
            self.patient_id_input.setReadOnly(True)
            self.bill_no.setReadOnly(True)
            self.doctor.setEnabled(False)
            self.admission_date.setReadOnly(True)

        for field in (
            self.patient_id_input,
            self.patient_name,
            self.admission_no,
            self.ward,
            self.bed_no,
            self.doctor,
            self.admission_date,
            self.advance_on_admission,
            self.bill_no,
            self.discharge_date,
            self.stay_days,
            self.scheme,
        ):
            self._style_left_field(field, min_width=72)
        self.patient_name.setMinimumWidth(160)
        self.doctor.setMinimumWidth(160)

    def load_bill_for_modification(self, bill: dict) -> None:
        self._load_saved_bill(bill)
        self._set_status(f"Editing bill {bill.get('bill_no', '')} — add/remove services and update payments.")

    def build_header_actions(self) -> QWidget | None:
        from app.ui.header_actions import create_header_action_bar

        if self._modification_mode:
            return create_header_action_bar(
                [
                    ("Adjust Advance", self._enter_advance),
                    ("Collect Advance", self._open_advance_collection),
                ]
            )

        return create_header_action_bar(
            [
                ("Admitted List", self._show_admitted_list),
                ("Reprint Bill", self._reprint_bill),
                ("Discharge Summary", self._open_discharge_summary),
                ("Adjust Advance", self._enter_advance),
                ("Collect Advance", self._open_advance_collection),
                ("IPD Admission", lambda: self._navigate("in_patient_admission")),
            ]
        )

    def _open_advance_collection(self) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut("advance_collection", parent=self, api=self.api, on_navigate=self._on_navigate)

    def _available_advance(self) -> Decimal:
        """Current deposit balance, plus any amount already applied on a loaded bill."""
        return self._patient_deposit_balance + self._bill_prior_adjust

    def _refresh_deposit_balance(self) -> None:
        patient_id = None
        if self._patient:
            patient_id = self._patient.get("id")
        elif self._admission:
            patient_id = self._admission.get("patient_id")
        if not patient_id:
            self._patient_deposit_balance = Decimal("0")
            self.advance_on_admission.setText("0.00")
            self._sync_adjust_advance_checkbox(enabled=False, checked=False)
            return
        try:
            data = self.api.get_patient_deposit_balance(
                patient_id=patient_id,
                patient_no=(
                    (self._patient or {}).get("patient_no")
                    or (self._admission or {}).get("patient_no")
                    or self.patient_id_input.text().strip()
                    or None
                ),
            )
            self._patient_deposit_balance = Decimal(str(data.get("balance", 0) or 0))
            self.advance_on_admission.setText(f"{self._available_advance():,.2f}")
        except ApiError as exc:
            self._patient_deposit_balance = Decimal("0")
            self.advance_on_admission.setText(f"{self._available_advance():,.2f}")
            self._set_status(f"Advance balance unavailable: {exc}")
        available = self._available_advance()
        has_advance = available > 0
        if not has_advance and self._adjust_advance <= 0:
            self._sync_adjust_advance_checkbox(enabled=False, checked=False)
        else:
            self._sync_adjust_advance_checkbox(
                enabled=has_advance or self._adjust_advance > 0,
                checked=self.adjust_advance_chk.isChecked() or self._adjust_advance > 0,
            )

    def _sync_adjust_advance_checkbox(self, *, enabled: bool, checked: bool) -> None:
        self.adjust_advance_chk.blockSignals(True)
        self.adjust_advance_chk.setEnabled(enabled)
        self.adjust_advance_chk.setChecked(checked)
        self.adjust_advance_chk.blockSignals(False)
        if not checked:
            self._adjust_advance = Decimal("0")

    def _on_adjust_advance_toggled(self, checked: bool) -> None:
        if checked:
            gross = sum(Decimal(str(line.get("amount", 0))) for line in self._bill_lines)
            available = self._available_advance()
            self._adjust_advance = min(available, gross)
            if available > 0 and gross <= 0:
                self._set_status(
                    f"Advance {available:,.2f} will apply when bill lines are added."
                )
            elif self._adjust_advance > 0:
                self._set_status(
                    f"Advance {self._adjust_advance:,.2f} will be adjusted against receivable."
                )
        else:
            self._adjust_advance = Decimal("0")
            self._set_status("Advance adjustment cleared.")
        self._calculate()

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _open_discharge_summary(self) -> None:
        admission = self._admission
        if not admission and self._saved_bill_id:
            try:
                bill = self.api.get_ipd_discharge(self._saved_bill_id)
                admission = {
                    "id": bill.get("admission_id"),
                    "patient_id": bill.get("patient_id"),
                    "patient_no": bill.get("patient_no"),
                    "patient_name": bill.get("patient_name"),
                    "admission_no": bill.get("admission_no"),
                    "ward_name": bill.get("ward_name"),
                    "doctor_name": bill.get("doctor_name"),
                    "doctor_id": bill.get("doctor_id"),
                    "admission_date": bill.get("admission_date"),
                    "discharge_date": bill.get("discharge_date"),
                }
            except ApiError:
                admission = None
        if admission:
            from app.ui.widgets.discharge_summary import set_pending_admission

            set_pending_admission(admission)
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(
            "diagnose_management",
            parent=self,
            api=self.api,
            on_navigate=self._on_navigate,
        )

    @staticmethod
    def _format_patient_name(patient: dict) -> str:
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        return " ".join(p for p in parts if p)

    def _set_admission_date_from_iso(self, value: str | date | None) -> None:
        if not value:
            self.admission_date.setDate(QDate.currentDate())
            return
        parts = str(value).split("-")
        if len(parts) == 3:
            self.admission_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))

    def _admission_date_iso(self) -> str:
        qd = self.admission_date.date()
        return date(qd.year(), qd.month(), qd.day()).isoformat()

    def _set_doctor(self, doctor_id: str | None) -> None:
        if doctor_id:
            idx = self.doctor.findData(doctor_id)
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)
                return
        self.doctor.setCurrentIndex(0)

    def _load_doctors(self) -> None:
        cache = get_session().cache
        current = self.doctor.currentData()
        self.doctor.clear()
        self.doctor.addItem("— Select Doctor —", None)
        doctors = list(cache.doctors if cache.loaded else [])
        if not doctors:
            try:
                result = self.api.list_doctors(page_size=200)
                doctors = result.get("items", [])
            except ApiError:
                doctors = []
        for doc in doctors:
            label = f"{doc.get('doctor_code')} — {doc.get('full_name', '')}"
            self.doctor.addItem(label, doc.get("id"))
        if current:
            idx = self.doctor.findData(current)
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)

    def _load_wards(self) -> None:
        cache = get_session().cache
        current = self.ward.currentData()
        self.ward.clear()
        self.ward.addItem("— Select Ward —", None)
        wards = list(cache.wards if cache.loaded else [])
        if not wards:
            try:
                wards = self.api.list_wards()
            except ApiError:
                wards = []
        for ward in wards:
            self.ward.addItem(f"{ward.get('code')} — {ward.get('name')}", ward.get("id"))
        self._set_ward(current)

    def _load_beds(self) -> None:
        current = self._bed_text()
        beds: list[str] = []
        try:
            rows = self.api.list_ipd_admissions()
        except ApiError:
            rows = []
        for row in rows:
            bed = (row.get("bed_no") or "").strip()
            if bed and bed not in beds:
                beds.append(bed)
        self.bed_no.blockSignals(True)
        self.bed_no.clear()
        self.bed_no.addItem("")
        for bed in sorted(beds):
            self.bed_no.addItem(bed)
        self.bed_no.blockSignals(False)
        self._set_bed(current)

    def _set_ward(self, ward_id: str | None, ward_name: str | None = None) -> None:
        if ward_id:
            idx = self.ward.findData(ward_id)
            if idx >= 0:
                self.ward.setCurrentIndex(idx)
                return
        if ward_name:
            needle = ward_name.strip().lower()
            for idx in range(self.ward.count()):
                if needle and needle in self.ward.itemText(idx).lower():
                    self.ward.setCurrentIndex(idx)
                    return
        if self.ward.count():
            self.ward.setCurrentIndex(0)

    def _set_bed(self, bed_no: str | None) -> None:
        text = (bed_no or "").strip()
        if not text:
            self.bed_no.setCurrentIndex(0 if self.bed_no.count() else -1)
            if self.bed_no.isEditable():
                self.bed_no.setEditText("")
            return
        idx = self.bed_no.findText(text)
        if idx < 0:
            self.bed_no.addItem(text)
            idx = self.bed_no.findText(text)
        self.bed_no.setCurrentIndex(idx)

    def _bed_text(self) -> str:
        return self.bed_no.currentText().strip()

    def _ward_label(self) -> str:
        if not self.ward.currentData():
            return ""
        text = self.ward.currentText()
        if " — " in text:
            return text.split(" — ", 1)[1]
        return text

    def _clear_admission_fields(self) -> None:
        self._admission = None
        self.admission_no.clear()
        self._set_ward(None)
        self._set_bed(None)
        self.doctor.setCurrentIndex(0)
        self.admission_date.setDate(QDate.currentDate())
        self.advance_on_admission.clear()
        self._bill_prior_adjust = Decimal("0")
        self._sync_adjust_advance_checkbox(enabled=False, checked=False)
        self._patient_deposit_balance = Decimal("0")
        self.stay_days.clear()

    def _apply_patient(self, patient: dict, *, clear_admission: bool = True) -> None:
        self._patient = patient
        self.patient_id_input.setText(patient.get("patient_no") or "")
        self.patient_name.setText(self._format_patient_name(patient))
        if clear_admission:
            self._clear_admission_fields()
            self._try_auto_load_admission(patient.get("id"))
        self._refresh_deposit_balance()
        self._calculate()

    def _load_patient_by_no(self, patient_no: str, *, show_errors: bool = True) -> dict | None:
        patient_no = patient_no.strip()
        if not patient_no:
            self._patient = None
            self.patient_name.clear()
            self._clear_admission_fields()
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
                self._clear_admission_fields()
                if show_errors:
                    QMessageBox.warning(self, "Patient", f"No patient found with id: {patient_no}")
                else:
                    self._set_status(f"Patient not found: {patient_no}")
                return None
            self._apply_patient(items[0])
            self._set_status(f"Patient loaded: {items[0].get('patient_no')}")
            return items[0]
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Patient", str(exc))
            else:
                self._set_status(str(exc))
            return None

    def _on_patient_id_lookup(self) -> None:
        if self._modification_mode or self._patient_id_enter:
            return
        self._load_patient_by_no(self.patient_id_input.text().strip(), show_errors=False)

    def _on_patient_id_enter(self) -> None:
        if self._modification_mode:
            return
        # Enter / paste+Enter should load by exact Patient Id, not open search.
        self._patient_id_enter = True
        self._load_patient_by_no(self.patient_id_input.text().strip(), show_errors=True)
        QTimer.singleShot(0, self._reset_patient_id_enter)

    def _reset_patient_id_enter(self) -> None:
        self._patient_id_enter = False

    def _try_auto_load_admission(self, patient_id: str | None) -> None:
        if not patient_id:
            return
        try:
            rows = self.api.list_ipd_admissions(status="admitted", patient_id=patient_id)
        except ApiError:
            return
        if len(rows) == 1:
            self._load_admission(rows[0], from_patient_lookup=True)

    def _find_patient(self) -> None:
        patient = pick_patient(
            self.api,
            self,
            initial_patient_no=self.patient_id_input.text().strip(),
        )
        if not patient:
            return
        self._apply_patient(patient)

    def _show_admitted_list(self) -> None:
        search = self.patient_id_input.text().strip() or None
        admission = self._pick_admission_dialog(search=search)
        if admission:
            self._load_admission(admission)

    def _pick_admission_dialog(self, search: str | None = None) -> dict | None:
        try:
            rows = self.api.list_ipd_admissions(status="admitted", search=search)
        except ApiError as exc:
            QMessageBox.warning(self, "Admitted Patients", str(exc))
            return None
        if not rows:
            QMessageBox.information(
                self,
                "Admitted Patients",
                "No admitted patients found. Try a different patient id or name.",
            )
            return None
        if len(rows) == 1 and search:
            return rows[0]

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Admitted Patient")
        dialog.resize(900, 480)
        layout = QVBoxLayout(dialog)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter"))
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("Patient id, name, admission no, ward...")
        filter_edit.setText(search or "")
        filter_row.addWidget(filter_edit, stretch=1)
        layout.addLayout(filter_row)

        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["Admission No", "Patient Id", "Patient Name", "Ward", "Bed", "Admit Date", "Doctor"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table, stretch=1)

        status_label = QLabel("")
        status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(status_label)

        def _populate(items: list[dict]) -> None:
            table.setRowCount(len(items))
            for row_idx, item in enumerate(items):
                table.setItem(row_idx, 0, QTableWidgetItem(item.get("admission_no", "")))
                table.setItem(row_idx, 1, QTableWidgetItem(item.get("patient_no") or ""))
                table.setItem(row_idx, 2, QTableWidgetItem(item.get("patient_name") or ""))
                table.setItem(row_idx, 3, QTableWidgetItem(item.get("ward_name") or ""))
                table.setItem(row_idx, 4, QTableWidgetItem(item.get("bed_no") or ""))
                table.setItem(row_idx, 5, QTableWidgetItem(str(item.get("admission_date", ""))))
                table.setItem(row_idx, 6, QTableWidgetItem(item.get("doctor_name") or ""))
                for col in range(7):
                    cell = table.item(row_idx, col)
                    if cell:
                        cell.setData(Qt.ItemDataRole.UserRole, item)
            status_label.setText(f"{len(items)} admitted patient(s). Double-click or Select to load.")

        def _apply_filter() -> None:
            query = filter_edit.text().strip().lower()
            if not query:
                _populate(rows)
                return
            filtered = [
                item
                for item in rows
                if query in (item.get("admission_no") or "").lower()
                or query in (item.get("patient_no") or "").lower()
                or query in (item.get("patient_name") or "").lower()
                or query in (item.get("ward_name") or "").lower()
                or query in (item.get("bed_no") or "").lower()
                or query in (item.get("doctor_name") or "").lower()
            ]
            _populate(filtered)

        filter_edit.textChanged.connect(_apply_filter)
        _apply_filter()

        selected: dict | None = None

        def _accept_selection() -> None:
            nonlocal selected
            sel_rows = table.selectionModel().selectedRows()
            if not sel_rows:
                QMessageBox.information(dialog, "Select", "Choose an admission from the list.")
                return
            cell = table.item(sel_rows[0].row(), 0)
            if cell:
                selected = cell.data(Qt.ItemDataRole.UserRole)
            dialog.accept()

        table.doubleClicked.connect(lambda _index: _accept_selection())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Select")
        buttons.accepted.connect(_accept_selection)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return selected
        return None

    def _enter_advance(self) -> None:
        self._refresh_deposit_balance()
        from app.ui.components.advance_adjust_dialog import prompt_advance_adjust

        amount = prompt_advance_adjust(
            self,
            available=self._available_advance(),
            current=self._adjust_advance,
            title="Advance Adjustment",
        )
        if amount is None:
            return
        self._adjust_advance = amount
        self._sync_adjust_advance_checkbox(
            enabled=self._available_advance() > 0 or self._adjust_advance > 0,
            checked=self._adjust_advance > 0,
        )
        self._calculate()

    def _reprint_bill(self) -> None:
        bill_no, ok = QInputDialog.getText(self, "Reprint IPD Bill", "Enter discharge bill number:")
        if not ok or not bill_no.strip():
            return
        try:
            bill = self.api.get_ipd_discharge_by_no(bill_no.strip())
        except ApiError as exc:
            QMessageBox.warning(self, "Reprint", str(exc))
            return
        self._load_saved_bill(bill)
        bill_no = bill.get("bill_no", "")
        self._saved_bill_id = bill.get("id")
        if bill_no:
            QGuiApplication.clipboard().setText(bill_no)
        self._set_status(f"Discharge bill loaded for reprint: {bill_no}")
        self._preview_bill()

    def _load_saved_bill(self, bill: dict) -> None:
        self._saved_bill_id = bill.get("id")
        admission = {
            "id": bill.get("admission_id"),
            "patient_id": bill.get("patient_id"),
            "admission_no": bill.get("admission_no"),
            "patient_name": bill.get("patient_name"),
            "patient_no": bill.get("patient_no"),
            "ward_id": bill.get("ward_id"),
            "ward_name": bill.get("ward_name"),
            "bed_no": bill.get("bed_no"),
            "doctor_id": bill.get("doctor_id"),
            "doctor_name": bill.get("doctor_name"),
            "admission_date": bill.get("admission_date"),
            "advance_amount": bill.get("adjust_advance", "0"),
        }
        self._load_admission(admission, from_bill=True)
        self.bill_no.setText(bill.get("bill_no") or "")
        if bill.get("discharge_date"):
            parts = str(bill["discharge_date"]).split("-")
            if len(parts) == 3:
                self.discharge_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self.stay_days.setText(str(bill.get("stay_days", "")))
        self.payment_panel.load_payments(bill.get("payments") or [])
        self.payment_panel.set_net_amount(bill.get("net_amount") or 0)
        self.scheme.setText(bill.get("scheme") or "")
        self._adjust_advance = Decimal(str(bill.get("adjust_advance", "0")))
        self._bill_prior_adjust = self._adjust_advance
        self._sync_adjust_advance_checkbox(
            enabled=self._available_advance() > 0 or self._adjust_advance > 0,
            checked=self._adjust_advance > 0,
        )
        self.hide_advance_chk.setChecked(bool(bill.get("hide_advance_on_bill")))
        self.advance_on_admission.setText(f"{self._available_advance():,.2f}")
        self._bill_lines = [
            {
                "service_id": line.get("service_id"),
                "service_code": line.get("service_code"),
                "service_name": line.get("service_name"),
                "category_name": line.get("category_name"),
                "sub_category_name": line.get("sub_category_name"),
                "rate": float(line.get("rate", 0)),
                "quantity": int(line.get("quantity", 1)),
                "amount": float(line.get("amount", 0)),
                "original_rate": float(line["original_rate"]) if line.get("original_rate") is not None else None,
                "hospital_amount": float(line.get("hospital_amount") or 0),
                "doctor_amount": float(line.get("doctor_amount") or 0),
                "sharing_doctor_id": line.get("sharing_doctor_id"),
                "line_source": line.get("line_source", "manual"),
                "package_id": line.get("package_id"),
            }
            for line in bill.get("lines") or []
        ]
        self._refresh_lines_table()
        self._calculate()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_splitter_sizes()

    def _schedule_splitter_sizes(self) -> None:
        if not self._splitter_sized:
            QTimer.singleShot(0, lambda: self._apply_splitter_sizes(0))

    def _apply_splitter_sizes(self, attempt: int) -> None:
        if self._splitter_sized:
            return
        total = self._splitter.width()
        if total <= 0:
            if attempt < 20:
                QTimer.singleShot(50, lambda: self._apply_splitter_sizes(attempt + 1))
            return
        left_width = max(LEFT_PANE_WIDTH, min(LEFT_PANE_WIDTH + 40, int(total * 0.36)))
        self._splitter.setSizes([left_width, max(total - left_width, 480)])
        self._splitter_sized = True

    def refresh(self) -> None:
        cache = get_session().cache
        self._schedule_splitter_sizes()
        self._load_doctors()
        self._load_wards()
        self._load_beds()
        non_lab_categories = [
            c for c in cache.service_categories if c.get("code") != "LAB"
        ]
        self._load_combo(self.category, non_lab_categories, "— All Categories —")
        modes = list(cache.payment_modes if cache.loaded else [])
        if not modes:
            try:
                modes = self.api.list_payment_modes()
            except ApiError:
                modes = []
        self.payment_panel.set_payment_modes(modes)
        self._load_combo(self.package, cache.billing_packages, "— Select Package —")
        try:
            refresh_patient_services_cache(self.api)
        except ApiError:
            pass
        self._catalog_base = catalog_from_cache(lab_only=False)
        self._on_catalog_filter_changed()
        pending = IpdDischargeWidget.pending_admission
        if pending:
            IpdDischargeWidget.pending_admission = None
            self._clear_form()
            self._load_admission(pending)

    @staticmethod
    def _load_combo(combo: QComboBox, items: list[dict], placeholder: str) -> None:
        combo.clear()
        combo.addItem(placeholder, None)
        for item in items:
            combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _lab_category_id(self) -> str | None:
        cache = get_session().cache
        return next(
            (c.get("id") for c in cache.service_categories if c.get("code") == "LAB"),
            None,
        )

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
        self.category.blockSignals(True)
        self.category.setCurrentIndex(0)
        self.category.blockSignals(False)
        self.catalog_search.clear()
        self._on_catalog_filter_changed()

    def _load_catalog(self) -> None:
        category_id = self.category.currentData()
        try:
            self._catalog_all = load_ipd_catalog_from_api(
                self.api,
                category_id=category_id,
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._apply_catalog_search()

    def _apply_catalog_search(self) -> None:
        self._collect_catalog_rate_edits()
        category_id = self.category.currentData()
        search = self.catalog_search.text().strip()
        if self._catalog_base is not None:
            self._catalog = filter_catalog(
                self._catalog_base,
                category_id=category_id,
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
                chk.setStyleSheet("QCheckBox { margin: 0px; padding: 0px; }")
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
        from app.services.billing_sharing import enrich_service_sharing

        source = self._catalog_base if self._catalog_base is not None else self._catalog_all
        cache_services = get_session().cache.patient_services or []
        lookup: dict[str, dict] = {}
        for item in source:
            service_id = item.get("id")
            if not service_id:
                continue
            enriched = enrich_service_sharing(item, patient_services=cache_services)
            lookup[str(service_id)] = self._service_with_catalog_rate(enriched)
        return lookup

    def _load_admission(self, admission: dict, *, from_bill: bool = False, from_patient_lookup: bool = False) -> None:
        self._admission = admission
        self.patient_id_input.setText(admission.get("patient_no") or "")
        self.patient_name.setText(admission.get("patient_name") or "")
        if admission.get("patient_id"):
            self._patient = {
                "id": admission.get("patient_id"),
                "patient_no": admission.get("patient_no"),
                "first_name": (admission.get("patient_name") or "").split(" ", 1)[0],
            }
        self.admission_no.setText(admission.get("admission_no") or "")
        self._set_ward(admission.get("ward_id"), admission.get("ward_name"))
        self._set_bed(admission.get("bed_no"))
        self._set_doctor(admission.get("doctor_id"))
        self._set_admission_date_from_iso(admission.get("admission_date"))
        self._refresh_deposit_balance()
        if not from_bill:
            self.bill_no.clear()
            self._adjust_advance = Decimal("0")
            self._bill_prior_adjust = Decimal("0")
            self._sync_adjust_advance_checkbox(
                enabled=self._available_advance() > 0,
                checked=False,
            )
            self.discharge_date.setDate(QDate.currentDate())
            self._update_stay_days()
        if admission.get("admission_no"):
            self._set_status(f"Admission loaded: {admission.get('admission_no')}")
        elif from_patient_lookup:
            self._set_status(f"Patient loaded: {admission.get('patient_no') or self.patient_id_input.text().strip()}")
        self._calculate()

    def _update_stay_days(self) -> None:
        qd_adm = self.admission_date.date()
        if not qd_adm.isValid():
            self.stay_days.clear()
            return
        adm = date(qd_adm.year(), qd_adm.month(), qd_adm.day())
        qd = self.discharge_date.date()
        dis = date(qd.year(), qd.month(), qd.day())
        days = max((dis - adm).days + 1, 1)
        self.stay_days.setText(str(days))

    def _add_line_from_service(
        self, service: dict, qty: int = 1, source: str = "manual", package_id: str | None = None
    ) -> None:
        from app.services.billing_sharing import enrich_service_sharing, is_sharing_service

        cache_services = get_session().cache.patient_services or []
        service = enrich_service_sharing(service, patient_services=cache_services)
        service = self._service_with_catalog_rate(service)
        if is_sharing_service(service) and not service.get("doctor_id"):
            try:
                full = self.api.get_patient_service(str(service.get("id")))
                service = enrich_service_sharing({**service, **full}, patient_services=cache_services)
            except ApiError:
                pass
        rate = Decimal(str(service.get("rate", 0)))
        sharing_kwargs = {"patient_services": cache_services}
        for line in self._bill_lines:
            if line.get("service_id") == service.get("id"):
                new_qty = int(line.get("quantity", 1)) + qty
                amounts = build_bill_line_amounts(
                    service,
                    rate=rate,
                    qty=new_qty,
                    parent=self,
                    **sharing_kwargs,
                )
                if amounts is None:
                    return
                line.update(amounts)
                line["line_source"] = line.get("line_source") or source
                self._refresh_lines_table()
                self._calculate()
                return
        amounts = build_bill_line_amounts(
            service,
            rate=rate,
            qty=qty,
            parent=self,
            **sharing_kwargs,
        )
        if amounts is None:
            return
        self._bill_lines.append({
            "service_id": service.get("id"),
            "service_code": service.get("code"),
            "service_name": service.get("name"),
            "category_name": service.get("category_name"),
            "sub_category_name": service.get("sub_category_name"),
            "line_source": source,
            "package_id": package_id,
            **amounts,
        })
        self._refresh_lines_table()
        self._calculate()

    def _add_selected_services(self) -> None:
        self._collect_catalog_rate_edits()
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

    def _apply_package(self) -> None:
        package_id = self.package.currentData()
        if not package_id:
            QMessageBox.information(self, "Package", "Select a package first.")
            return
        try:
            detail = self.api.get_billing_package(package_id)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        items = detail.get("items") or []
        if not items:
            QMessageBox.information(self, "Package", "No services mapped to this package.")
            return
        lookup = self._service_lookup()
        for entry in items:
            service = dict(lookup.get(str(entry.get("service_id"))) or {})
            service.update({
                "id": entry.get("service_id"),
                "code": entry.get("service_code"),
                "name": entry.get("service_name"),
                "category_name": service.get("category_name"),
                "sub_category_name": service.get("sub_category_name"),
                "rate": entry.get("rate_override") or entry.get("service_rate") or 0,
            })
            self._add_line_from_service(
                service,
                qty=int(entry.get("quantity") or 1),
                source="package",
                package_id=package_id,
            )
        self._set_status(f"Package applied: {detail.get('name')} ({len(items)} services)")

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
            for row, line in enumerate(self._bill_lines):
                self.lines_table.setItem(
                    row, 0, self._compact_table_item(line.get("service_code", ""))
                )
                self.lines_table.setItem(
                    row,
                    1,
                    self._compact_table_item(line.get("service_name", ""), editable=True),
                )
                self.lines_table.setItem(
                    row, 2, self._compact_table_item(line.get("category_name") or "")
                )
                self.lines_table.setItem(
                    row, 3, self._compact_table_item(str(line.get("rate", "")), editable=True)
                )
                self.lines_table.setItem(
                    row, 4, self._compact_table_item(str(line.get("quantity", 1)), editable=True)
                )
                self.lines_table.setItem(
                    row, 5, self._compact_table_item(f"{line.get('amount', 0):.2f}")
                )
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
        if column == 1:
            name = item.text().strip()
            if name:
                line["service_name"] = name
                item.setToolTip(name)
        elif column in (3, 4):
            try:
                rate = Decimal(str(line.get("rate", 0)))
                qty = int(line.get("quantity", 1))
                if column == 3:
                    rate = Decimal(item.text().strip() or "0")
                    line["rate"] = float(rate)
                else:
                    qty = max(int(item.text().strip() or "1"), 1)
                    line["quantity"] = qty
                amount = float(rate * qty)
                line["amount"] = amount
                self._lines_table_updating = True
                try:
                    amount_item = self.lines_table.item(row, 5)
                    if amount_item:
                        amount_item.setText(f"{amount:.2f}")
                finally:
                    self._lines_table_updating = False
                self._calculate()
            except (ArithmeticError, ValueError):
                pass

    def _sync_line_edits_from_table(self) -> None:
        self.lines_table.clearFocus()
        for row in range(len(self._bill_lines)):
            line = self._bill_lines[row]
            name_item = self.lines_table.item(row, 1)
            if name_item:
                name = name_item.text().strip()
                if name:
                    line["service_name"] = name
            rate_item = self.lines_table.item(row, 3)
            qty_item = self.lines_table.item(row, 4)
            if rate_item and qty_item:
                try:
                    rate = Decimal(rate_item.text().strip() or "0")
                    qty = max(int(qty_item.text().strip() or "1"), 1)
                    line["rate"] = float(rate)
                    line["quantity"] = qty
                    line["amount"] = float(rate * qty)
                except (ArithmeticError, ValueError):
                    pass

    def _parse_amount(self, field: QLineEdit) -> Decimal:
        text = field.text().strip() or "0"
        return Decimal(text)

    def _calculate(self) -> None:
        gross = sum(Decimal(str(line.get("amount", 0))) for line in self._bill_lines)
        max_adjust = min(self._available_advance(), gross)
        if self.adjust_advance_chk.isChecked():
            if self._adjust_advance <= 0 or self._adjust_advance > max_adjust:
                self._adjust_advance = max_adjust
        else:
            self._adjust_advance = Decimal("0")
        net = gross - self._adjust_advance
        if net < 0:
            net = Decimal("0")
        self.net_amount.setText(f"{net:.2f}")
        self.payment_panel.set_net_amount(net)
        if self._adjust_advance > 0:
            self.advance_adjusted_label.setText(
                f"Advance adjusted: {self._adjust_advance:,.2f}  (net after advance)"
            )
            self.advance_adjusted_label.setVisible(True)
        elif self._available_advance() > 0:
            self.advance_adjusted_label.setText(
                f"Advance available: {self._available_advance():,.2f} — tick Adjust to bill"
            )
            self.advance_adjusted_label.setVisible(True)
        else:
            self.advance_adjusted_label.setText("")
            self.advance_adjusted_label.setVisible(False)

    def _report_endpoint(self) -> str | None:
        if self._saved_bill_id:
            return f"/reports/ipd-bill/{self._saved_bill_id}"
        bill_no = self.bill_no.text().strip()
        if bill_no:
            return f"/reports/ipd-bill/by-no/{bill_no}"
        return None

    def _preview_bill(self) -> None:
        endpoint = self._report_endpoint()
        if endpoint:
            preview_report(self.api, endpoint, parent=self, report_code="IPD_BILL", default_copies=1)

    def _print_bill(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Print", "Save or load a discharge bill first.")
            return
        print_report(self.api, endpoint, parent=self, report_code="IPD_BILL")

    def _save_discharge(self) -> None:
        if self._modification_mode:
            if not self._saved_bill_id:
                QMessageBox.warning(self, "Validation", "Load a bill to modify first.")
                return
        elif not self._patient:
            QMessageBox.warning(self, "Validation", "Enter or find a patient first.")
            return
        if not self._modification_mode and not self.doctor.currentData():
            QMessageBox.warning(self, "Validation", "Select a doctor first.")
            return
        adm_qd = self.admission_date.date()
        dis_qd = self.discharge_date.date()
        if not self._modification_mode and date(dis_qd.year(), dis_qd.month(), dis_qd.day()) < date(
            adm_qd.year(), adm_qd.month(), adm_qd.day()
        ):
            QMessageBox.warning(
                self,
                "Validation",
                "Discharge date cannot be before admission date.",
            )
            return
        if not self._bill_lines:
            QMessageBox.warning(self, "Validation", "Add at least one service line.")
            return
        self._sync_line_edits_from_table()
        self._refresh_deposit_balance()
        gross = sum(Decimal(str(line.get("amount", 0))) for line in self._bill_lines)
        if self._available_advance() > 0 and self._adjust_advance <= 0 and gross > 0:
            QMessageBox.warning(
                self,
                "Advance Adjustment Required",
                "Patient has an advance balance. Tick \"Adjust to bill\" next to "
                "Advance Balance to apply it against this receivable before saving.",
            )
            return
        ok, message = self.payment_panel.validate()
        if not ok:
            QMessageBox.warning(self, "Validation", message)
            return
        qd = self.discharge_date.date()
        discharge_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        payload = {
            "discharge_date": discharge_date,
            "payments": self.payment_panel.get_payments(),
            "scheme": self.scheme.text().strip() or None,
            "admin_charges": "0",
            "scheme_discount": "0",
            "sanctioned_scheme_amount": "0",
            "adjust_advance": str(self._adjust_advance),
            "hide_advance_on_bill": self.hide_advance_chk.isChecked(),
            "ward_id": self.ward.currentData(),
            "bed_no": self._bed_text() or None,
            "lines": [
                {
                    "service_id": line["service_id"],
                    "quantity": line["quantity"],
                    "rate": str(line["rate"]),
                    "service_name": line.get("service_name"),
                    "line_source": line.get("line_source", "manual"),
                    "package_id": line.get("package_id"),
                    **sharing_fields_for_payload(line),
                }
                for line in self._bill_lines
            ],
        }
        if not self._modification_mode:
            payload["patient_id"] = (self._admission or {}).get("patient_id") or self._patient.get("id")
            admission_id = (self._admission or {}).get("id")
            if admission_id:
                payload["admission_id"] = admission_id
            payload["doctor_id"] = self.doctor.currentData()
            payload["admission_date"] = self._admission_date_iso()
        try:
            if self._modification_mode:
                if not self._saved_bill_id:
                    QMessageBox.warning(self, "Validation", "Load a bill to modify first.")
                    return
                bill = self.api.update_ipd_discharge(self._saved_bill_id, payload)
                title = "Updated"
                msg = (
                    f"IPD bill updated successfully.\n\n"
                    f"Bill No: {bill.get('bill_no')}\n"
                    f"Stay Days: {bill.get('stay_days')}\n"
                    f"Net Amount: {bill.get('net_amount')}"
                )
            else:
                bill = self.api.create_ipd_discharge(payload)
                title = "Discharged"
                msg = (
                    f"Patient discharged successfully.\n\n"
                    f"Bill No: {bill.get('bill_no')}\n"
                    f"Stay Days: {bill.get('stay_days')}\n"
                    f"Net Amount: {bill.get('net_amount')}"
                )
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        bill_no = bill.get("bill_no", "")
        self.bill_no.setText(bill_no)
        self._saved_bill_id = bill.get("id")
        if bill_no:
            QGuiApplication.clipboard().setText(bill_no)
        if not self._modification_mode:
            self._admission = None
        self._set_status(
            f"Bill {bill_no} {'updated' if self._modification_mode else 'saved'} — "
            f"stay {bill.get('stay_days')} day(s), net {bill.get('net_amount')} — opening preview."
        )
        QMessageBox.information(self, title, msg)
        self._preview_bill()

    def on_module_deactivated(self) -> None:
        if not self._modification_mode:
            self._clear_form()
            self._refresh_hold_buttons()

    def _capture_hold_state(self) -> dict:
        return {
            "hold_label": hold_label_from_patient(
                self._patient,
                extra=(self.admission_no.text().strip() or "IPD"),
            ),
            "patient": dict(self._patient) if self._patient else None,
            "admission": dict(self._admission) if self._admission else None,
            "bill_lines": [dict(line) for line in self._bill_lines],
            "patient_name": self.patient_name.text(),
            "admission_no": self.admission_no.text(),
            "ward_id": self.ward.currentData(),
            "ward_name": self._ward_label(),
            "bed_no": self._bed_text(),
            "hide_advance_on_bill": self.hide_advance_chk.isChecked(),
            "doctor_id": self.doctor.currentData(),
            "admission_date": date_iso(self.admission_date),
            "discharge_date": date_iso(self.discharge_date),
            "scheme": self.scheme.text(),
            "category_id": self.category.currentData(),
            "package_id": self.package.currentData(),
            "catalog_checked_ids": list(self._catalog_checked_ids),
            "catalog_rate_overrides": dict(self._catalog_rate_overrides),
            "adjust_advance": str(self._adjust_advance),
            "bill_prior_adjust": str(self._bill_prior_adjust),
            "adjust_checked": self.adjust_advance_chk.isChecked(),
            "adjust_enabled": self.adjust_advance_chk.isEnabled(),
            "advance_on_admission": self.advance_on_admission.text(),
            "patient_deposit_balance": str(self._patient_deposit_balance),
            "payments": self.payment_panel.get_payments(),
        }

    def _restore_hold_state(self, state: dict) -> None:
        self._clear_form()
        patient = state.get("patient")
        if patient:
            self._patient = patient
            self.patient_id_input.setText(patient.get("patient_no") or "")
            self.patient_name.setText(state.get("patient_name") or self._format_patient_name(patient))
        admission = state.get("admission")
        self._admission = admission
        self.admission_no.setText(state.get("admission_no") or "")
        self._set_ward(state.get("ward_id"), state.get("ward_name"))
        self._set_bed(state.get("bed_no"))
        self.hide_advance_chk.setChecked(bool(state.get("hide_advance_on_bill")))
        self._set_doctor(state.get("doctor_id"))
        set_date_iso(self.admission_date, state.get("admission_date"))
        set_date_iso(self.discharge_date, state.get("discharge_date"))
        self._update_stay_days()
        self.scheme.setText(state.get("scheme") or "")
        self.advance_on_admission.setText(state.get("advance_on_admission") or "")
        try:
            self._patient_deposit_balance = Decimal(str(state.get("patient_deposit_balance") or "0"))
        except Exception:
            self._patient_deposit_balance = Decimal("0")
        try:
            self._bill_prior_adjust = Decimal(str(state.get("bill_prior_adjust") or "0"))
        except Exception:
            self._bill_prior_adjust = Decimal("0")
        self._sync_adjust_advance_checkbox(
            enabled=bool(state.get("adjust_enabled")),
            checked=bool(state.get("adjust_checked")),
        )
        try:
            self._adjust_advance = Decimal(str(state.get("adjust_advance") or "0"))
        except Exception:
            self._adjust_advance = Decimal("0")
        set_combo_value(self.category, state.get("category_id"))
        set_combo_value(self.package, state.get("package_id"))
        self._catalog_checked_ids = {str(sid) for sid in (state.get("catalog_checked_ids") or [])}
        self._catalog_rate_overrides = dict(state.get("catalog_rate_overrides") or {})
        self._bill_lines = [dict(line) for line in (state.get("bill_lines") or [])]
        self._on_catalog_filter_changed()
        self._refresh_lines_table()
        self._calculate()
        self._apply_hold_payments(state.get("payments"))

    def _clear_form(self) -> None:
        self._patient = None
        self._admission = None
        self._bill_lines = []
        self._saved_bill_id = None
        self.patient_id_input.clear()
        self.patient_name.clear()
        self.admission_no.clear()
        self._set_ward(None)
        self._set_bed(None)
        self.hide_advance_chk.setChecked(False)
        self.doctor.setCurrentIndex(0)
        self.admission_date.setDate(QDate.currentDate())
        self.advance_on_admission.clear()
        self.bill_no.clear()
        self.discharge_date.setDate(QDate.currentDate())
        self.stay_days.clear()
        self.scheme.clear()
        self._adjust_advance = Decimal("0")
        self._bill_prior_adjust = Decimal("0")
        self._patient_deposit_balance = Decimal("0")
        self._sync_adjust_advance_checkbox(enabled=False, checked=False)
        self.net_amount.setText("0.00")
        self.advance_adjusted_label.setText("")
        self.advance_adjusted_label.setVisible(False)
        self.payment_panel.clear_amounts()
        self._refresh_lines_table()
        self._refresh_hold_buttons()
        self._set_status("Ready for new discharge.")

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
