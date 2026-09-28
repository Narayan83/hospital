"""Reset module UI state when the user leaves a menu."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def deactivate_module(module_id: str | None, widget: QWidget | None) -> None:
    """Clear pending navigation and in-memory form state for a module being left."""
    if not module_id or widget is None:
        return

    _clear_pending_navigation(module_id)

    if hasattr(widget, "on_module_deactivated"):
        widget.on_module_deactivated()
        return

    if hasattr(widget, "reset_state") and callable(widget.reset_state):
        widget.reset_state()
        return

    if hasattr(widget, "_clear_bill") and callable(widget._clear_bill):
        widget._clear_bill()
        return

    if hasattr(widget, "_clear_form") and callable(widget._clear_form):
        widget._clear_form()


def _clear_pending_navigation(module_id: str) -> None:
    if module_id == "opd_bill_reprint":
        from app.ui.widgets.opd_bill_reprint import OpdBillReprintWidget

        OpdBillReprintWidget.pending_patient_no = None
    elif module_id == "pathology_bill_reprint":
        from app.ui.widgets.pathology_bill_reprint import PathologyBillReprintWidget

        PathologyBillReprintWidget.pending_patient_no = None
    elif module_id == "diagnose_management":
        from app.ui.widgets.discharge_summary import set_pending_admission

        set_pending_admission(None)
