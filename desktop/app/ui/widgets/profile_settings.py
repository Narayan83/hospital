from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.session import get_session


class ProfileWidget(QWidget):
    logout_requested = Signal()

    def __init__(self):
        super().__init__()
        session = get_session()
        layout = QVBoxLayout(self)
        heading = QLabel("Profile")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        layout.addWidget(QLabel(f"Name: {session.full_name}"))
        layout.addWidget(QLabel(f"Email: {session.email}"))
        layout.addWidget(QLabel(f"Roles: {', '.join(session.roles) or 'None'}"))
        logout_btn = QPushButton("Logout")
        logout_btn.setMaximumWidth(120)
        logout_btn.clicked.connect(self.logout_requested.emit)
        layout.addWidget(logout_btn)
        layout.addStretch()


class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Application settings will be configured here."))
        layout.addStretch()


class NotificationsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Notifications")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Your recent notifications will appear here."))
        layout.addStretch()
