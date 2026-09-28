from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from app.session import get_session
from app.ui.flow_layout import FlowLayout
from app.ui.styles import BTN_DANGER, BTN_ICON, BORDER, INPUT_BG, SURFACE, TEXT, TEXT_MUTED


class TopHeader(QWidget):
    notifications_clicked = Signal()
    settings_clicked = Signal()
    profile_clicked = Signal()
    logout_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(f"background: {SURFACE}; border-bottom: 2px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.setContentsMargins(0, 0, 0, 0)

        breadcrumb = QLabel("HMS")
        breadcrumb.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {TEXT_MUTED};"
            " letter-spacing: 0.5px; text-transform: uppercase;"
        )
        self.breadcrumb_label = breadcrumb
        title_col.addWidget(breadcrumb)

        self.title_label = QLabel("Dashboard")
        self.title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {TEXT};")
        title_col.addWidget(self.title_label)
        layout.addLayout(title_col)

        # Wrapping host so page shortcuts move to the next line on narrow widths.
        self._actions_host = QWidget()
        self._actions_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._actions_layout = FlowLayout(self._actions_host, margin=0, h_spacing=6, v_spacing=4)
        self._actions_host.hide()
        layout.addWidget(self._actions_host, stretch=1)

        session = get_session()

        for attr, signal, icon, tip in (
            ("notify_btn", self.notifications_clicked, "🔔", "Notifications"),
            ("settings_btn", self.settings_clicked, "⚙", "Settings"),
            ("profile_btn", self.profile_clicked, "👤", "Profile"),
        ):
            btn = QPushButton(icon)
            btn.setFixedSize(34, 34)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(BTN_ICON)
            btn.clicked.connect(signal.emit)
            setattr(self, attr, btn)
            if attr == "settings_btn" and not session.is_admin_user_type():
                btn.hide()
            layout.addWidget(btn)

        user_card = QFrame()
        user_card.setStyleSheet(
            f"QFrame {{ background: {INPUT_BG}; border: 2px solid {BORDER}; border-radius: 8px; }}"
        )
        user_layout = QHBoxLayout(user_card)
        user_layout.setContentsMargins(10, 4, 12, 4)
        user_layout.setSpacing(8)

        avatar = QLabel(self._initials(session.full_name or session.email or "U"))
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background: #1e40af; color: white; border-radius: 16px;"
            " font-size: 12px; font-weight: 700;"
        )
        user_layout.addWidget(avatar)

        user_info = QVBoxLayout()
        user_info.setSpacing(0)
        name_lbl = QLabel(session.full_name or "User")
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #0f172a; background: transparent; border: none;"
        )
        user_info.addWidget(name_lbl)
        email_lbl = QLabel(session.email or "")
        email_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent; border: none;")
        user_info.addWidget(email_lbl)
        user_layout.addLayout(user_info)
        layout.addWidget(user_card)

        if session.full_name:
            self.profile_btn.setToolTip(f"{session.full_name}\n{session.email}")

        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setToolTip("Sign out and return to login")
        self.logout_btn.setStyleSheet(BTN_DANGER)
        self.logout_btn.clicked.connect(self.logout_clicked.emit)
        layout.addWidget(self.logout_btn)

    @staticmethod
    def _initials(name: str) -> str:
        parts = [p for p in name.replace("@", " ").split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def set_hospital_name(self, name: str) -> None:
        short = name if len(name) <= 24 else f"{name[:22]}…"
        self.breadcrumb_label.setText(short)
        self.breadcrumb_label.setToolTip(name)

    def set_page_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_page_actions(self, widget: QWidget | None) -> None:
        while self._actions_layout.count():
            item = self._actions_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()
        if widget is None:
            self._actions_host.hide()
            self.updateGeometry()
            return
        # Prefer adopting individual buttons so FlowLayout can wrap them.
        nested = widget.layout()
        if nested is not None and nested.count() > 0:
            buttons: list[QWidget] = []
            while nested.count():
                item = nested.takeAt(0)
                child = item.widget()
                if child is not None:
                    buttons.append(child)
            widget.deleteLater()
            for btn in buttons:
                self._actions_layout.addWidget(btn)
        else:
            self._actions_layout.addWidget(widget)
        self._actions_host.show()
        self.updateGeometry()

    def clear_page_actions(self) -> None:
        self.set_page_actions(None)
