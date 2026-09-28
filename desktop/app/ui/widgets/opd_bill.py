from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.billing_catalog import (
    catalog_from_cache,
    filter_catalog,
    load_opd_catalog_from_api,
)
from app.services.billing_sharing import build_bill_line_amounts, sharing_fields_for_payload
from app.session import get_session
from app.services.master_cache import refresh_doctors_cache, refresh_patient_services_cache
from app.ui.components.multi_payment_panel import MultiPaymentPanel
from app.ui.components.patient_registration_dialog import register_patient_dialog
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.styles import (
    BORDER,
    HEADER_BTN_STYLE,
    INPUT_BG,
    TABLE_COMPACT_STYLE as SERVICE_TABLE_STYLE,
)
from app.ui.bill_hold import (
    BillHoldMixin,
    date_iso,
    hold_label_from_patient,
    set_combo_value,
    set_date_iso,
)
from app.ui.components.date_edit import style_date_field

# Re-export for modules that historically imported these from opd_bill.
__all__ = ("HEADER_BTN_STYLE", "SERVICE_TABLE_STYLE", "OpdBillWidget")

LEFT_PANE_WIDTH = 420
SERVICE_TABLE_ROW_HEIGHT = 26
CATALOG_COL_RATE = 4
CATALOG_CODE_WIDTH = 70
CATALOG_SERVICE_WIDTH = 260
CATALOG_CATEGORY_WIDTH = 90
CATALOG_RATE_WIDTH = 90

# Thin + sharp borders on this screen only (do not change global theme).
_OPD_LINE = BORDER
_OPD_FOCUS = "#2563eb"
LEFT_GROUP_STYLE = f"""
QGroupBox {{
    margin-top: 8px;
    padding: 8px 6px 4px 6px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
"""
FILTER_GROUP_STYLE = f"""
QGroupBox {{
    margin-top: 4px;
    padding: 3px 6px 2px 6px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
"""
LEFT_LABEL_STYLE = "font-size: 12px; padding: 1px 0; margin: 0;"

OPD_HEADER_BTN_STYLE = (
    f"QPushButton {{ font-size: 11px; padding: 4px 10px; border: 1px solid {_OPD_LINE}; "
    f"border-radius: 2px; background: {INPUT_BG}; color: #0f172a; }}"
    f"QPushButton:hover {{ background: #e8ecf3; border-color: #64748b; }}"
)

OPD_TABLE_STYLE = SERVICE_TABLE_STYLE + f"""
QTableWidget {{
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
    gridline-color: #b8c4d4;
}}
QHeaderView::section {{
    border: none;
    border-bottom: 1px solid {_OPD_LINE};
    border-right: 1px solid #b8c4d4;
}}
"""


def _left_field_style() -> str:
    from app.ui.styles import compact_field_style, form_field_style

    # Keep density/sizing from theme; force thin sharp edges for OPD only.
    return (
        form_field_style()
        + compact_field_style()
        + f"""
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {{
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus {{
    border: 1px solid {_OPD_FOCUS};
}}
QLineEdit:read-only {{
    border: 1px solid {_OPD_LINE};
}}
QComboBox::drop-down {{
    border-left: 1px solid {_OPD_LINE};
    border-top-right-radius: 2px;
    border-bottom-right-radius: 2px;
}}
"""
    )

def _left_field_height() -> int:
    from app.ui.styles import left_pane_field_height

    return left_pane_field_height()


def _left_form_spacing() -> int:
    from app.ui.responsive_layout import get_density

    return max(4, get_density().form_v_spacing - 2)


# Resolved when this module is first imported (after theme density is applied).
LEFT_FIELD_STYLE = _left_field_style()
LEFT_FIELD_HEIGHT = _left_field_height()
LEFT_FORM_SPACING = _left_form_spacing()
LEFT_SECTION_SPACING = LEFT_FORM_SPACING


class OpdBillWidget(BillHoldMixin, QWidget):
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
        self._splitter_sized = False
        self._lines_table_updating = False
        self._adjust_advance = Decimal("0")
        self._patient_deposit_balance = Decimal("0")
        self._renewal_history_patient_key: str | None = None
        self._renewal_service_dates: dict[str, dict] = {}
        self._renewal_alerted_keys: set[tuple[str, str, date]] = set()
        self._build_ui()

    @staticmethod
    def _configure_service_table(table: QTableWidget) -> None:
        table.setStyleSheet(OPD_TABLE_STYLE)
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
    def _left_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LEFT_LABEL_STYLE)
        return label

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
        left.setContentsMargins(4, 4, 4, 4)
        left.setSpacing(LEFT_SECTION_SPACING)

        patient_box = QGroupBox("Patient")
        patient_box.setStyleSheet(LEFT_GROUP_STYLE)
        patient_form = QFormLayout(patient_box)
        patient_form.setVerticalSpacing(LEFT_FORM_SPACING)
        patient_form.setHorizontalSpacing(12)
        patient_form.setContentsMargins(6, 8, 6, 4)
        patient_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        patient_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        # Keep ExpandingFieldsGrow — apply_responsive_layout would otherwise
        # force FieldsStayAtSizeHint and leave Patient Name at a short size hint.
        patient_form.setProperty("hmsResponsive", True)
        pid_row = QHBoxLayout()
        pid_row.setSpacing(4)
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Patient No")
        self.patient_id.editingFinished.connect(self._on_patient_id_lookup)
        find_btn = QPushButton("Find")
        find_btn.setFixedHeight(LEFT_FIELD_HEIGHT)
        find_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        find_btn.clicked.connect(self._find_patient)
        pid_row.addWidget(self.patient_id, stretch=1)
        pid_row.addWidget(find_btn)
        patient_form.addRow(self._left_label("Patient Id"), pid_row)
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self.patient_name.setProperty("hmsAllowWide", True)
        self.patient_name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.mobile = QLineEdit()
        self.mobile.setReadOnly(True)
        patient_form.addRow(self._left_label("Patient Name"), self.patient_name)
        patient_form.addRow(self._left_label("Mobile"), self.mobile)
        left.addWidget(patient_box)

        bill_box = QGroupBox("Bill Details")
        bill_box.setStyleSheet(LEFT_GROUP_STYLE)
        self._bill_form = QFormLayout(bill_box)
        bill_form = self._bill_form
        bill_form.setVerticalSpacing(LEFT_FORM_SPACING)
        bill_form.setHorizontalSpacing(12)
        bill_form.setContentsMargins(6, 8, 6, 4)
        bill_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        bill_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.bill_no = QLineEdit()
        self.bill_no.setReadOnly(True)
        self.bill_no.setPlaceholderText("Financial-year series on Save (e.g. OPD202600001)")
        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd/MM/yyyy")
        self.bill_date.setDate(QDate.currentDate())
        self.doctor = QComboBox()
        self.department = QComboBox()
        self.visit_category = QComboBox()
        self.visit_category.addItem("OPD", "opd")
        self.visit_category.addItem("Reference", "reference")
        self.visit_category.addItem("Appointment", "appointment")
        self.visit_category.addItem("Online Booking", "online_booking")
        self.visit_category.currentIndexChanged.connect(self._on_visit_category_changed)
        self.token_session = QComboBox()
        self.token_session.addItem("Morning", "morning")
        self.token_session.addItem("Evening", "evening")
        for combo in (self.doctor, self.department, self.visit_category, self.token_session):
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.setMinimumWidth(120)
        self._default_token_session()
        self.doctor.currentIndexChanged.connect(self._on_doctor_changed)
        self.appointment_date = QDateEdit()
        self.appointment_date.setCalendarPopup(True)
        self.appointment_date.setDisplayFormat("dd/MM/yyyy")
        self.appointment_date.setDate(QDate.currentDate())
        self.token_no = QLineEdit()
        self.token_no.setReadOnly(True)
        self.token_no.setPlaceholderText("Assigned on Save")
        self.scheme = QLineEdit()
        self.scheme.setPlaceholderText("No Scheme")
        bill_form.addRow(self._left_label("Bill No"), self.bill_no)
        date_visit_row = QHBoxLayout()
        date_visit_row.setSpacing(6)
        date_visit_row.addWidget(self.bill_date, stretch=1)
        date_visit_row.addWidget(self.visit_category, stretch=1)
        bill_form.addRow(self._left_label("Date / Visit"), date_visit_row)
        session_token_row = QHBoxLayout()
        session_token_row.setSpacing(6)
        session_token_row.addWidget(self.token_session, stretch=1)
        session_token_row.addWidget(self.token_no, stretch=1)
        bill_form.addRow(self._left_label("Session / Token"), session_token_row)
        self._booking_date_label = self._left_label("Booking Date")
        self._booking_date_row = QWidget()
        booking_row_layout = QHBoxLayout(self._booking_date_row)
        booking_row_layout.setContentsMargins(0, 0, 0, 0)
        booking_row_layout.setSpacing(0)
        booking_row_layout.addWidget(self.appointment_date)
        bill_form.addRow(self._booking_date_label, self._booking_date_row)
        dept_scheme_row = QHBoxLayout()
        dept_scheme_row.setSpacing(6)
        dept_scheme_row.addWidget(self.department, stretch=1)
        dept_scheme_row.addWidget(self.scheme, stretch=1)
        bill_form.addRow(self._left_label("Dept / Scheme"), dept_scheme_row)
        self._on_visit_category_changed()
        left.addWidget(bill_box)

        net_row = QHBoxLayout()
        net_row.setContentsMargins(6, 2, 6, 2)
        net_row.setSpacing(8)
        net_label = QLabel("Net Amount")
        net_label.setStyleSheet("font-weight: bold; color: #334155; font-size: 12px;")
        self.net_amount = QLineEdit("0.00")
        self.net_amount.setReadOnly(True)
        self.net_amount.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.net_amount.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #b91c1c; padding: 2px 6px;"
            f"background: #ffffff; border: 1px solid {_OPD_LINE}; border-radius: 2px;"
        )
        net_row.addWidget(net_label)
        net_row.addWidget(self.net_amount, stretch=1)
        left.addLayout(net_row)

        advance_row = QHBoxLayout()
        advance_row.setContentsMargins(6, 0, 6, 2)
        advance_row.setSpacing(8)
        self.deposit_balance = QLineEdit("0.00")
        self.deposit_balance.setReadOnly(True)
        self.deposit_balance.setFixedHeight(LEFT_FIELD_HEIGHT)
        self.deposit_balance.setStyleSheet(LEFT_FIELD_STYLE)
        adjust_btn = QPushButton("Adjust Advance")
        adjust_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        adjust_btn.clicked.connect(self._enter_advance)
        advance_row.addWidget(self._left_label("Advance Bal"))
        advance_row.addWidget(self.deposit_balance, stretch=1)
        advance_row.addWidget(adjust_btn)
        left.addLayout(advance_row)

        self.payment_panel = MultiPaymentPanel(
            "Payments",
            compact=True,
            group_style=LEFT_GROUP_STYLE
            + f"""
QTableWidget {{
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
}}
QPushButton {{
    border: 1px solid {_OPD_LINE};
    border-radius: 2px;
}}
""",
            field_style=LEFT_FIELD_STYLE,
        )
        left.addWidget(self.payment_panel)
        self._splitter.addWidget(left_scroll)

        right = QVBoxLayout()
        right_host = QWidget()
        right_host.setLayout(right)
        right_host.setMinimumWidth(480)
        self._splitter.addWidget(right_host)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([LEFT_PANE_WIDTH, 900])

        for field in (
            self.patient_id,
            self.patient_name,
            self.mobile,
            self.bill_no,
            self.scheme,
            self.doctor,
            self.department,
            self.visit_category,
            self.token_session,
            self.appointment_date,
            self.token_no,
            self.bill_date,
        ):
            if isinstance(field, QDateEdit):
                style_date_field(
                    field,
                    compact=True,
                    fixed_height=LEFT_FIELD_HEIGHT,
                    min_width=140,
                    extra_style=LEFT_FIELD_STYLE,
                )
                continue
            field.setStyleSheet(LEFT_FIELD_STYLE)
            field.setFixedHeight(LEFT_FIELD_HEIGHT)
            if field is self.patient_name:
                field.setMinimumWidth(300)
                field.setMaximumWidth(16777215)
                field.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
            else:
                field.setMinimumWidth(140)

        doctor_box = QGroupBox("Doctor")
        doctor_box.setStyleSheet(FILTER_GROUP_STYLE)
        doctor_row = QHBoxLayout(doctor_box)
        doctor_row.setContentsMargins(8, 2, 8, 2)
        doctor_row.setSpacing(8)
        doctor_row.addWidget(QLabel("Doctor"))
        doctor_row.addWidget(self.doctor, stretch=1)
        right.addWidget(doctor_box)

        filter_box = QGroupBox("Service Filters")
        filter_box.setStyleSheet(FILTER_GROUP_STYLE)
        filter_row = QHBoxLayout(filter_box)
        filter_row.setContentsMargins(8, 2, 8, 2)
        filter_row.setSpacing(8)
        self.category = QComboBox()
        self.category.setMinimumWidth(140)
        self.category.setStyleSheet(LEFT_FIELD_STYLE)
        self.package = QComboBox()
        self.package.setMinimumWidth(180)
        self.package.setStyleSheet(LEFT_FIELD_STYLE)
        show_btn = QPushButton("Show All")
        show_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        show_btn.clicked.connect(self._show_all_services)
        apply_pkg_btn = QPushButton("Apply Package")
        apply_pkg_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
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
        self.lines_table.setMinimumWidth(520)
        self.lines_table.itemChanged.connect(self._on_line_item_changed)

        catalog_header_row = QHBoxLayout()
        catalog_header_row.setSpacing(8)
        catalog_lbl = QLabel("Available Services")
        catalog_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Search service name or code...")
        self.catalog_search.setMinimumWidth(180)
        self.catalog_search.setClearButtonEnabled(True)
        self.catalog_search.setStyleSheet(LEFT_FIELD_STYLE)
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
        add_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        add_btn.clicked.connect(self._add_selected_services)
        remove_btn = QPushButton("Remove Line")
        remove_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        remove_btn.clicked.connect(self._remove_selected_lines)
        lines_header_row.addWidget(lines_lbl)
        lines_header_row.addStretch()
        lines_header_row.addWidget(add_btn)
        lines_header_row.addWidget(remove_btn)
        right.addLayout(lines_header_row)
        right.addWidget(self.lines_table, stretch=1)

        btn_row = QHBoxLayout()
        save_label = "Update Bill" if self._modification_mode else "Save Bill"
        self.save_btn = QPushButton(save_label)
        self.save_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        self.save_btn.clicked.connect(self._save_bill)
        self.print_bill_btn = QPushButton("Print Bill")
        self.print_bill_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        self.print_bill_btn.clicked.connect(self._print_bill)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(OPD_HEADER_BTN_STYLE)
        clear_btn.clicked.connect(self._clear_bill)
        if self._modification_mode:
            clear_btn.hide()
        exit_hint = QLabel(
            "Bill No uses OPD financial-year series (resets 1 April each year). Preview opens after save."
            if not self._modification_mode
            else "Modify services and payments, then click Update Bill."
        )
        exit_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.print_bill_btn)
        self._setup_bill_hold_buttons(btn_row, style=OPD_HEADER_BTN_STYLE)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(exit_hint)
        right.addLayout(btn_row)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(28)
        outer.addWidget(self.status)

        if self._modification_mode:
            self.patient_id.setReadOnly(True)
            self.bill_date.setEnabled(False)
            self.bill_no.setReadOnly(True)

    def load_bill_for_modification(self, bill: dict) -> None:
        self._load_saved_bill(bill)
        self._set_status(f"Editing bill {bill.get('bill_no', '')} — add/remove services and update payments.")

    def build_header_actions(self) -> QWidget | None:
        if self._modification_mode:
            return None
        from app.ui.header_actions import create_header_action_bar

        return create_header_action_bar(
            [
                ("New Patient", self._open_patient_registration),
                ("Service Creation", lambda: self._navigate("patient_service_creation")),
                ("Tokens", self._show_tokens_dialog),
                ("Reprint Bill", self._reprint_bill),
                ("Casesheet", self._print_casesheet),
                ("Pathology Bill", self._open_pathology_bill_window),
                ("Collect Advance", self._open_advance_collection),
                ("Adjust Advance", self._enter_advance),
                ("IPD Admission", lambda: self._navigate("in_patient_admission")),
                ("IPD Bill", lambda: self._navigate("ipd_bill")),
            ],
            button_style=OPD_HEADER_BTN_STYLE,
        )

    def _default_token_session(self) -> None:
        idx = 0 if datetime.now().hour < 12 else 1
        self.token_session.setCurrentIndex(idx)

    @staticmethod
    def _is_scheduled_visit(visit_category: str | None) -> bool:
        return visit_category in ("appointment", "online_booking")

    def _on_visit_category_changed(self) -> None:
        visit = self.visit_category.currentData()
        is_scheduled = self._is_scheduled_visit(visit)
        if visit == "online_booking":
            self._booking_date_label.setText("Online Booking Date")
        elif visit == "appointment":
            self._booking_date_label.setText("Appointment Date")
        else:
            self._booking_date_label.setText("Booking Date")
        self._booking_date_label.setVisible(is_scheduled)
        self._booking_date_row.setVisible(is_scheduled)

    def _open_advance_collection(self) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut("advance_collection", parent=self, api=self.api, on_navigate=self._on_navigate)

    def _refresh_deposit_balance(self) -> None:
        if not self._patient:
            self._patient_deposit_balance = Decimal("0")
            self.deposit_balance.setText("0.00")
            return
        try:
            data = self.api.get_patient_deposit_balance(
                patient_id=self._patient.get("id"),
                patient_no=self._patient.get("patient_no") or self.patient_id.text().strip() or None,
            )
            self._patient_deposit_balance = Decimal(str(data.get("balance", 0) or 0))
            self.deposit_balance.setText(f"{self._patient_deposit_balance:,.2f}")
        except ApiError as exc:
            self._patient_deposit_balance = Decimal("0")
            self.deposit_balance.setText("0.00")
            self._set_status(f"Advance balance unavailable: {exc}")

    def _enter_advance(self) -> None:
        if not self._patient:
            QMessageBox.warning(self, "Advance", "Load a patient first.")
            return
        self._refresh_deposit_balance()
        from app.ui.components.advance_adjust_dialog import prompt_advance_adjust

        amount = prompt_advance_adjust(
            self,
            available=self._patient_deposit_balance,
            current=self._adjust_advance,
            title="Adjust Advance",
        )
        if amount is None:
            return
        self._adjust_advance = amount
        self._calculate()

    def _navigate(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._on_navigate)

    def _open_patient_registration(self) -> None:
        patient = register_patient_dialog(self.api, self)
        if patient:
            self._apply_patient(patient)

    def _open_pathology_bill_window(self) -> None:
        from app.ui.navigation import make_shortcut_navigator

        from app.ui.widgets.pathology_bill import PathologyBillWidget

        dialog = QDialog(self)
        dialog.setWindowTitle("Pathology Bill")
        dialog.resize(1180, 760)
        layout = QVBoxLayout(dialog)
        widget = PathologyBillWidget(self.api, on_navigate=make_shortcut_navigator(self))
        layout.addWidget(widget)
        widget.refresh()
        if self._patient:
            widget._apply_patient(self._patient)
        dialog.exec()

    def _show_tokens_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("OPD Token Details")
        dialog.resize(820, 480)
        layout = QVBoxLayout(dialog)

        filter_box = QGroupBox("Filters")
        filter_form = QFormLayout(filter_box)
        token_doctor = QComboBox()
        token_doctor.addItem("— All Doctors —", None)
        cache = get_session().cache
        for doc in cache.doctors if cache.loaded else []:
            token_doctor.addItem(f"{doc.get('doctor_code')} — {doc.get('full_name', '')}", doc.get("id"))
        current_doctor = self.doctor.currentData()
        if current_doctor:
            idx = token_doctor.findData(current_doctor)
            if idx >= 0:
                token_doctor.setCurrentIndex(idx)

        token_date = QDateEdit()
        token_date.setCalendarPopup(True)
        token_date.setDisplayFormat("dd/MM/yyyy")
        visit = self.visit_category.currentData()
        if self._is_scheduled_visit(visit):
            token_date.setDate(self.appointment_date.date())
        else:
            token_date.setDate(self.bill_date.date())

        token_session = QComboBox()
        token_session.addItem("— All Sessions —", None)
        token_session.addItem("Morning", "morning")
        token_session.addItem("Evening", "evening")
        session_idx = self.token_session.findData(self.token_session.currentData())
        if session_idx >= 0:
            token_session.setCurrentIndex(session_idx + 1)

        token_visit = QComboBox()
        token_visit.addItem("— All Types —", None)
        token_visit.addItem("OPD", "opd")
        token_visit.addItem("Reference", "reference")
        token_visit.addItem("Appointment", "appointment")
        token_visit.addItem("Online Booking", "online_booking")
        visit_idx = self.visit_category.findData(visit)
        if visit_idx >= 0:
            token_visit.setCurrentIndex(visit_idx + 1)

        filter_form.addRow("Doctor", token_doctor)
        filter_form.addRow("Token Date", token_date)
        filter_form.addRow("Session", token_session)
        filter_form.addRow("Visit Type", token_visit)
        layout.addWidget(filter_box)

        token_table = QTableWidget(0, 7)
        token_table.setHorizontalHeaderLabels(
            ["Token", "Date", "Session", "Type", "Patient", "Patient Id", "Bill No"]
        )
        token_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        token_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        token_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(token_table, stretch=1)

        status_label = QLabel("")
        status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(status_label)

        def _load_tokens() -> None:
            params: dict = {}
            if token_doctor.currentData():
                params["doctor_id"] = token_doctor.currentData()
            qd = token_date.date()
            params["token_date"] = date(qd.year(), qd.month(), qd.day()).isoformat()
            if token_session.currentData():
                params["token_session"] = token_session.currentData()
            if token_visit.currentData():
                params["visit_category"] = token_visit.currentData()
            try:
                items = self.api.list_opd_tokens(**params)
            except ApiError as exc:
                QMessageBox.warning(dialog, "Tokens", str(exc))
                return
            token_table.setRowCount(len(items))
            for row, item in enumerate(items):
                token_table.setItem(row, 0, QTableWidgetItem(str(item.get("token_number", ""))))
                token_table.setItem(row, 1, QTableWidgetItem(str(item.get("token_date", ""))))
                session_label = (item.get("token_session") or "").title()
                token_table.setItem(row, 2, QTableWidgetItem(session_label))
                type_label = (item.get("visit_category") or "").replace("_", " ").upper()
                token_table.setItem(row, 3, QTableWidgetItem(type_label))
                token_table.setItem(row, 4, QTableWidgetItem(item.get("patient_name") or ""))
                token_table.setItem(row, 5, QTableWidgetItem(item.get("patient_no") or ""))
                token_table.setItem(row, 6, QTableWidgetItem(item.get("bill_no") or ""))
            status_label.setText(
                f"{len(items)} token(s) found. Each visit type + session has its own numeric series (1, 2, 3…)."
            )

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(_load_tokens)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        btn_row = QHBoxLayout()
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(buttons)
        layout.addLayout(btn_row)

        _load_tokens()
        dialog.exec()

    def _apply_patient(self, patient: dict) -> None:
        old_key = self._patient_key()
        self._patient = patient
        self.patient_id.setText(patient.get("patient_no", ""))
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self.mobile.setText(patient.get("mobile") or patient.get("phone") or "")
        if self._patient_key() != old_key:
            self._renewal_history_patient_key = None
            self._renewal_service_dates.clear()
            self._renewal_alerted_keys.clear()
        self._refresh_deposit_balance()
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

    def _resolve_patient_for_print(self) -> dict | None:
        patient_no = self.patient_id.text().strip()
        if not patient_no:
            QMessageBox.warning(self, "Casesheet", "Enter a Patient Id first.")
            return None
        return self._load_patient_by_no(patient_no, show_errors=True)

    def _print_casesheet(self) -> None:
        patient = self._resolve_patient_for_print()
        if not patient:
            return
        doctor_id = self.doctor.currentData()
        if not doctor_id:
            QMessageBox.warning(self, "Casesheet", "Select a Doctor first.")
            return
        patient_id = patient.get("id")
        if not patient_id:
            QMessageBox.warning(self, "Casesheet", "Could not resolve patient record.")
            return
        qd = self.bill_date.date()
        case_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        query = urlencode({"doctor_id": doctor_id, "case_date": case_date})
        preview_report(
            self.api,
            f"/reports/opd-casesheet/{patient_id}?{query}",
            parent=self,
            title="OPD Case Sheet",
            report_code="OPD_CASESHEET",
        )

    def _reprint_bill(self) -> None:
        from app.ui.widgets.opd_bill_reprint import OpdBillReprintWidget

        patient_no = self.patient_id.text().strip()
        OpdBillReprintWidget.request_open(patient_no)
        self._navigate("opd_bill_reprint")

    def _load_saved_bill(self, bill: dict) -> None:
        self._saved_bill_id = bill.get("id")
        self._patient = {
            "id": bill.get("patient_id"),
            "patient_no": bill.get("patient_no"),
            "first_name": (bill.get("patient_name") or "").split(" ")[0] if bill.get("patient_name") else "",
            "last_name": "",
        }
        self.patient_id.setText(bill.get("patient_no") or "")
        self.patient_name.setText(bill.get("patient_name") or "")
        self.mobile.clear()
        self.bill_no.setText(bill.get("bill_no") or "")
        if bill.get("bill_date"):
            parts = str(bill["bill_date"]).split("-")
            if len(parts) == 3:
                self.bill_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self.payment_panel.load_payments(bill.get("payments") or [])
        self.payment_panel.set_net_amount(bill.get("net_amount") or 0, auto_fill_cash=False)
        if bill.get("doctor_id"):
            idx = self.doctor.findData(bill["doctor_id"])
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)
        if bill.get("department_id"):
            idx = self.department.findData(bill["department_id"])
            if idx >= 0:
                self.department.setCurrentIndex(idx)
        visit = bill.get("visit_category") or "opd"
        idx = self.visit_category.findData(visit)
        if idx >= 0:
            self.visit_category.setCurrentIndex(idx)
        session = bill.get("token_session")
        if session:
            sidx = self.token_session.findData(session)
            if sidx >= 0:
                self.token_session.setCurrentIndex(sidx)
        if bill.get("appointment_date"):
            parts = str(bill["appointment_date"]).split("-")
            if len(parts) == 3:
                self.appointment_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        token = bill.get("token_number")
        self.token_no.setText(str(token) if token is not None else "")
        self._on_visit_category_changed()
        self.scheme.setText(bill.get("scheme") or "")
        self._adjust_advance = Decimal(str(bill.get("adjust_advance", "0")))
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
        self._load_combo(self.department, cache.departments, "— Select —")
        self._load_combo(self.package, cache.billing_packages, "— Select Package —")

        if not cache.doctors:
            try:
                refresh_doctors_cache(self.api)
            except ApiError:
                pass
        doctors = list(get_session().cache.doctors)
        self.doctor.clear()
        self.doctor.addItem("— Select Doctor —", None)
        for doc in doctors:
            label = f"{doc.get('doctor_code')} — {doc.get('full_name', '')}"
            self.doctor.addItem(label, doc.get("id"))
        self._apply_default_doctor_selection()

        try:
            refresh_patient_services_cache(self.api)
        except ApiError:
            pass
        self._catalog_base = catalog_from_cache(lab_only=False)
        self._on_catalog_filter_changed()

    @staticmethod
    def _load_combo(combo: QComboBox, items: list[dict], placeholder: str) -> None:
        combo.clear()
        combo.addItem(placeholder, None)
        for item in items:
            combo.addItem(f"{item.get('code')} — {item.get('name')}", item.get("id"))

    def _apply_default_doctor_selection(self) -> None:
        if self._modification_mode and self._saved_bill_id:
            return
        if self.doctor.currentData():
            return
        if self.doctor.count() > 1:
            self.doctor.setCurrentIndex(1)

    def _on_doctor_changed(self) -> None:
        doctor_id = self.doctor.currentData()
        if not doctor_id:
            return
        cache = get_session().cache
        doctor = next((doc for doc in cache.doctors if doc.get("id") == doctor_id), None)
        if not doctor:
            return
        department_id = doctor.get("department_id")
        if not department_id:
            return
        idx = self.department.findData(department_id)
        if idx >= 0:
            self.department.setCurrentIndex(idx)

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
            self._catalog_all = load_opd_catalog_from_api(
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

    def _find_patient(self) -> None:
        patient = pick_patient(self.api, self, initial_patient_no=self.patient_id.text().strip())
        if not patient:
            return
        self._apply_patient(patient)

    def _patient_key(self) -> str | None:
        if not self._patient:
            return None
        return self._patient.get("id") or self._patient.get("patient_no")

    @staticmethod
    def _parse_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _current_bill_date(self) -> date:
        qd = self.bill_date.date()
        return date(qd.year(), qd.month(), qd.day())

    def _load_renewal_history(self) -> None:
        patient_key = self._patient_key()
        if not patient_key or patient_key == self._renewal_history_patient_key:
            return
        self._renewal_service_dates.clear()
        if not self._patient:
            return
        try:
            summaries = self.api.list_opd_bills_by_patient(
                patient_id=self._patient.get("id"),
                patient_no=self._patient.get("patient_no"),
            )
        except ApiError as exc:
            self._set_status(f"Could not check renewal history: {exc}")
            return
        self._renewal_history_patient_key = patient_key
        for summary in summaries:
            bill_id = summary.get("id")
            if not bill_id:
                continue
            try:
                bill = self.api.get_opd_bill(bill_id)
            except ApiError:
                continue
            billed_on = self._parse_date(bill.get("bill_date") or summary.get("bill_date"))
            if not billed_on:
                continue
            for line in bill.get("lines") or []:
                service_id = line.get("service_id")
                if not service_id:
                    continue
                key = str(service_id)
                previous = self._renewal_service_dates.get(key)
                if not previous or billed_on > previous["bill_date"]:
                    self._renewal_service_dates[key] = {
                        "bill_date": billed_on,
                        "bill_no": bill.get("bill_no") or summary.get("bill_no"),
                    }

    def _warn_if_service_expired(self, service: dict) -> None:
        if self._modification_mode or not self._patient or not service.get("is_renewal"):
            return
        service_id = service.get("id")
        if not service_id:
            return
        try:
            renewal_days = int(service.get("renewal_days") or 0)
        except (TypeError, ValueError):
            return
        self._load_renewal_history()
        last = self._renewal_service_dates.get(str(service_id))
        if not last:
            return
        bill_date = self._current_bill_date()
        expiry_date = last["bill_date"] + timedelta(days=renewal_days)
        if bill_date <= expiry_date:
            return
        alert_key = (str(self._patient_key() or ""), str(service_id), bill_date)
        if alert_key in self._renewal_alerted_keys:
            return
        self._renewal_alerted_keys.add(alert_key)
        QMessageBox.warning(
            self,
            "Service Expired",
            f"{service.get('name') or 'This service'} was last billed on "
            f"{last['bill_date'].strftime('%d/%m/%Y')} and expired on "
            f"{expiry_date.strftime('%d/%m/%Y')}.\n\n"
            "Please renew/check before billing again.",
        )

    def _add_line_from_service(self, service: dict, qty: int = 1, source: str = "manual", package_id: str | None = None) -> None:
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
        self._warn_if_service_expired(service)
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
        net = gross - self._adjust_advance
        if net < 0:
            net = Decimal("0")
        self.net_amount.setText(f"{net:.2f}")
        self.payment_panel.set_net_amount(net)

    def _report_endpoint(self) -> str | None:
        if self._saved_bill_id:
            return f"/reports/opd-bill/{self._saved_bill_id}"
        bill_no = self.bill_no.text().strip()
        if bill_no:
            return f"/reports/opd-bill/by-no/{bill_no}"
        return None

    def _preview_bill(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Preview", "Save or load a bill first.")
            return
        preview_report(self.api, endpoint, parent=self, report_code="OPD_BILL")

    def _print_bill(self) -> None:
        endpoint = self._report_endpoint()
        if not endpoint:
            QMessageBox.information(self, "Print", "Save or load a bill first.")
            return
        print_report(self.api, endpoint, parent=self, report_code="OPD_BILL")

    def _save_bill(self) -> None:
        if not self._patient:
            QMessageBox.warning(self, "Validation", "Find and load a patient first.")
            return
        if not self._bill_lines:
            QMessageBox.warning(self, "Validation", "Add at least one service line.")
            return
        self._sync_line_edits_from_table()
        doctor_id = self.doctor.currentData()
        visit_category = self.visit_category.currentData() or "opd"
        if not doctor_id:
            QMessageBox.warning(self, "Validation", "Select a doctor. Doctor is required for OPD bills.")
            return
        if not self.token_session.currentData():
            QMessageBox.warning(self, "Validation", "Select morning or evening session for token.")
            return
        if self._is_scheduled_visit(visit_category):
            aq = self.appointment_date.date()
            if not aq.isValid():
                QMessageBox.warning(self, "Validation", "Select booking date for appointment / online booking.")
                return
        ok, message = self.payment_panel.validate()
        if not ok:
            QMessageBox.warning(self, "Validation", message)
            return
        qd = self.bill_date.date()
        bill_date = date(qd.year(), qd.month(), qd.day()).isoformat()
        payload = {
            "doctor_id": doctor_id,
            "department_id": self.department.currentData(),
            "token_session": self.token_session.currentData(),
            "payments": self.payment_panel.get_payments(),
            "scheme": self.scheme.text().strip() or None,
            "admin_charges": "0",
            "scheme_discount": "0",
            "sanctioned_scheme_amount": "0",
            "adjust_advance": str(self._adjust_advance),
            "visit_category": visit_category,
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
            payload["patient_id"] = self._patient.get("id")
            payload["bill_date"] = bill_date
        if self._is_scheduled_visit(visit_category):
            aq = self.appointment_date.date()
            payload["appointment_date"] = date(aq.year(), aq.month(), aq.day()).isoformat()
        try:
            if self._modification_mode:
                if not self._saved_bill_id:
                    QMessageBox.warning(self, "Validation", "Load a bill to modify first.")
                    return
                bill = self.api.update_opd_bill(self._saved_bill_id, payload)
                action = "updated"
            else:
                bill = self.api.create_opd_bill(payload)
                action = "saved"
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        bill_no = (bill.get("bill_no") or "").strip()
        patient_no = (bill.get("patient_no") or self.patient_id.text().strip() or "").strip()
        saved_bill_id = bill.get("id")
        if not bill_no:
            QMessageBox.warning(
                self,
                "Saved",
                "Bill saved but bill number was not returned. Check Reprint Bill or contact support.",
            )
            return
        token = bill.get("token_number")
        token_msg = f" Token: {token}" if token is not None else ""
        patient_msg = f" Patient: {patient_no}" if patient_no else ""
        preview_endpoint = f"/reports/opd-bill/{saved_bill_id}" if saved_bill_id else None
        if preview_endpoint:
            preview_report(
                self.api,
                preview_endpoint,
                parent=self,
                title="OPD Bill Preview",
                report_code="OPD_BILL",
                default_copies=1,
            )
        if bill_no:
            QGuiApplication.clipboard().setText(bill_no)
        title = "Updated" if self._modification_mode else "Saved"
        QMessageBox.information(
            self,
            title,
            f"OPD Bill No: {bill_no}\nPatient Id: {patient_no or '—'}{token_msg}\n\n"
            "Preview opened. Select copies and print from the preview window.",
        )
        if not self._modification_mode:
            self._clear_bill()
            self._set_status(f"Bill {action}: {bill_no}{patient_msg}{token_msg} — ready for new bill.")
        else:
            self.bill_no.setText(bill_no)
            self._saved_bill_id = saved_bill_id
            self.token_no.setText(str(token) if token is not None else "")
            if bill_no:
                QGuiApplication.clipboard().setText(bill_no)
            self._set_status(f"Bill {action}: {bill_no}{patient_msg}{token_msg}")

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
            "appointment_date": date_iso(self.appointment_date),
            "visit_category": self.visit_category.currentData(),
            "token_session": self.token_session.currentData(),
            "doctor_id": self.doctor.currentData(),
            "department_id": self.department.currentData(),
            "scheme": self.scheme.text(),
            "category_id": self.category.currentData(),
            "package_id": self.package.currentData(),
            "catalog_checked_ids": list(self._catalog_checked_ids),
            "catalog_rate_overrides": dict(self._catalog_rate_overrides),
            "adjust_advance": str(self._adjust_advance),
            "payments": self.payment_panel.get_payments(),
            "renewal_history_patient_key": self._renewal_history_patient_key,
            "renewal_service_dates": dict(self._renewal_service_dates),
            "renewal_alerted_keys": list(self._renewal_alerted_keys),
        }

    def _restore_hold_state(self, state: dict) -> None:
        self._clear_bill()
        patient = state.get("patient")
        if patient:
            self._apply_patient(patient)
        set_combo_value(self.visit_category, state.get("visit_category"))
        set_combo_value(self.token_session, state.get("token_session"))
        set_combo_value(self.doctor, state.get("doctor_id"))
        set_combo_value(self.department, state.get("department_id"))
        self.scheme.setText(state.get("scheme") or "")
        set_date_iso(self.bill_date, state.get("bill_date"))
        set_date_iso(self.appointment_date, state.get("appointment_date"))
        set_combo_value(self.category, state.get("category_id"))
        set_combo_value(self.package, state.get("package_id"))
        self._catalog_checked_ids = {str(sid) for sid in (state.get("catalog_checked_ids") or [])}
        self._catalog_rate_overrides = dict(state.get("catalog_rate_overrides") or {})
        self._bill_lines = [dict(line) for line in (state.get("bill_lines") or [])]
        try:
            self._adjust_advance = Decimal(str(state.get("adjust_advance") or "0"))
        except Exception:
            self._adjust_advance = Decimal("0")
        self._renewal_history_patient_key = state.get("renewal_history_patient_key")
        self._renewal_service_dates = dict(state.get("renewal_service_dates") or {})
        self._renewal_alerted_keys = {
            tuple(item) if isinstance(item, (list, tuple)) else item
            for item in (state.get("renewal_alerted_keys") or [])
        }
        self._on_catalog_filter_changed()
        self._refresh_lines_table()
        self._calculate()
        self._apply_hold_payments(state.get("payments"))

    def _clear_bill(self) -> None:
        self._patient = None
        self._bill_lines = []
        self._saved_bill_id = None
        self._renewal_history_patient_key = None
        self._renewal_service_dates.clear()
        self._renewal_alerted_keys.clear()
        self.patient_id.clear()
        self.patient_name.clear()
        self.mobile.clear()
        self.bill_no.clear()
        self.token_no.clear()
        self.bill_date.setDate(QDate.currentDate())
        self.visit_category.setCurrentIndex(0)
        self._default_token_session()
        self.appointment_date.setDate(QDate.currentDate())
        self._on_visit_category_changed()
        self.doctor.setCurrentIndex(0)
        self.department.setCurrentIndex(0)
        self.scheme.clear()
        self.category.setCurrentIndex(0)
        self.package.setCurrentIndex(0)
        self._catalog_checked_ids.clear()
        self._catalog_rate_overrides.clear()
        self._on_catalog_filter_changed()
        self.catalog_search.clear()
        self._adjust_advance = Decimal("0")
        self._patient_deposit_balance = Decimal("0")
        self.deposit_balance.setText("0.00")
        self.net_amount.setText("0.00")
        self.payment_panel.clear_amounts()
        self.payment_panel.set_net_amount(Decimal("0"), auto_fill_cash=False)
        self._refresh_lines_table()
        self._on_catalog_filter_changed()
        self._refresh_hold_buttons()
        self._set_status("Ready for new bill.")

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
