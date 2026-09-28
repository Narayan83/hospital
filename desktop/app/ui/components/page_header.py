from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.styles import PAGE_TITLE, SUBTITLE


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setStyleSheet(PAGE_TITLE)
        layout.addWidget(self._title)

        self._subtitle = QLabel(subtitle)
        self._subtitle.setStyleSheet(SUBTITLE)
        self._subtitle.setVisible(bool(subtitle))
        layout.addWidget(self._subtitle)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle.setText(subtitle)
        self._subtitle.setVisible(bool(subtitle))
