"""Helpers for HMS data tables — drag-resize with sensible initial widths."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableView, QTableWidget

# Preferred starting widths by role (user can still drag-resize).
_WIDTH_CHECKBOX = 36
_WIDTH_ACTION = 78
_WIDTH_NUMBER = 90
_WIDTH_SHORT = 80
_WIDTH_CODE = 110
_WIDTH_PHONE = 120
_WIDTH_TEXT = 180

_ACTION_KEYS = frozenset({"action", "actions", "edit", "ops", "options"})
_NUMBER_KEYS = frozenset(
    {
        "age",
        "qty",
        "quantity",
        "rate",
        "amount",
        "price",
        "sort",
        "paid",
        "balance",
        "slno",
        "sl",
        "no",
        "token",
        "count",
        "total",
        "net",
        "discount",
        "days",
        "years",
    }
)
_CODE_KEYS = frozenset(
    {
        "code",
        "id",
        "patient id",
        "sex",
        "gender",
        "status",
        "pin",
        "type",
        "unit",
        "session",
    }
)
_PHONE_KEYS = frozenset({"mobile", "phone", "contact"})
_CHECKBOX_KEYS = frozenset({"add", "select", "sel", "✓", "☑"})
_SHORT_KEYS = frozenset({"category", "cat"})


def _normalize_header(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _header_label(table: QTableWidget | QTableView, col: int) -> str:
    if isinstance(table, QTableWidget):
        item = table.horizontalHeaderItem(col)
        return _normalize_header(item.text() if item is not None else "")
    model = table.model()
    if model is None:
        return ""
    raw = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
    return _normalize_header(str(raw) if raw is not None else "")


def _kind_from_label(label: str) -> str:
    if not label or label in _CHECKBOX_KEYS:
        return "checkbox"
    if label in _ACTION_KEYS or label.endswith(" action"):
        return "action"
    if label in _SHORT_KEYS or label.endswith(" category"):
        return "short"
    if label in _NUMBER_KEYS or label.endswith(" amount") or label.endswith(" rate"):
        return "number"
    if label in _PHONE_KEYS or "mobile" in label or "phone" in label:
        return "phone"
    if label in _CODE_KEYS or label.endswith(" id") or label.endswith(" code"):
        return "code"
    # Short numeric-looking headers
    if label in {"#", "sr", "s.no", "s no"}:
        return "number"
    return "text"


def _preferred_width(kind: str) -> int:
    return {
        "checkbox": _WIDTH_CHECKBOX,
        "action": _WIDTH_ACTION,
        "number": _WIDTH_NUMBER,
        "short": _WIDTH_SHORT,
        "code": _WIDTH_CODE,
        "phone": _WIDTH_PHONE,
        "text": _WIDTH_TEXT,
    }.get(kind, _WIDTH_TEXT)


def _column_kinds(table: QTableWidget | QTableView, column_count: int) -> list[str]:
    override = table.property("hmsColumnKinds")
    if isinstance(override, (list, tuple)) and len(override) == column_count:
        return [str(k) for k in override]

    header = table.horizontalHeader()
    kinds: list[str] = []
    for col in range(column_count):
        # Preserve tiny fixed checkbox / add columns.
        if (
            header is not None
            and header.sectionResizeMode(col) == QHeaderView.ResizeMode.Fixed
            and header.sectionSize(col) <= 48
        ):
            kinds.append("checkbox")
            continue
        kinds.append(_kind_from_label(_header_label(table, col)))
    return kinds


def _pick_stretch_column(kinds: list[str], table: QTableWidget | QTableView) -> int | None:
    override = table.property("hmsStretchColumn")
    if override is not None:
        try:
            idx = int(override)
            if 0 <= idx < len(kinds):
                return idx
        except (TypeError, ValueError):
            pass

    for preferred in ("text", "phone", "code"):
        for col, kind in enumerate(kinds):
            if kind == preferred:
                return col
    for col, kind in enumerate(kinds):
        if kind not in {"checkbox", "action", "number", "short"}:
            return col
    return None


def enable_column_resize(table: QTableWidget | QTableView) -> None:
    """Interactive drag-resize with text-friendly widths (Action/Amount never steal space)."""
    if table.property("hmsSkipColumnResize"):
        return

    header = table.horizontalHeader()
    if header is None:
        return

    if isinstance(table, QTableWidget):
        column_count = table.columnCount()
    else:
        model = table.model()
        column_count = model.columnCount() if model is not None else 0

    if column_count <= 0:
        return

    kinds = _column_kinds(table, column_count)
    header.setMinimumSectionSize(48)
    header.setStretchLastSection(False)
    # Allow drag-reorder left/right; Stretch mode blocks reliable resize handles.
    header.setSectionsMovable(True)
    if hasattr(header, "setFirstSectionMovable"):
        header.setFirstSectionMovable(True)

    for col, kind in enumerate(kinds):
        if kind == "checkbox":
            # Keep fixed narrow checkbox / Add columns.
            if header.sectionResizeMode(col) != QHeaderView.ResizeMode.Fixed:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(col, _WIDTH_CHECKBOX)
            continue
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        current = header.sectionSize(col)
        preferred = _preferred_width(kind)
        # Seed sensible widths: text/name wider, numbers/action/category compact.
        if kind in {"action", "number", "short"}:
            header.resizeSection(col, preferred)
        elif kind in {"code", "phone"} and current < preferred:
            header.resizeSection(col, preferred)
        elif kind == "text" and current < preferred:
            header.resizeSection(col, preferred)
        elif current < 40 or current > preferred * 3:
            header.resizeSection(col, preferred)

    # Stretch fights Interactive drag-resize; skip unless a screen opts in.
    if not table.property("hmsNoStretch"):
        stretch_col = _pick_stretch_column(kinds, table)
        if stretch_col is not None and kinds[stretch_col] not in {
            "checkbox",
            "action",
            "number",
            "short",
        }:
            header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)

    table.setProperty("hmsColumnsSized", True)


def apply_resizable_columns(root) -> None:
    """Enable smart column resize on every table under *root*."""
    for table in root.findChildren(QTableWidget):
        enable_column_resize(table)
    for table in root.findChildren(QTableView):
        enable_column_resize(table)
