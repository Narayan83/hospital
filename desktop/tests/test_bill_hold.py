"""Hold/Resume is in-memory only — one parked draft per screen, no bill number."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DESKTOP_ROOT = Path(__file__).resolve().parents[1]
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QWidget

from app.ui.bill_hold import BillHoldMixin, BillHoldSlot, hold_label_from_patient


def _app() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


class BillHoldSlotTests(unittest.TestCase):
    def test_park_take_roundtrip(self) -> None:
        slot = BillHoldSlot()
        self.assertFalse(slot.has_draft())
        slot.park({"hold_label": "P1 Ramesh", "lines": [{"service_id": "a", "qty": 1}]})
        self.assertTrue(slot.has_draft())
        self.assertEqual(slot.label(), "P1 Ramesh")
        peeked = slot.peek()
        peeked["lines"][0]["qty"] = 9
        taken = slot.take()
        self.assertEqual(taken["lines"][0]["qty"], 1)
        self.assertFalse(slot.has_draft())
        self.assertIsNone(slot.take())

    def test_second_park_replaces_first(self) -> None:
        slot = BillHoldSlot()
        slot.park({"hold_label": "first"})
        slot.park({"hold_label": "second"})
        self.assertEqual(slot.take()["hold_label"], "second")

    def test_hold_label_from_patient(self) -> None:
        self.assertEqual(
            hold_label_from_patient({"patient_no": "P9", "first_name": "Asha"}),
            "P9 Asha",
        )
        self.assertEqual(hold_label_from_patient(None, extra="IPD"), "IPD")


class DummyBill(BillHoldMixin, QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._modification_mode = False
        self._patient = None
        self._bill_lines: list[dict] = []
        self.status_text = ""
        layout = QHBoxLayout(self)
        self._setup_bill_hold_buttons(layout)

    def _set_status(self, message: str) -> None:
        self.status_text = message

    def _capture_hold_state(self) -> dict:
        return {
            "hold_label": hold_label_from_patient(self._patient),
            "patient": dict(self._patient) if self._patient else None,
            "bill_lines": [dict(line) for line in self._bill_lines],
        }

    def _restore_hold_state(self, state: dict) -> None:
        self._clear_bill()
        self._patient = dict(state["patient"]) if state.get("patient") else None
        self._bill_lines = [dict(line) for line in (state.get("bill_lines") or [])]

    def _clear_bill(self) -> None:
        self._patient = None
        self._bill_lines = []
        self._refresh_hold_buttons()


class BillHoldMixinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def setUp(self) -> None:
        self._orig_info = QMessageBox.information
        self._orig_question = QMessageBox.question
        QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        self.widget = DummyBill()

    def tearDown(self) -> None:
        QMessageBox.information = self._orig_info
        QMessageBox.question = self._orig_question
        self.widget.deleteLater()

    def test_hold_resume_new_bill(self) -> None:
        self.widget._patient = {"patient_no": "P100", "first_name": "Ravi"}
        self.widget._bill_lines = [{"service_id": "s1", "service_name": "OPD Consult"}]
        self.widget._on_hold_bill()
        self.assertIsNone(self.widget._patient)
        self.assertEqual(self.widget._bill_lines, [])
        self.assertTrue(self.widget._held.has_draft())
        self.assertTrue(self.widget.resume_btn.isEnabled())

        self.widget._patient = {"patient_no": "P200", "first_name": "Urgent"}
        self.widget._bill_lines = [{"service_id": "s2"}]
        self.widget._on_resume_held()
        self.assertEqual(self.widget._patient["patient_no"], "P100")
        self.assertEqual(self.widget._bill_lines[0]["service_id"], "s1")
        self.assertFalse(self.widget._held.has_draft())

    def test_hold_empty_does_nothing(self) -> None:
        self.widget._on_hold_bill()
        self.assertFalse(self.widget._held.has_draft())

    def test_overwrite_hold_requires_confirm(self) -> None:
        self.widget._patient = {"patient_no": "A"}
        self.widget._on_hold_bill()
        self.widget._patient = {"patient_no": "B"}
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No)
        self.widget._on_hold_bill()
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        self.assertEqual(self.widget._held.label(), "A")
        self.assertEqual(self.widget._patient["patient_no"], "B")

    def test_deactivate_clears_form_keeps_hold(self) -> None:
        self.widget._patient = {"patient_no": "P100", "first_name": "Ravi"}
        self.widget._bill_lines = [{"service_id": "s1"}]
        self.widget._on_hold_bill()
        self.widget._patient = {"patient_no": "P200"}
        self.widget._bill_lines = [{"service_id": "s9"}]
        self.widget._clear_bill()
        self.assertIsNone(self.widget._patient)
        self.assertTrue(self.widget._held.has_draft())
        self.widget._on_resume_held()
        self.assertEqual(self.widget._patient["patient_no"], "P100")


if __name__ == "__main__":
    unittest.main()
