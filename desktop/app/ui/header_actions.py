"""Shared header shortcut button bar that wraps on narrow screens."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from app.ui.flow_layout import FlowLayout
from app.ui.styles import HEADER_BTN_STYLE


def create_header_action_bar(
    actions: list[tuple[str, Callable[[], None]]],
    *,
    spacing: int = 6,
    button_style: str | None = None,
) -> QWidget:
    """Build a wrapping row of page shortcut buttons (full labels always readable)."""
    bar = QWidget()
    bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = FlowLayout(bar, margin=0, h_spacing=spacing, v_spacing=4)
    style = button_style or HEADER_BTN_STYLE
    for label, handler in actions:
        btn = QPushButton(label)
        btn.setStyleSheet(style)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(handler)
        layout.addWidget(btn)
    return bar
