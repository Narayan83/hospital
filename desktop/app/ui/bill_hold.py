"""Park one unsaved bill in memory so the counter can start another.

Held drafts are never saved, never numbered, and never appear in reports.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QMessageBox, QPushButton


def combo_value(combo: QComboBox):
    return combo.currentData()


def set_combo_value(combo: QComboBox, value) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def date_iso(edit: QDateEdit) -> str:
    qd = edit.date()
    return f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"


def set_date_iso(edit: QDateEdit, value: str | None) -> None:
    if not value:
        return
    parts = str(value).split("-")
    if len(parts) < 3:
        return
    try:
        edit.setDate(QDate(int(parts[0]), int(parts[1][:2]), int(parts[2][:2])))
    except ValueError:
        return


def hold_label_from_patient(patient: dict | None, extra: str = "") -> str:
    if not patient:
        return extra or "held bill"
    number = (patient.get("patient_no") or "").strip()
    name = (patient.get("patient_name") or "").strip()
    if not name:
        name = " ".join(
            part
            for part in (
                patient.get("first_name"),
                patient.get("last_name"),
            )
            if part
        ).strip()
    if number and name:
        return f"{number} {name}".strip()
    return number or name or extra or "held bill"


class BillHoldSlot:
    """At most one parked draft. Parking a second bill replaces the first."""

    def __init__(self) -> None:
        self._draft: dict | None = None

    def has_draft(self) -> bool:
        return self._draft is not None

    def label(self) -> str:
        if not self._draft:
            return ""
        return str(self._draft.get("hold_label") or "held bill")

    def park(self, state: dict) -> None:
        self._draft = deepcopy(state)

    def take(self) -> dict | None:
        draft = self._draft
        self._draft = None
        if draft is None:
            return None
        return deepcopy(draft)

    def peek(self) -> dict | None:
        if self._draft is None:
            return None
        return deepcopy(self._draft)


class BillHoldMixin:
    """Hold / Resume buttons for new-bill screens (not modify mode)."""

    def _setup_bill_hold_buttons(
        self,
        layout: QHBoxLayout,
        *,
        style: str | None = None,
        style_button=None,
        insert_at: int | None = None,
    ) -> None:
        self._held = BillHoldSlot()
        self.hold_btn = None
        self.resume_btn = None
        if getattr(self, "_modification_mode", False):
            return
        self.hold_btn = QPushButton("Hold Bill")
        self.resume_btn = QPushButton("Resume Held")
        self.hold_btn.setToolTip("Park this unsaved bill and start a new one.")
        self.resume_btn.setToolTip("Bring back the parked bill.")
        self.hold_btn.clicked.connect(self._on_hold_bill)
        self.resume_btn.clicked.connect(self._on_resume_held)
        if style_button:
            style_button(self.hold_btn)
            style_button(self.resume_btn)
        elif style:
            self.hold_btn.setStyleSheet(style)
            self.resume_btn.setStyleSheet(style)
        if insert_at is None:
            layout.addWidget(self.hold_btn)
            layout.addWidget(self.resume_btn)
        else:
            layout.insertWidget(insert_at, self.hold_btn)
            layout.insertWidget(insert_at + 1, self.resume_btn)
        self._refresh_hold_buttons()

    def _refresh_hold_buttons(self) -> None:
        if not getattr(self, "_held", None):
            return
        resume = getattr(self, "resume_btn", None)
        if resume is None:
            return
        has_draft = self._held.has_draft()
        resume.setEnabled(has_draft)
        label = self._held.label()
        resume.setText(f"Resume ({label})" if has_draft and label else "Resume Held")

    def _has_holdable_content(self) -> bool:
        if getattr(self, "_patient", None):
            return True
        if getattr(self, "_admission", None):
            return True
        return bool(getattr(self, "_bill_lines", None))

    def _reset_current_bill_form(self) -> None:
        if hasattr(self, "_clear_bill"):
            self._clear_bill()
        elif hasattr(self, "_clear_form"):
            self._clear_form()

    def _confirm_hold(self, title: str, text: str) -> bool:
        yes = QMessageBox.StandardButton.Yes
        no = QMessageBox.StandardButton.No
        return QMessageBox.question(self, title, text, yes | no, no) == yes

    def _on_hold_bill(self) -> None:
        if getattr(self, "_modification_mode", False):
            return
        if not self._has_holdable_content():
            QMessageBox.information(
                self,
                "Hold Bill",
                "Nothing to hold. Load a patient or add services first.",
            )
            return
        if self._held.has_draft():
            if not self._confirm_hold(
                "Replace Held Bill",
                f"A bill is already on hold ({self._held.label()}).\n"
                "Replace it with this bill?",
            ):
                return
        self._held.park(self._capture_hold_state())
        self._reset_current_bill_form()
        self._refresh_hold_buttons()
        self._set_status(
            f"Bill held: {self._held.label()} — start a new bill, then click Resume."
        )

    def _on_resume_held(self) -> None:
        if not self._held.has_draft():
            QMessageBox.information(self, "Resume", "No bill is on hold.")
            return
        if self._has_holdable_content():
            if not self._confirm_hold(
                "Resume Held Bill",
                "Current bill is not saved.\nDiscard it and resume the held bill?",
            ):
                return
        state = self._held.take()
        if not state:
            self._refresh_hold_buttons()
            return
        self._restore_hold_state(state)
        self._refresh_hold_buttons()
        self._set_status(f"Resumed held bill: {state.get('hold_label') or ''}".strip())

    def _apply_hold_payments(self, payments: list | None) -> None:
        panel = getattr(self, "payment_panel", None)
        if panel is None:
            return
        net_widget = getattr(self, "net_amount", None)
        raw = net_widget.text() if net_widget is not None else "0"
        try:
            net = Decimal(str(raw).replace(",", "").strip() or "0")
        except Exception:
            net = Decimal("0")
        panel.set_net_amount(net, auto_fill_cash=False)
        panel.load_payments(payments or [])
