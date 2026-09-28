"""Shared QDateEdit setup — centered text and calendar popup button."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import QDateEdit

from app.ui.styles import date_edit_stylesheet

_DATE_LINE_STYLE = (
    "border: none; background: transparent; padding: 0px; margin: 0px; min-height: 0px;"
)


def _apply_date_line_layout(date_edit: QDateEdit) -> None:
    line = date_edit.lineEdit()
    if line is None:
        return
    line.setProperty("hmsSkipFormStyle", True)
    line.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    line.setFrame(False)
    line.setContentsMargins(0, 0, 0, 0)
    line.setStyleSheet(_DATE_LINE_STYLE)


def configure_date_edit(
    date_edit: QDateEdit,
    *,
    display_format: str = "dd/MM/yyyy",
    calendar_popup: bool = True,
) -> QDateEdit:
    date_edit.setCalendarPopup(calendar_popup)
    date_edit.setDisplayFormat(display_format)
    date_edit.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
    _apply_date_line_layout(date_edit)
    return date_edit


def finalize_date_edit(date_edit: QDateEdit) -> None:
    """Re-apply inner line layout after stylesheets and fixed heights are set."""
    _apply_date_line_layout(date_edit)
    QTimer.singleShot(0, lambda: _apply_date_line_layout(date_edit))


class StandardDateEdit(QDateEdit):
    """Date field with calendar popup, centered text, and standard calendar button."""

    def __init__(self, parent=None, *, default: QDate | None = None):
        super().__init__(parent)
        configure_date_edit(self)
        self.setDate(default or QDate.currentDate())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        finalize_date_edit(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        _apply_date_line_layout(self)


def style_date_field(
    field: QDateEdit,
    *,
    compact: bool = False,
    fixed_height: int | None = None,
    min_width: int | None = None,
    extra_style: str = "",
) -> None:
    configure_date_edit(field)
    field.setProperty("hmsCompactDate", compact)
    css = date_edit_stylesheet(compact=compact)
    field.setStyleSheet(f"{extra_style}\n{css}".strip() if extra_style else css)
    if fixed_height is not None:
        field.setFixedHeight(fixed_height)
    if min_width is not None:
        field.setMinimumWidth(min_width)
    finalize_date_edit(field)
