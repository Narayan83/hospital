from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QMouseEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.styles import TABLE_COMPACT_STYLE, compact_field_style, form_field_style
from app.ui.responsive_layout import get_density

PAYMENT_ROW_HEIGHT = 34
PAYMENT_ROW_HEIGHT_COMPACT = 26


def _amount_edit_style() -> str:
    return form_field_style() + compact_field_style()


def _cell_padding(compact: bool) -> int:
    return 1 if compact else 2


def _payment_row_heights() -> tuple[int, int]:
    d = get_density()
    return d.payment_row_height, d.payment_row_compact


COMPACT_GROUP_STYLE = """
QGroupBox {
    margin-top: 8px;
    padding: 8px 6px 4px 6px;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""


def _compact_btn_style() -> str:
    d = get_density()
    h = d.compact_field_height
    return f"min-height: {h}px; max-height: {h + 2}px; padding: 2px 10px; font-size: {d.compact_font_size}px;"


class _PaymentAmountEdit(QLineEdit):
    """Amount field — empty by default; zero placeholder is not typed over."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("0")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def _is_zero_value(self) -> bool:
        text = self.text().strip()
        if not text:
            return True
        try:
            return Decimal(text) == 0
        except Exception:
            return False

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        if self._is_zero_value():
            self.selectAll()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if self._is_zero_value():
            self.selectAll()


class MultiPaymentPanel(QGroupBox):
    """All payment modes visible at once — enter amount per mode (no dropdown rows)."""

    def __init__(
        self,
        title: str = "Payments",
        *,
        compact: bool = False,
        group_style: str | None = None,
        field_style: str | None = None,
    ):
        super().__init__(title)
        self._compact = compact
        self._field_style = field_style
        self._payment_modes: list[dict] = []
        self._net_amount = Decimal("0")
        self._amount_edits: dict[str, QLineEdit] = {}
        if compact or group_style:
            self.setStyleSheet(group_style or COMPACT_GROUP_STYLE)
        self._build_ui()

    def _row_height(self) -> int:
        normal, compact = _payment_row_heights()
        return compact if self._compact else normal

    def _amount_cell(self) -> tuple[QWidget, _PaymentAmountEdit]:
        """Wrap the amount editor so each row gets its own padded lane."""
        pad = _cell_padding(self._compact)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(0)

        amount_edit = _PaymentAmountEdit()
        amount_edit.setStyleSheet(self._field_style or _amount_edit_style())
        amount_edit.setMinimumWidth(72)
        amount_edit.textChanged.connect(self._update_totals)
        layout.addWidget(amount_edit)
        return host, amount_edit

    def _effective_row_height(self, amount_edit: _PaymentAmountEdit) -> int:
        pad = _cell_padding(self._compact)
        content_h = max(amount_edit.sizeHint().height(), amount_edit.minimumSizeHint().height())
        return max(self._row_height(), content_h + (pad * 2) + 2)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        if self._compact:
            layout.setContentsMargins(4, 4, 4, 2)
            layout.setSpacing(2)
        else:
            layout.setContentsMargins(8, 12, 8, 8)
            layout.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        fill_btn = QPushButton("Fill Balance")
        clear_btn = QPushButton("Clear")
        if self._compact:
            fill_btn.setStyleSheet(_compact_btn_style())
            clear_btn.setStyleSheet(_compact_btn_style())
        fill_btn.clicked.connect(self._fill_balance)
        clear_btn.clicked.connect(self.clear_amounts)
        btn_row.addWidget(fill_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Payment Mode", "Amount"])
        self.table.setProperty("hmsColumnKinds", ["text", "number"])
        self.table.setProperty("hmsStretchColumn", 0)
        amount_w = 100 if self._compact else 110
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, amount_w)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_style = TABLE_COMPACT_STYLE
        if self._compact:
            table_style += """
            QHeaderView::section { padding: 3px 6px; font-size: 12px; }
            QTableWidget { font-size: 12px; }
            """
        self.table.setStyleSheet(table_style)
        layout.addWidget(self.table)

        totals = QHBoxLayout()
        totals.setContentsMargins(0, 4 if self._compact else 2, 0, 0)
        totals.setSpacing(8)
        self.total_paid = QLabel("Paid: 0.00")
        self.balance = QLabel("Balance: 0.00")
        total_font = "11px" if self._compact else "11px"
        self.total_paid.setStyleSheet(f"font-weight: bold; color: #0f766e; font-size: {total_font};")
        self.balance.setStyleSheet(f"font-weight: bold; color: #b45309; font-size: {total_font};")
        totals.addWidget(self.total_paid)
        totals.addStretch()
        totals.addWidget(self.balance)
        layout.addLayout(totals)

    def set_payment_modes(self, modes: list[dict]) -> None:
        saved = self.get_payments()
        self._payment_modes = list(modes)
        self._rebuild_table()
        if saved:
            self.load_payments(saved)

    def _rebuild_table(self) -> None:
        row_h = self._row_height()
        self.table.setRowCount(0)
        self._amount_edits.clear()
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(row_h)

        for row, mode in enumerate(self._payment_modes):
            self.table.insertRow(row)
            ledger = mode.get("ledger_code") or mode.get("ledger_name") or ""
            name = (mode.get("name") or mode.get("code") or "").strip()
            code = (mode.get("code") or "").strip()
            # Short visible label so Amount stays on-screen; full detail in tooltip.
            if name and code and name.upper() != code.upper():
                label = f"{code} — {name}"
            else:
                label = name or code or "—"
            tip = label
            if ledger:
                tip = f"{label}  [{ledger}]"
            name_item = QTableWidgetItem(label)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setToolTip(tip)
            self.table.setItem(row, 0, name_item)

            amount_host, amount_edit = self._amount_cell()
            row_h = max(row_h, self._effective_row_height(amount_edit))
            self.table.setRowHeight(row, row_h)
            self.table.setCellWidget(row, 1, amount_host)
            self._amount_edits[str(mode.get("id"))] = amount_edit

        # Keep Amount column visible after rows load (Mode stretches, Amount stays ~100px).
        from app.ui.table_utils import enable_column_resize

        enable_column_resize(self.table)
        amount_w = 100 if self._compact else 110
        self.table.setColumnWidth(1, amount_w)

        header_h = self.table.horizontalHeader().height()
        rows = max(len(self._payment_modes), 1)
        frame = self.table.frameWidth() * 2
        table_h = header_h + rows * row_h + frame + 2
        self.table.setMinimumHeight(table_h)
        self.table.setMaximumHeight(table_h)

    def set_net_amount(self, net_amount: Decimal | float | str, *, auto_fill_cash: bool = True) -> None:
        self._net_amount = Decimal(str(net_amount or "0"))
        if self._net_amount < 0:
            self._net_amount = Decimal("0")
        self._update_totals()
        if auto_fill_cash:
            self.fill_cash_default()

    def fill_cash_default(self) -> None:
        if self._net_amount <= 0:
            self.clear_amounts()
            return
        for mode in self._payment_modes:
            if mode.get("is_cash"):
                edit = self._amount_edits.get(str(mode.get("id")))
                if not edit:
                    continue
                for other_id, other_edit in self._amount_edits.items():
                    other_edit.blockSignals(True)
                    if other_id == str(mode.get("id")):
                        other_edit.setText(f"{self._net_amount:.2f}")
                    else:
                        other_edit.setText("")
                    other_edit.blockSignals(False)
                self._update_totals()
                return

    def clear_amounts(self) -> None:
        for edit in self._amount_edits.values():
            edit.blockSignals(True)
            edit.setText("")
            edit.blockSignals(False)
        self._update_totals()

    def clear(self) -> None:
        self.clear_amounts()

    def load_payments(self, payments: list[dict]) -> None:
        self.clear_amounts()
        for payment in payments or []:
            mode_id = str(payment.get("payment_mode_id", ""))
            edit = self._amount_edits.get(mode_id)
            if not edit:
                continue
            edit.blockSignals(True)
            edit.setText(f"{Decimal(str(payment.get('amount', 0))):.2f}")
            edit.blockSignals(False)
        self._update_totals()

    def get_payments(self) -> list[dict]:
        rows: list[dict] = []
        for mode_id, amount_edit in self._amount_edits.items():
            amount = self._parse_amount(amount_edit.text())
            if amount <= 0:
                continue
            rows.append({"payment_mode_id": mode_id, "amount": str(amount)})
        return rows

    def validate(self) -> tuple[bool, str]:
        payments = self.get_payments()
        if not payments:
            return False, "Enter amount in at least one payment mode."
        total = sum(Decimal(item["amount"]) for item in payments)
        if abs(total - self._net_amount) > Decimal("0.01"):
            return False, (
                f"Payment total ({total:.2f}) must equal net amount ({self._net_amount:.2f})."
            )
        return True, ""

    def _fill_balance(self) -> None:
        paid = sum(self._parse_amount(edit.text()) for edit in self._amount_edits.values())
        balance = self._net_amount - paid
        if balance <= 0:
            return
        for mode in self._payment_modes:
            if mode.get("is_cash"):
                edit = self._amount_edits.get(str(mode.get("id")))
                if edit and self._parse_amount(edit.text()) == 0:
                    edit.setText(f"{balance:.2f}")
                    return
        for edit in self._amount_edits.values():
            if self._parse_amount(edit.text()) == 0:
                edit.setText(f"{balance:.2f}")
                return

    def _parse_amount(self, text: str) -> Decimal:
        cleaned = (text or "").strip() or "0"
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _update_totals(self) -> None:
        total = sum(self._parse_amount(edit.text()) for edit in self._amount_edits.values())
        balance = self._net_amount - total
        self.total_paid.setText(f"Paid: {total:.2f}")
        self.balance.setText(f"Balance: {balance:.2f}")
        if balance == 0 and self._net_amount > 0:
            size = "11px" if self._compact else "11px"
            self.balance.setStyleSheet(f"font-weight: bold; color: #15803d; font-size: {size};")
        else:
            size = "11px" if self._compact else "11px"
            self.balance.setStyleSheet(f"font-weight: bold; color: #b45309; font-size: {size};")
