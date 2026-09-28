from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_doctors_cache
from app.session import get_session
from app.ui.components.medicine_incremental_search import MedicineIncrementalSearch
from app.ui.components.medicine_quantity_dialog import ask_medicine_quantity
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report, print_report
from app.ui.styles import BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY, FORM_FIELD_STYLE

# GenERP-inspired palette for sale bill (teal accent, clean white surfaces)
ACCENT = "#0F6E63"
ACCENT_DARK = "#0A4F47"
ACCENT_SOFT = "#E7F3F1"
SURFACE_MUTED = "#F6F7F9"
BORDER = "#E5E8EC"
BORDER_STRONG = "#CFD5DD"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#667085"
TEXT_TERTIARY = "#9AA4B2"
DANGER = "#D0342C"
DANGER_SOFT = "#FBEAE9"

LINE_COLUMNS = [
    "#",
    "Code",
    "Product",
    "Nos",
    "Batch",
    "Factor",
    "Exp",
    "Qty",
    "Rate",
    "Tax%",
    "Tax",
    "Total",
    "Disc%",
    "Disc",
    "Net",
]
COL_IDX = 0
COL_CODE = 1
COL_NAME = 2
COL_NOS = 3
COL_BATCH = 4
COL_FACTOR = 5
COL_EXPDT = 6
COL_QTY = 7
COL_RATE = 8
COL_TAXPER = 9
COL_TAX = 10
COL_TOT = 11
COL_DISPER = 12
COL_DISAMNT = 13
COL_NET = 14

EDITABLE_COLS = {
    COL_NOS,
    COL_BATCH,
    COL_FACTOR,
    COL_EXPDT,
    COL_QTY,
    COL_RATE,
    COL_TAXPER,
    COL_DISPER,
}
READONLY_COLS = {COL_IDX, COL_CODE, COL_NAME, COL_TAX, COL_TOT, COL_DISAMNT, COL_NET}
READONLY_BG = QColor("#f1f5f9")

TABLE_STYLE = f"""
QTableWidget {{
    background: #ffffff;
    color: {TEXT_PRIMARY};
    gridline-color: {BORDER};
    font-size: 12px;
    border: none;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT_PRIMARY};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QHeaderView::section {{
    background: {SURFACE_MUTED};
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
}}
"""


def _style_btn(btn: QPushButton, css: str, *, min_height: int = 34) -> QPushButton:
    btn.setStyleSheet(css)
    btn.setMinimumHeight(min_height)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _field_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setStyleSheet(
        f"font-size: 10px; font-weight: 700; color: {TEXT_TERTIARY};"
        " letter-spacing: 0.6px; margin-bottom: 2px;"
    )
    return label


def _section_label(text: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 4, 0, 8)
    layout.setSpacing(8)
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"font-size: 10px; font-weight: 700; color: {TEXT_TERTIARY}; letter-spacing: 1px;"
    )
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
    layout.addWidget(lbl)
    layout.addWidget(line, stretch=1)
    return row


class PharmacySaleBillWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        self._on_navigate = on_navigate
        self._patient: dict | None = None
        self._catalog_by_code: dict[str, dict] = {}
        self._catalog_all: list[dict] = []
        self._item_ids: dict[int, str] = {}
        self._saved_bill_id: str | None = None
        self._selected_row: int | None = None
        self._pending_medicine: dict | None = None
        self._updating = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")
        page = QWidget()
        page.setStyleSheet(f"background: #ffffff; color: {TEXT_PRIMARY};")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(20, 16, 20, 32)
        page_layout.setSpacing(14)

        page_layout.addWidget(self._build_topbar())
        page_layout.addWidget(self._build_meta_strip())
        page_layout.addWidget(self._build_primary_card())
        page_layout.addWidget(self._build_items_card())
        page_layout.addWidget(self._build_payment_card())
        page_layout.addLayout(self._build_actions_row())
        page_layout.addWidget(self._build_recent_bills())
        page_layout.addStretch()

        scroll.setWidget(page)
        outer.addWidget(scroll)

        self.lines_table.cellChanged.connect(self._on_cell_changed)
        self.bill_discount.textChanged.connect(self._recalc_footer_totals)
        self.round_off.textChanged.connect(self._recalc_footer_totals)
        self.cash_credit.currentIndexChanged.connect(self._recalc_footer_totals)
        self.customer_name.textChanged.connect(self._update_customer_avatar)

        QShortcut(QKeySequence("F9"), self, self._save)
        QShortcut(QKeySequence("F5"), self, self._clear_form)
        QShortcut(QKeySequence("F2"), self, self._find_patient)
        QShortcut(QKeySequence("F3"), self, lambda: self.med_search._browse_all())

        for widget in self.findChildren((QLineEdit, QComboBox, QDateEdit)):
            if not widget.property("hmsSkipFormStyle"):
                extra = widget.styleSheet().strip()
                widget.setStyleSheet(f"{FORM_FIELD_STYLE}\n{extra}" if extra else FORM_FIELD_STYLE)

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 12)

        left = QVBoxLayout()
        left.setSpacing(2)
        session = get_session()
        hospital = (
            (session.cache.hospital_profile or {}).get("hospital_name")
            or "Medical Shop"
        )
        eyebrow = QLabel(hospital.upper())
        eyebrow.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {ACCENT}; letter-spacing: 1.4px;"
        )
        title = QLabel("Sale Bill")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setWeight(QFont.Weight.ExtraBold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; margin: 0;")
        left.addWidget(eyebrow)
        left.addWidget(title)
        layout.addLayout(left)
        layout.addStretch()

        self.bill_no_chip = QLabel("Bill No: —")
        self.bill_no_chip.setStyleSheet(
            f"background: {TEXT_PRIMARY}; color: #ffffff; padding: 8px 14px;"
            f" border-radius: 7px; font-family: Consolas, monospace; font-weight: 700; font-size: 13px;"
        )
        layout.addWidget(self.bill_no_chip)

        user_block = QHBoxLayout()
        user_block.setSpacing(8)
        self.user_avatar = QLabel("U")
        self.user_avatar.setFixedSize(36, 36)
        self.user_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_avatar.setStyleSheet(
            f"background: {ACCENT}; color: white; border-radius: 18px;"
            " font-weight: 700; font-size: 12px;"
        )
        user_col = QVBoxLayout()
        user_col.setSpacing(0)
        user_name = QLabel(session.full_name or "User")
        user_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_PRIMARY};")
        user_email = QLabel(session.email or "")
        user_email.setStyleSheet(f"font-size: 11px; color: {TEXT_TERTIARY};")
        user_col.addWidget(user_name)
        user_col.addWidget(user_email)
        user_block.addWidget(self.user_avatar)
        user_block.addLayout(user_col)
        layout.addLayout(user_block)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background: {TEXT_PRIMARY}; max-height: 2px;")
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(bar)
        wrap.addWidget(divider)
        host = QWidget()
        host.setLayout(wrap)
        return host

    def _build_meta_strip(self) -> QFrame:
        strip = QFrame()
        strip.setStyleSheet(
            f"QFrame {{ background: {SURFACE_MUTED}; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        grid = QGridLayout(strip)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        self.bill_date = QDateEdit()
        self.bill_date.setCalendarPopup(True)
        self.bill_date.setDisplayFormat("dd-MM-yyyy")
        self.bill_date.setDate(QDate.currentDate())

        self.last_bill_no = QLineEdit()
        self.last_bill_no.setReadOnly(True)
        self.last_bill_no.setProperty("hmsSkipFormStyle", True)
        self.last_bill_no.setStyleSheet(
            f"border: none; background: transparent; color: {TEXT_SECONDARY};"
            " font-weight: 600; font-family: Consolas, monospace; padding: 6px 0;"
        )

        self.remarks = QLineEdit()
        self.remarks.setPlaceholderText("Optional note")

        self.bill_discount = QLineEdit("0.00")
        self.bill_discount.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.cash_credit = QComboBox()
        self.cash_credit.addItems(["Cash", "Credit"])

        self.doctor = QComboBox()
        self.doctor.setEditable(True)

        self.scheme = QComboBox()
        self.scheme.setEditable(True)
        self.scheme.addItems(["NORMAL BILL", "INSURANCE", "STAFF", "VIP"])

        self.bill_no = QLineEdit("0")
        self.bill_no.hide()

        fields = [
            ("Date", self.bill_date),
            ("Last Bill", self.last_bill_no),
            ("Narration", self.remarks),
            ("Bill Discount", self.bill_discount),
            ("Cash / Credit", self.cash_credit),
            ("Doctor", self.doctor),
            ("Scheme", self.scheme),
        ]
        for index, (label_text, widget) in enumerate(fields):
            col = (index % 4) * 2
            row = index // 4
            cell = QVBoxLayout()
            cell.setSpacing(4)
            cell.addWidget(_field_label(label_text))
            cell.addWidget(widget)
            grid.addLayout(cell, row, col, 1, 2)

        return strip

    def _build_primary_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #ffffff; border: 1px solid {BORDER};"
            f" border-left: 4px solid {ACCENT}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        customer_row = QHBoxLayout()
        customer_row.setSpacing(12)
        self.cust_avatar = QLabel("W")
        self.cust_avatar.setFixedSize(44, 44)
        self.cust_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cust_avatar.setStyleSheet(
            f"background: {ACCENT_SOFT}; color: {ACCENT_DARK}; border-radius: 10px;"
            " font-weight: 800; font-size: 15px;"
        )
        customer_row.addWidget(self.cust_avatar)

        cust_fields = QHBoxLayout()
        cust_main = QVBoxLayout()
        cust_main.setSpacing(4)
        cust_main.addWidget(_field_label("Customer"))
        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Walk-in (type name or Find patient)")
        self.customer_name.setMinimumHeight(36)
        cust_main.addWidget(self.customer_name)
        cust_fields.addLayout(cust_main, stretch=3)

        find_btn = _style_btn(
            QPushButton("+ Find Patient"),
            f"QPushButton {{ border: 1px solid {ACCENT}; color: {ACCENT_DARK}; background: #fff;"
            f" border-radius: 7px; padding: 8px 12px; font-weight: 700; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT_SOFT}; }}",
            min_height=36,
        )
        find_btn.clicked.connect(self._find_patient)
        cust_fields.addWidget(find_btn)
        customer_row.addLayout(cust_fields, stretch=1)

        outstanding = QVBoxLayout()
        outstanding.setAlignment(Qt.AlignmentFlag.AlignRight)
        outstanding.addWidget(_field_label("Outstanding"))
        self.outstanding_val = QLabel("— 0.00")
        self.outstanding_val.setStyleSheet(
            f"font-family: Consolas, monospace; font-weight: 700; font-size: 15px;"
            f" color: {TEXT_SECONDARY};"
        )
        outstanding.addWidget(self.outstanding_val)
        customer_row.addLayout(outstanding)
        layout.addLayout(customer_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            f"background: transparent; border: none; border-top: 1px dashed {BORDER};"
        )
        layout.addWidget(sep)

        layout.addWidget(
            _section_label("Add Item — search medicine, Enter to pick, Enter again to add")
        )

        self.med_search = MedicineIncrementalSearch(
            self.api,
            self._on_medicine_selected,
            self,
            local_catalog=lambda: self._catalog_all,
        )
        self.med_search.status.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: 10px;")
        layout.addWidget(self.med_search)

        add_grid = QGridLayout()
        add_grid.setHorizontalSpacing(10)
        add_grid.setVerticalSpacing(4)

        self.f_qty = QLineEdit("1")
        self.f_rate = QLineEdit("0.00")
        self.f_rate.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_disc = QLineEdit("0.00")
        self.f_disc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_gst = QLineEdit("0.00")
        self.f_gst.setAlignment(Qt.AlignmentFlag.AlignRight)

        for col, (label_text, widget) in enumerate(
            [
                ("Qty", self.f_qty),
                ("Rate", self.f_rate),
                ("Disc %", self.f_disc),
                ("GST %", self.f_gst),
            ],
            start=0,
        ):
            cell = QVBoxLayout()
            cell.addWidget(_field_label(label_text))
            cell.addWidget(widget)
            add_grid.addLayout(cell, 0, col)

        add_btn = _style_btn(
            QPushButton("Add"),
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none; border-radius: 7px;"
            " padding: 8px 16px; font-weight: 700; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {ACCENT_DARK}; }}",
            min_height=36,
        )
        add_btn.clicked.connect(self._add_item_from_form)
        add_cell = QVBoxLayout()
        add_cell.addWidget(QLabel(""))
        add_cell.addWidget(add_btn)
        add_grid.addLayout(add_cell, 0, 4)
        layout.addLayout(add_grid)

        stock_row = QHBoxLayout()
        stock_row.addWidget(_field_label("Stock"))
        self.stock_label = QLabel("—")
        self.stock_label.setStyleSheet(
            f"font-family: Consolas, monospace; color: {TEXT_SECONDARY}; font-size: 12px;"
        )
        stock_row.addWidget(self.stock_label)
        stock_row.addStretch()
        layout.addLayout(stock_row)

        self.address1 = QLineEdit()
        self.address2 = QLineEdit()
        self.address3 = QLineEdit()
        for field in (self.address1, self.address2, self.address3):
            field.hide()

        return card

    def _build_items_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.lines_table = QTableWidget(8, len(LINE_COLUMNS))
        self.lines_table.setHorizontalHeaderLabels(LINE_COLUMNS)
        self.lines_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.lines_table.horizontalHeader().setStretchLastSection(True)
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.setStyleSheet(TABLE_STYLE)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lines_table.setMinimumHeight(220)
        self._ensure_blank_rows()
        layout.addWidget(self.lines_table)

        totals = QFrame()
        totals.setStyleSheet(f"background: {SURFACE_MUTED}; border-top: 1px solid {BORDER};")
        totals_layout = QHBoxLayout(totals)
        totals_layout.setContentsMargins(14, 10, 14, 10)
        totals_layout.addStretch()

        self.gross_val = self._total_item("Gross", "0.00")
        self.tax_val = self._total_item("Tax", "0.00")
        self.net_val = self._total_item("Net", "0.00", accent=True)
        totals_layout.addWidget(self.gross_val["wrap"])
        totals_layout.addSpacing(24)
        totals_layout.addWidget(self.tax_val["wrap"])
        totals_layout.addSpacing(24)
        totals_layout.addWidget(self.net_val["wrap"])
        layout.addWidget(totals)

        remove_row = QFrame()
        remove_row.setStyleSheet(f"border-top: 1px solid {BORDER}; background: #fff;")
        remove_layout = QHBoxLayout(remove_row)
        remove_layout.setContentsMargins(12, 8, 12, 8)
        remove_btn = _style_btn(
            QPushButton("Remove Selected Item"),
            BTN_DANGER,
            min_height=30,
        )
        remove_btn.clicked.connect(self._remove_selected)
        remove_layout.addWidget(remove_btn)
        remove_layout.addStretch()
        layout.addWidget(remove_row)

        self.round_off = QLineEdit("0.00")
        self.round_off.hide()
        return card

    def _total_item(self, label: str, value: str, *, accent: bool = False) -> dict:
        wrap = QWidget()
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setAlignment(Qt.AlignmentFlag.AlignRight)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {TEXT_TERTIARY}; letter-spacing: 0.5px;"
        )
        val = QLabel(value)
        color = ACCENT_DARK if accent else TEXT_PRIMARY
        size = "18px" if accent else "14px"
        val.setStyleSheet(
            f"font-family: Consolas, monospace; font-weight: 700; font-size: {size}; color: {color};"
        )
        col.addWidget(lbl)
        col.addWidget(val)
        return {"wrap": wrap, "value": val}

    def _build_payment_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_label("Payment"))

        entry = QHBoxLayout()
        entry.setSpacing(10)
        self.payment_mode = QComboBox()
        self.pay_amount = QLineEdit()
        self.pay_amount.setPlaceholderText("0.00")
        self.pay_amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pay_amount.setReadOnly(True)
        entry.addWidget(self.payment_mode, stretch=2)
        entry.addWidget(self.pay_amount, stretch=1)
        layout.addLayout(entry)

        summary = QHBoxLayout()
        summary.addStretch()

        paid_block = QVBoxLayout()
        paid_block.setAlignment(Qt.AlignmentFlag.AlignRight)
        paid_title = QLabel("PAID")
        paid_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {TEXT_TERTIARY};"
        )
        self.paid_val = QLabel("0.00")
        self.paid_val.setStyleSheet(
            "font-family: Consolas, monospace; font-weight: 700; font-size: 14px;"
        )
        paid_block.addWidget(paid_title)
        paid_block.addWidget(self.paid_val)
        summary.addLayout(paid_block)
        summary.addSpacing(28)

        balance_block = QVBoxLayout()
        balance_block.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.balance_lbl = QLabel("BALANCE (CREDIT)")
        self.balance_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {TEXT_TERTIARY};"
        )
        self.balance_val = QLabel("0.00")
        self.balance_val.setStyleSheet(
            f"font-family: Consolas, monospace; font-weight: 700; font-size: 14px; color: {ACCENT_DARK};"
        )
        balance_block.addWidget(self.balance_lbl)
        balance_block.addWidget(self.balance_val)
        summary.addLayout(balance_block)
        layout.addLayout(summary)
        return card

    def _build_actions_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        save_btn = _style_btn(QPushButton("Save Bill"), BTN_PRIMARY, min_height=42)
        save_btn.clicked.connect(self._save)
        clear_btn = _style_btn(QPushButton("Clear"), BTN_SECONDARY, min_height=42)
        clear_btn.clicked.connect(self._clear_form)
        print_btn = _style_btn(QPushButton("Print Bill"), BTN_SECONDARY, min_height=42)
        print_btn.clicked.connect(self._print_bill)
        row.addWidget(save_btn)
        row.addWidget(clear_btn)
        row.addWidget(print_btn)
        row.addStretch()
        return row

    def _build_recent_bills(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(_section_label("Recent Bills"))
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(0)
        layout.addLayout(self.recent_list)
        return host

    def _update_customer_avatar(self) -> None:
        value = self.customer_name.text().strip()
        self.cust_avatar.setText(value[:1].upper() if value else "W")

    def _on_medicine_selected(self, medicine: dict) -> None:
        self._pending_medicine = medicine
        code = medicine.get("code", "")
        name = medicine.get("name", "")
        rate = medicine.get("sale_rate") or medicine.get("mrp") or medicine.get("rate") or 0
        self.med_search.search_box.setText(f"{code} — {name}")
        self.f_rate.setText(f"{float(rate):.2f}")
        self.f_qty.setFocus()
        self.f_qty.selectAll()
        stock_qty = medicine.get("stock_qty")
        if stock_qty is None:
            try:
                lookup = self.api.pharmacy_stock_lookup(code)
                self._show_stock(lookup)
            except ApiError:
                self.stock_label.setText("—")
        else:
            self._show_stock(
                {
                    "item_code": code,
                    "stock_qty": stock_qty,
                    "rate": rate,
                }
            )

    def _add_item_from_form(self) -> None:
        if not self._pending_medicine:
            self.med_search.focus_search()
            return
        qty_info = ask_medicine_quantity(self._pending_medicine, self)
        if not qty_info:
            return
        row = self._first_empty_row()
        self._apply_medicine_row(
            row,
            self._pending_medicine,
            nos=qty_info["nos"],
            factor=qty_info["factor"],
            qty=qty_info["qty"],
        )
        disc = self._dec(self.f_disc.text())
        gst = self._dec(self.f_gst.text())
        self._updating = True
        try:
            self.lines_table.item(row, COL_DISPER).setText(f"{disc:.2f}")
            self.lines_table.item(row, COL_TAXPER).setText(f"{gst:.2f}")
        finally:
            self._updating = False
        self._recalc_row(row)
        self._recalc_footer_totals()
        self._pending_medicine = None
        self.med_search.search_box.clear()
        self.f_qty.setText("1")
        self.f_rate.setText("0.00")
        self.med_search.focus_search()

    def _first_empty_row(self) -> int:
        for row in range(self.lines_table.rowCount()):
            code = self.lines_table.item(row, COL_CODE).text().strip()
            name = self.lines_table.item(row, COL_NAME).text().strip()
            if not code and not name:
                return row
        self.lines_table.insertRow(self.lines_table.rowCount())
        row = self.lines_table.rowCount() - 1
        for col in range(len(LINE_COLUMNS)):
            self.lines_table.setItem(row, col, self._cell_item(row, col))
        return row

    def refresh(self) -> None:
        cache = get_session().cache
        self.payment_mode.clear()
        modes = cache.payment_modes if cache.loaded else []
        if not modes:
            try:
                modes = self.api.list_payment_modes()
            except ApiError:
                modes = []
        for mode in modes:
            self.payment_mode.addItem(mode.get("name", ""), mode.get("id"))
        if self.payment_mode.count():
            cash_idx = self.payment_mode.findText("Cash", Qt.MatchFlag.MatchFixedString)
            if cash_idx >= 0:
                self.payment_mode.setCurrentIndex(cash_idx)

        doctors = cache.doctors if cache.loaded else []
        if not doctors:
            try:
                refresh_doctors_cache(self.api)
                doctors = get_session().cache.doctors or self.api.list_doctors()
            except ApiError:
                doctors = []
        self.doctor.blockSignals(True)
        self.doctor.clear()
        self.doctor.addItem("", None)
        for doc in doctors:
            label = f"{doc.get('doctor_code', '')} — {doc.get('full_name') or doc.get('name', '')}"
            self.doctor.addItem(label, doc.get("id"))
        self.doctor.blockSignals(False)

        try:
            items = self.api.list_pharmacy_items("MD")
            self._catalog_all = items
            self._catalog_by_code = {item.get("code", "").upper(): item for item in items}
            last_info = self.api.pharmacy_last_sale_bill_info()
            last_no = last_info.get("last_bill_no") or ""
            self.last_bill_no.setText(last_no)
            preview = last_info.get("next_preview") or "Auto on Save"
            self.bill_no_chip.setText(f"Bill No: {preview}")
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

        self._load_recent_bills()
        self._recalc_all()
        self.med_search.focus_search()

    def _load_recent_bills(self) -> None:
        while self.recent_list.count():
            item = self.recent_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            end = date.today()
            start = end - timedelta(days=30)
            rows = self.api.pharmacy_sales_register(start.isoformat(), end.isoformat())
        except ApiError:
            rows = []
        if not rows:
            empty = QLabel("No recent bills")
            empty.setStyleSheet(f"color: {TEXT_TERTIARY}; font-size: 12px; padding: 8px 4px;")
            self.recent_list.addWidget(empty)
            return
        for row in list(reversed(rows))[:5]:
            self.recent_list.addWidget(self._recent_row(row))

    def _recent_row(self, row: dict) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(f"border-bottom: 1px solid {BORDER}; background: transparent;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 8, 4, 8)
        bill_no = QLabel(str(row.get("bill_no", "")))
        bill_no.setStyleSheet(
            f"font-family: Consolas, monospace; font-weight: 600; color: {TEXT_PRIMARY};"
        )
        patient = QLabel(row.get("patient_name") or "Walk-in")
        patient.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        bill_date = row.get("bill_date", "")
        if hasattr(bill_date, "strftime"):
            bill_date = bill_date.strftime("%d-%m-%Y")
        date_lbl = QLabel(str(bill_date))
        date_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        amount = QLabel(f"₹{float(row.get('net_amount', 0)):,.2f}")
        amount.setStyleSheet(
            f"font-family: Consolas, monospace; color: {TEXT_PRIMARY}; font-size: 12px;"
        )
        layout.addWidget(bill_no, stretch=1)
        layout.addWidget(patient, stretch=2)
        layout.addWidget(date_lbl, stretch=1)
        layout.addWidget(amount, stretch=1)
        return frame

    def _cell_item(self, row: int, col: int, text: str = "") -> QTableWidgetItem:
        if col == COL_IDX:
            text = str(row + 1)
        item = QTableWidgetItem(text)
        if col in READONLY_COLS:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setBackground(READONLY_BG)
        elif col in EDITABLE_COLS:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
        if col == COL_CODE:
            item.setForeground(QColor(ACCENT_DARK))
        return item

    def _ensure_blank_rows(self) -> None:
        for row in range(self.lines_table.rowCount()):
            for col in range(len(LINE_COLUMNS)):
                if not self.lines_table.item(row, col):
                    self.lines_table.setItem(row, col, self._cell_item(row, col))
            for col in (COL_TOT, COL_TAX, COL_DISAMNT, COL_NET):
                if not self.lines_table.item(row, col).text().strip():
                    self.lines_table.item(row, col).setText("0.00")

    def _find_patient(self) -> None:
        patient = pick_patient(self.api, self)
        if not patient:
            return
        self._patient = patient
        self.customer_name.setText(patient.get("full_name") or patient.get("name", ""))
        self.address1.setText(patient.get("contact_address1") or "")
        self.address2.setText(patient.get("contact_address2") or "")
        self.address3.setText(patient.get("contact_address3") or "")
        self._update_customer_avatar()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._recalc_row(row)
            self._recalc_footer_totals()
        finally:
            self._updating = False

    def _apply_medicine_row(
        self,
        row: int,
        medicine: dict,
        *,
        nos: int = 1,
        factor: float = 1.0,
        qty: int = 1,
    ) -> None:
        code = medicine.get("code", "")
        rate = medicine.get("sale_rate") or medicine.get("mrp") or medicine.get("rate") or 0
        self._item_ids[row] = medicine.get("id")
        self._catalog_by_code[code.upper()] = medicine
        self._updating = True
        try:
            self.lines_table.item(row, COL_IDX).setText(str(row + 1))
            self.lines_table.item(row, COL_CODE).setText(code)
            self.lines_table.item(row, COL_NAME).setText(medicine.get("name", ""))
            self.lines_table.item(row, COL_NOS).setText(str(nos))
            self.lines_table.item(row, COL_FACTOR).setText(str(factor))
            self.lines_table.item(row, COL_QTY).setText(str(qty))
            self.lines_table.item(row, COL_RATE).setText(f"{float(rate):.2f}")
        finally:
            self._updating = False

    def _show_stock(self, lookup: dict) -> None:
        code = lookup.get("item_code", "")
        stock = lookup.get("stock_qty", 0)
        rate = lookup.get("rate")
        rate_text = f"{float(rate):.2f}" if rate else "—"
        self.stock_label.setText(f"{code}  |  Stock {stock}  |  Rate {rate_text}")

    @staticmethod
    def _dec(text: str, default: Decimal = Decimal("0")) -> Decimal:
        try:
            return Decimal(text.strip() or "0")
        except Exception:
            return default

    def _recalc_row(self, row: int) -> None:
        code = self.lines_table.item(row, COL_CODE).text().strip()
        if not code:
            for col in (COL_TOT, COL_TAX, COL_DISAMNT, COL_NET):
                self.lines_table.item(row, col).setText("0.00")
            return
        nos = self._dec(self.lines_table.item(row, COL_NOS).text())
        factor = self._dec(self.lines_table.item(row, COL_FACTOR).text(), Decimal("1"))
        qty = self._dec(self.lines_table.item(row, COL_QTY).text())
        rate = self._dec(self.lines_table.item(row, COL_RATE).text())
        taxper = self._dec(self.lines_table.item(row, COL_TAXPER).text())
        disper = self._dec(self.lines_table.item(row, COL_DISPER).text())

        tot = (nos * factor * qty * rate).quantize(Decimal("0.01"))
        tax = (tot * taxper / Decimal("100")).quantize(Decimal("0.01"))
        dis = (tot * disper / Decimal("100")).quantize(Decimal("0.01"))
        net = (tot + tax - dis).quantize(Decimal("0.01"))

        for col, val in ((COL_TOT, tot), (COL_TAX, tax), (COL_DISAMNT, dis), (COL_NET, net)):
            self.lines_table.item(row, col).setText(f"{val:.2f}")

    def _recalc_all(self) -> None:
        self._updating = True
        try:
            for row in range(self.lines_table.rowCount()):
                code = self.lines_table.item(row, COL_CODE).text().strip()
                name = self.lines_table.item(row, COL_NAME).text().strip()
                if code or name:
                    self._recalc_row(row)
            self._recalc_footer_totals()
        finally:
            self._updating = False

    def _recalc_footer_totals(self) -> None:
        gross = Decimal("0")
        tax = Decimal("0")
        for row in range(self.lines_table.rowCount()):
            code = self.lines_table.item(row, COL_CODE).text().strip()
            if not code:
                continue
            line_tot = self._dec(self.lines_table.item(row, COL_TOT).text())
            line_dis = self._dec(self.lines_table.item(row, COL_DISAMNT).text())
            gross += line_tot - line_dis
            tax += self._dec(self.lines_table.item(row, COL_TAX).text())

        bill_disc = self._dec(self.bill_discount.text())
        subtotal = gross + tax - bill_disc
        round_off = self._dec(self.round_off.text())
        net = (subtotal + round_off).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if self.round_off.text().strip() in ("", "0", "0.00") and subtotal != net:
            auto_round = (net - subtotal).quantize(Decimal("0.01"))
            self.round_off.blockSignals(True)
            self.round_off.setText(f"{auto_round:.2f}")
            self.round_off.blockSignals(False)
            net = subtotal + auto_round

        self.gross_val["value"].setText(f"{gross:.2f}")
        self.tax_val["value"].setText(f"{tax:.2f}")
        self.net_val["value"].setText(f"{net:.2f}")
        self.pay_amount.setText(f"{net:.2f}")
        self._recalc_payment_summary(net)

    def _recalc_payment_summary(self, net: Decimal) -> None:
        is_credit = self.cash_credit.currentIndex() == 1
        paid = Decimal("0") if is_credit else net
        balance = net - paid
        self.paid_val.setText(f"{paid:.2f}")
        if balance > 0:
            self.balance_lbl.setText("BALANCE (DUE)")
            self.balance_val.setText(f"{balance:.2f}")
            self.balance_val.setStyleSheet(
                f"font-family: Consolas, monospace; font-weight: 700; font-size: 14px; color: {DANGER};"
            )
        else:
            self.balance_lbl.setText("BALANCE (CREDIT)")
            self.balance_val.setText(f"{abs(balance):.2f}")
            self.balance_val.setStyleSheet(
                f"font-family: Consolas, monospace; font-weight: 700; font-size: 14px; color: {ACCENT_DARK};"
            )

    def _remove_selected(self) -> None:
        row = self.lines_table.currentRow()
        if row < 0:
            return
        code = self.lines_table.item(row, COL_CODE).text().strip()
        if not code:
            return
        self.lines_table.removeRow(row)
        self._item_ids = {
            (idx if idx < row else idx - 1): value
            for idx, value in self._item_ids.items()
            if idx != row
        }
        if self.lines_table.rowCount() < 8:
            self.lines_table.insertRow(self.lines_table.rowCount())
        self._ensure_blank_rows()
        for idx in range(self.lines_table.rowCount()):
            self.lines_table.item(idx, COL_IDX).setText(str(idx + 1))
        self._recalc_footer_totals()

    def _collect_lines(self) -> list[dict]:
        lines: list[dict] = []
        for row in range(self.lines_table.rowCount()):
            code = self.lines_table.item(row, COL_CODE).text().strip()
            name = self.lines_table.item(row, COL_NAME).text().strip()
            if not code and not name:
                continue
            item_id = self._item_ids.get(row)
            if not item_id and code in self._catalog_by_code:
                item_id = self._catalog_by_code[code]["id"]
            if not item_id:
                raise ValueError(f"Row {row + 1}: medicine not linked properly. Add it again from search.")
            qty_val = int(self._dec(self.lines_table.item(row, COL_QTY).text()))
            if qty_val <= 0:
                raise ValueError(f"Row {row + 1}: quantity must be greater than zero.")
            nos_val = int(self._dec(self.lines_table.item(row, COL_NOS).text(), Decimal("1")))
            factor_val = float(self._dec(self.lines_table.item(row, COL_FACTOR).text(), Decimal("1")))
            exp_text = self.lines_table.item(row, COL_EXPDT).text().strip()
            expiry = None
            if exp_text:
                parts = exp_text.replace("-", "/").split("/")
                if len(parts) == 3:
                    expiry = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts[0]) <= 2 else exp_text
            lines.append(
                {
                    "item_id": item_id,
                    "quantity": qty_val,
                    "rate": float(self._dec(self.lines_table.item(row, COL_RATE).text())),
                    "nos": nos_val,
                    "factor": factor_val,
                    "batch_no": self.lines_table.item(row, COL_BATCH).text().strip() or None,
                    "expiry_date": expiry,
                    "tax_percent": float(self._dec(self.lines_table.item(row, COL_TAXPER).text())),
                    "tax_amount": float(self._dec(self.lines_table.item(row, COL_TAX).text())),
                    "line_discount_percent": float(
                        self._dec(self.lines_table.item(row, COL_DISPER).text())
                    ),
                    "line_discount_amount": float(
                        self._dec(self.lines_table.item(row, COL_DISAMNT).text())
                    ),
                    "line_net": float(self._dec(self.lines_table.item(row, COL_NET).text())),
                }
            )
        return lines

    def _save(self) -> None:
        try:
            lines = self._collect_lines()
        except ValueError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return
        if not lines:
            QMessageBox.warning(self, "Validation", "Enter at least one medicine line.")
            return
        doctor_id = self.doctor.currentData()
        doctor_name = self.doctor.currentText().strip()
        payload = {
            "patient_id": self._patient.get("id") if self._patient else None,
            "patient_name": self.customer_name.text().strip() or None,
            "doctor_id": doctor_id,
            "doctor_name": doctor_name or None,
            "scheme": self.scheme.currentText().strip() or None,
            "payment_mode_id": self.payment_mode.currentData(),
            "is_cash": self.cash_credit.currentIndex() == 0,
            "discount_amount": float(self._dec(self.bill_discount.text())),
            "round_off": float(self._dec(self.round_off.text())),
            "remarks": self.remarks.text().strip() or None,
            "address1": self.address1.text().strip() or None,
            "address2": self.address2.text().strip() or None,
            "address3": self.address3.text().strip() or None,
            "bill_date": self.bill_date.date().toPython().isoformat(),
            "lines": lines,
        }
        try:
            bill = self.api.create_pharmacy_sale_bill(payload)
            self._saved_bill_id = bill.get("id")
            bill_no = bill.get("bill_no", "")
            self.bill_no.setText(bill_no)
            self.last_bill_no.setText(bill_no)
            self.bill_no_chip.setText(f"Bill No: {bill_no}")
            QMessageBox.information(self, "Saved", f"Sale bill {bill_no} saved.")
            if self._saved_bill_id:
                preview_report(
                    self.api,
                    f"/reports/pharmacy-sale-bill/{self._saved_bill_id}",
                    parent=self,
                    title="Medical Bill Preview",
                    report_code="PHARMACY_SALE_BILL",
                )
            self._clear_after_save()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _clear_form(self) -> None:
        self._patient = None
        self._pending_medicine = None
        self._saved_bill_id = None
        self.customer_name.clear()
        self.remarks.clear()
        self.bill_discount.setText("0.00")
        self.address1.clear()
        self.address2.clear()
        self.address3.clear()
        self._item_ids.clear()
        self.lines_table.setRowCount(8)
        self.lines_table.clearContents()
        self._ensure_blank_rows()
        self.round_off.setText("0.00")
        self.bill_no.setText("0")
        self.stock_label.setText("—")
        self._update_customer_avatar()
        self._recalc_footer_totals()
        self.med_search.focus_search()

    def _clear_after_save(self) -> None:
        self._clear_form()
        try:
            last_info = self.api.pharmacy_last_sale_bill_info()
            preview = last_info.get("next_preview") or "Auto on Save"
            self.bill_no_chip.setText(f"Bill No: {preview}")
        except ApiError:
            pass
        self._load_recent_bills()

    def _print_bill(self) -> None:
        if not self._saved_bill_id:
            QMessageBox.information(self, "Print", "Save a bill first.")
            return
        print_report(
            self.api,
            f"/reports/pharmacy-sale-bill/{self._saved_bill_id}",
            parent=self,
            title="Medical Bill",
            report_code="PHARMACY_SALE_BILL",
        )
