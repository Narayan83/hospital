from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.styles import BORDER, PANEL_CARD, SURFACE, TEXT, TEXT_MUTED


class ModulePlaceholderWidget(QWidget):
    def __init__(self, code: str, label: str, legacy_form: str | None, parameters: str | None):
        super().__init__()
        self._code = code
        self._label = label
        self._legacy_form = legacy_form
        self._parameters = parameters
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(self._label)
        title.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {TEXT};")
        layout.addWidget(title)

        subtitle = QLabel("This module is planned and will be implemented in a future release.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        layout.addWidget(subtitle)

        details = [
            f"Menu code: {self._code}",
        ]
        if self._legacy_form:
            details.append(f"Legacy form (FoxPro): {self._legacy_form}")
        if self._parameters:
            details.append(f"Parameters: {self._parameters}")

        meta = QLabel("\n".join(details))
        meta.setWordWrap(True)
        meta.setStyleSheet(
            f"font-size: 13px; color: {TEXT_MUTED}; background: {SURFACE}; "
            f"border: 2px solid {BORDER}; border-radius: 8px; padding: 12px;"
        )
        layout.addWidget(meta)
        layout.addStretch()

    def refresh(self) -> None:
        pass
