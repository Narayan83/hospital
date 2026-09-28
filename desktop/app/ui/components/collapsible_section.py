from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.ui.styles import BORDER, PRIMARY, PRIMARY_DARK, SURFACE


class CollapsibleSection(QWidget):
    """Section with a clickable header that expands or collapses its body."""

    def __init__(self, title: str, *, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._expanded = expanded

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 6)
        root.setSpacing(0)

        header_frame = QFrame()
        header_frame.setObjectName("collapsibleHeader")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self.toggle)
        self._refresh_toggle_label()
        header_layout.addWidget(self._toggle_btn)
        header_layout.addStretch()

        self._body = QWidget()
        self.content_layout = QVBoxLayout(self._body)
        self.content_layout.setContentsMargins(12, 8, 8, 8)
        self._body.setVisible(expanded)

        root.addWidget(header_frame)
        root.addWidget(self._body)

        self.setStyleSheet(
            f"""
            QFrame#collapsibleHeader {{
                background: {SURFACE};
                border: 2px solid {BORDER};
                border-radius: 6px;
            }}
            QFrame#collapsibleHeader QPushButton {{
                text-align: left;
                font-weight: 600;
                color: {PRIMARY_DARK};
                border: none;
                padding: 4px 2px;
                background: transparent;
            }}
            QFrame#collapsibleHeader QPushButton:hover {{
                color: {PRIMARY};
            }}
            """
        )

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._refresh_toggle_label()

    def set_title(self, title: str) -> None:
        self._title = title
        self._refresh_toggle_label()

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _refresh_toggle_label(self) -> None:
        arrow = "▼" if self._expanded else "▶"
        self._toggle_btn.setText(f"{arrow}  {self._title}")
