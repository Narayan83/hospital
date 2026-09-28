from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.components.patient_search_dialog import pick_patient
from app.ui.print_utils import preview_report
from app.ui.styles import BTN_DANGER, BTN_PRIMARY, BTN_SECONDARY


class _NextFieldOnEnter(QObject):
    """Enter moves to the next entry field and does not activate dialog buttons."""

    def __init__(self, fields: list[QWidget]):
        super().__init__()
        self._fields = fields

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        target = obj if obj in self._fields else None
        if target is None and isinstance(obj, QWidget):
            parent = obj.parentWidget()
            while parent is not None and parent not in self._fields:
                parent = parent.parentWidget()
            target = parent
        if target not in self._fields:
            return False
        if isinstance(target, QComboBox):
            view = target.view()
            if view is not None and view.isVisible():
                return False
        if isinstance(target, QDateEdit):
            calendar = target.calendarWidget()
            if calendar is not None and calendar.isVisible():
                return False
        index = self._fields.index(target)
        if index + 1 < len(self._fields):
            self._fields[index + 1].setFocus(Qt.FocusReason.TabFocusReason)
        return True


class AdvanceCollectionWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._patient: dict | None = None
        self._payment_modes: list[dict] = []
        self._editing_id: str | None = None
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Advance Collection")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e40af;")
        layout.addWidget(heading)

        hint = QLabel(
            "Enter patient and amount, then Save — voucher number is generated automatically. "
            "To modify or reprint an existing advance, select it from Patient Advance History below."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Collection")
        form_box.setProperty("hmsExpandFormFields", True)
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form = QVBoxLayout(form_box)
        form.setSpacing(10)

        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Enter patient id")
        self.patient_no.returnPressed.connect(lambda: self._load_patient(show_errors=True))
        self.patient_no.editingFinished.connect(lambda: self._load_patient(show_errors=False))
        self.patient_no.textChanged.connect(self._on_patient_id_typed)

        find_btn = QPushButton("Find Patient")
        find_btn.setStyleSheet(BTN_SECONDARY)
        find_btn.clicked.connect(self._pick_patient)

        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self.patient_name.setPlaceholderText("Name appears when the patient id is entered")
        self._wide(self.patient_name)

        for field in (self.patient_no, find_btn, self.patient_name):
            field.setFixedHeight(34)

        patient_row = QHBoxLayout()
        patient_row.setSpacing(8)
        patient_row.addWidget(self._inline("Patient Id", self.patient_no), stretch=1)
        patient_row.addWidget(find_btn)
        patient_row.addWidget(self._inline("Name", self.patient_name), stretch=1)
        form.addLayout(patient_row)

        self.voucher_date = QDateEdit()
        self.voucher_date.setCalendarPopup(True)
        self.voucher_date.setDisplayFormat("dd-MM-yyyy")
        self.voucher_date.setDate(QDate.currentDate())
        self.voucher_date.setMaximumWidth(150)

        self.payment_mode = QComboBox()
        self.payment_mode.setMinimumWidth(220)
        self._wide(self.payment_mode)

        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setMaximumWidth(140)
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)

        money = QHBoxLayout()
        money.setSpacing(12)
        money.addWidget(self._labeled("Date", self.voucher_date))
        money.addWidget(self._labeled("Payment Mode", self.payment_mode), stretch=1)
        money.addWidget(self._labeled("Amount", self.amount))
        form.addLayout(money)

        self.narration = QLineEdit()
        self.narration.setPlaceholderText("Optional narration")
        self._wide(self.narration)
        form.addWidget(self._labeled("Narration", self.narration))

        layout.addWidget(form_box)
        self.setProperty("hmsExpandFormFields", True)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Advance")
        self.save_btn.setStyleSheet(BTN_PRIMARY)
        self.save_btn.clicked.connect(self._save)
        self.print_btn = QPushButton("Print")
        self.print_btn.setStyleSheet(BTN_SECONDARY)
        self.print_btn.clicked.connect(self._print_current)
        self.print_btn.setEnabled(False)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(BTN_DANGER)
        self.delete_btn.clicked.connect(self._delete_current)
        self.delete_btn.setEnabled(False)
        clear_btn = QPushButton("Clear / New")
        clear_btn.setStyleSheet(BTN_SECONDARY)
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.voucher_no_display = QLineEdit()
        self.voucher_no_display.setReadOnly(True)
        self.voucher_no_display.setPlaceholderText("Assigned on save")
        self.voucher_no_display.setFixedHeight(34)
        self.deposit_balance = QLineEdit("0.00")
        self.deposit_balance.setReadOnly(True)
        self.deposit_balance.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.deposit_balance.setFixedHeight(34)
        self.deposit_balance.setStyleSheet(
            "QLineEdit { background: #ecfdf5; color: #065f46; font-weight: 700; }"
        )
        summary = QHBoxLayout()
        summary.setSpacing(8)
        summary.addWidget(self._inline("Voucher No", self.voucher_no_display), stretch=1)
        summary.addWidget(self._inline("Current Balance", self.deposit_balance), stretch=1)
        layout.addLayout(summary)

        self.status = QLineEdit()
        self.status.setReadOnly(True)
        layout.addWidget(self.status)

        hist_box = QGroupBox("Patient Advance History")
        hist_layout = QVBoxLayout(hist_box)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Voucher", "Date", "Amount", "Payment Mode", "Narration", "Id"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_row_activated)
        hist_layout.addWidget(self.table)

        hist_btns = QHBoxLayout()
        edit_row_btn = QPushButton("Edit Selected")
        edit_row_btn.clicked.connect(self._edit_selected)
        print_row_btn = QPushButton("Print Selected")
        print_row_btn.clicked.connect(self._print_selected)
        delete_row_btn = QPushButton("Delete Selected")
        delete_row_btn.clicked.connect(self._delete_selected)
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self._reload_history)
        hist_btns.addWidget(edit_row_btn)
        hist_btns.addWidget(print_row_btn)
        hist_btns.addWidget(delete_row_btn)
        hist_btns.addWidget(refresh_btn)
        hist_btns.addStretch()
        hist_layout.addLayout(hist_btns)
        layout.addWidget(hist_box, stretch=1)

        self._enter_filter = _NextFieldOnEnter(
            [self.patient_no, self.voucher_date, self.payment_mode, self.amount, self.narration]
        )
        for field in (self.patient_no, self.voucher_date, self.payment_mode, self.amount, self.narration):
            field.installEventFilter(self._enter_filter)
            if isinstance(field, QDateEdit):
                for editor in field.findChildren(QLineEdit):
                    editor.installEventFilter(self._enter_filter)

        QTimer.singleShot(0, self._focus_patient_id)

    @staticmethod
    def _wide(widget: QWidget) -> QWidget:
        widget.setProperty("hmsAllowWide", True)
        widget.setMaximumWidth(16777215)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return widget

    @staticmethod
    def _inline(caption: str, field: QWidget) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(caption)
        label.setStyleSheet("color: #334155; font-size: 12px; font-weight: 600;")
        label.setFixedWidth(label.fontMetrics().horizontalAdvance(caption) + 6)
        field.setFixedHeight(34)
        row.addWidget(label)
        row.addWidget(field, stretch=1)
        return wrap

    @staticmethod
    def _labeled(caption: str, field: QWidget) -> QWidget:
        wrap = QWidget()
        column = QVBoxLayout(wrap)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        label = QLabel(caption)
        label.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
        column.addWidget(label)
        column.addWidget(field)
        return wrap

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Re-assert wide fields in case global form styling capped them.
        for field in (self.patient_name, self.narration):
            field.setMaximumWidth(16777215)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        QTimer.singleShot(0, self._focus_patient_id)

    def _focus_patient_id(self) -> None:
        self.patient_no.setFocus(Qt.FocusReason.OtherFocusReason)
        self.patient_no.selectAll()

    def refresh(self) -> None:
        try:
            self._payment_modes = self.api.list_payment_modes()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        current = self.payment_mode.currentData()
        self.payment_mode.clear()
        for mode in self._payment_modes:
            label = f"{mode.get('code')} — {mode.get('name')}"
            self.payment_mode.addItem(label, mode.get("id"))
        if current:
            idx = self.payment_mode.findData(current)
            if idx >= 0:
                self.payment_mode.setCurrentIndex(idx)
        elif self.payment_mode.count():
            for i in range(self.payment_mode.count()):
                mode = next(
                    (m for m in self._payment_modes if m.get("id") == self.payment_mode.itemData(i)),
                    None,
                )
                if mode and mode.get("is_cash"):
                    self.payment_mode.setCurrentIndex(i)
                    break
        self._focus_patient_id()

    def apply_patient(self, patient: dict | None) -> None:
        if not patient:
            return
        self._patient = patient
        self.patient_no.setText(patient.get("patient_no") or "")
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        self.patient_name.setText(" ".join(p for p in parts if p))
        self._refresh_deposit_balance()
        self._reload_history()

    def _pick_patient(self) -> None:
        patient = pick_patient(self.api, self)
        if patient:
            self.apply_patient(patient)

    def _on_patient_id_typed(self, text: str) -> None:
        loaded = ""
        if self._patient:
            loaded = (self._patient.get("patient_no") or "").strip().upper()
        if text.strip().upper() == loaded:
            return
        self._patient = None
        self.patient_name.clear()
        self.deposit_balance.setText("0.00")
        self._rows = []
        self.table.setRowCount(0)

    def _load_patient(self, show_errors: bool = True) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            return
        if self._patient and (self._patient.get("patient_no") or "").strip().upper() == patient_no.upper():
            if not self.patient_name.text().strip():
                self.apply_patient(self._patient)
            return
        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                self._patient = None
                self.patient_name.clear()
                if show_errors:
                    QMessageBox.warning(self, "Patient", f"No patient found: {patient_no}")
                else:
                    self.status.setText(f"No patient found: {patient_no}")
                return
            self.apply_patient(items[0])
            self.status.setText(f"Patient loaded: {items[0].get('patient_no') or patient_no}")
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Patient", str(exc))
            else:
                self.status.setText(str(exc))

    def _refresh_deposit_balance(self) -> None:
        if not self._patient:
            self.deposit_balance.setText("0.00")
            return
        try:
            data = self.api.get_patient_deposit_balance(patient_id=self._patient.get("id"))
            self.deposit_balance.setText(f"{float(data.get('balance', 0)):,.2f}")
        except ApiError:
            self.deposit_balance.setText("0.00")

    def _set_editing(self, advance: dict | None) -> None:
        if not advance:
            self._editing_id = None
            self.voucher_no_display.clear()
            self.voucher_no_display.setPlaceholderText("Assigned on save")
            self.save_btn.setText("Save Advance")
            self.print_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        self._editing_id = advance.get("id")
        self.voucher_no_display.setText(advance.get("voucher_no") or "")
        self.save_btn.setText("Update Advance")
        self.print_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        vd = advance.get("voucher_date") or ""
        if vd:
            try:
                y, m, d = [int(x) for x in str(vd)[:10].split("-")]
                self.voucher_date.setDate(QDate(y, m, d))
            except Exception:
                pass
        mode_id = advance.get("payment_mode_id")
        if mode_id:
            idx = self.payment_mode.findData(mode_id)
            if idx >= 0:
                self.payment_mode.setCurrentIndex(idx)
        self.amount.setText(f"{float(advance.get('amount') or 0):.2f}")
        self.narration.setText(advance.get("narration") or "")
        self.status.setText(f"Editing {advance.get('voucher_no', '')}")

    def _reload_history(self) -> None:
        self._rows = []
        self.table.setRowCount(0)
        if not self._patient:
            return
        try:
            self._rows = self.api.list_advances(patient_id=self._patient.get("id")) or []
        except ApiError as exc:
            QMessageBox.warning(self, "History", str(exc))
            return
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
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, cell)

    def _selected_advance(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _on_row_activated(self) -> None:
        self._edit_selected()

    def _edit_selected(self) -> None:
        advance = self._selected_advance()
        if not advance:
            QMessageBox.information(self, "Edit", "Select a row first.")
            return
        self._set_editing(advance)

    def _print_selected(self) -> None:
        advance = self._selected_advance()
        if not advance or not advance.get("id"):
            QMessageBox.information(self, "Print", "Select a row first.")
            return
        self._print_voucher(advance["id"])

    def _delete_selected(self) -> None:
        advance = self._selected_advance()
        if not advance or not advance.get("id"):
            QMessageBox.information(self, "Delete", "Select a row first.")
            return
        self._confirm_delete(advance)

    def _print_current(self) -> None:
        if not self._editing_id:
            QMessageBox.information(self, "Print", "Save an advance first, or select one from history.")
            return
        self._print_voucher(self._editing_id)

    def _print_voucher(self, voucher_id: str) -> None:
        endpoint = f"/reports/advance/{voucher_id}"
        preview_report(
            self.api,
            endpoint,
            parent=self,
            title="Advance Receipt Preview",
            report_code="ADVANCE_RECEIPT",
            default_copies=1,
        )

    def _delete_current(self) -> None:
        if not self._editing_id:
            return
        advance = {
            "id": self._editing_id,
            "voucher_no": self.voucher_no_display.text(),
        }
        self._confirm_delete(advance)

    def _confirm_delete(self, advance: dict) -> None:
        voucher_no = advance.get("voucher_no") or ""
        reply = QMessageBox.question(
            self,
            "Delete Advance",
            f"Delete advance voucher {voucher_no}?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_advance(advance["id"])
        except ApiError as exc:
            QMessageBox.warning(self, "Delete", str(exc))
            return
        QMessageBox.information(self, "Deleted", f"Advance {voucher_no} deleted.")
        if self._editing_id == advance.get("id"):
            self._clear_form_keep_patient()
        self._refresh_deposit_balance()
        self._reload_history()

    def _clear_form_keep_patient(self) -> None:
        self._set_editing(None)
        self.amount.clear()
        self.narration.clear()
        self.voucher_date.setDate(QDate.currentDate())
        self.status.clear()

    def _clear(self) -> None:
        self._patient = None
        self.patient_no.clear()
        self.patient_name.clear()
        self.deposit_balance.setText("0.00")
        self._clear_form_keep_patient()
        self._rows = []
        self.table.setRowCount(0)
        self._focus_patient_id()

    def _save(self) -> None:
        if not self._patient:
            QMessageBox.warning(self, "Validation", "Select a patient first.")
            return
        mode_id = self.payment_mode.currentData()
        if not mode_id:
            QMessageBox.warning(self, "Validation", "Select a payment mode.")
            return
        try:
            amount = Decimal(self.amount.text().strip() or "0")
        except Exception:
            QMessageBox.warning(self, "Validation", "Enter a valid amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Amount must be greater than zero.")
            return

        qd = self.voucher_date.date()
        payload = {
            "voucher_date": date(qd.year(), qd.month(), qd.day()).isoformat(),
            "payment_mode_id": mode_id,
            "amount": str(amount),
            "narration": self.narration.text().strip() or None,
        }
        try:
            if self._editing_id:
                result = self.api.update_advance(self._editing_id, payload)
                action = "updated"
            else:
                payload["patient_id"] = self._patient.get("id")
                result = self.api.collect_advance(payload)
                action = "saved"
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self._set_editing(result)
        self._refresh_deposit_balance()
        self._reload_history()
        self.status.setText(f"{action.title()} {result.get('voucher_no', '')}")

        reply = QMessageBox.question(
            self,
            "Advance Receipt",
            f"Advance {action}. Voucher: {result.get('voucher_no', '')}\n\n"
            "Open print preview now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and result.get("id"):
            self._print_voucher(result["id"])
