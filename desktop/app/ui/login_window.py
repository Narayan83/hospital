from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import get_config
from app.controllers.auth_controller import AuthController
from app.hms_env import resolve_config_summary
from app.perf_log import begin_flow, end_flow, log_dir, log_info, step
from app.ui.styles import BG, BTN_PRIMARY, INPUT_BG, PRIMARY, PRIMARY_DARK, SURFACE, TEXT_MUTED, apply_form_field_style


class LoginWindow(QWidget):
    login_success = Signal()

    def __init__(self):
        super().__init__()
        self.controller = AuthController()
        self.setWindowTitle("HMS — Sign In")
        self.setFixedSize(780, 520)
        self._setup_ui()
        apply_form_field_style(self)
        self._refresh_connection_status()

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        brand = QFrame()
        brand.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0.3, y2:1,
                    stop:0 {PRIMARY_DARK}, stop:1 {PRIMARY});
            }}
            """
        )
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(48, 48, 48, 48)
        brand_layout.setSpacing(16)

        icon = QLabel("🏥")
        icon.setStyleSheet("font-size: 48px; background: transparent;")
        brand_layout.addWidget(icon)

        brand_title = QLabel("HMS")
        brand_title.setStyleSheet(
            "font-size: 32px; font-weight: 800; color: white;"
            " letter-spacing: 2px; background: transparent;"
        )
        brand_layout.addWidget(brand_title)

        brand_sub = QLabel("Hospital\nManagement System")
        brand_sub.setStyleSheet(
            "font-size: 16px; font-weight: 500; color: #93c5fd;"
            " line-height: 1.4; background: transparent;"
        )
        brand_layout.addWidget(brand_sub)
        brand_layout.addStretch()

        tagline = QLabel("Patients · Billing · Pharmacy · Records")
        tagline.setStyleSheet("font-size: 12px; color: #60a5fa; background: transparent;")
        tagline.setWordWrap(True)
        brand_layout.addWidget(tagline)
        root.addWidget(brand, stretch=5)

        form_panel = QFrame()
        form_panel.setStyleSheet(f"background: {SURFACE};")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(56, 64, 56, 64)
        form_layout.setSpacing(0)

        title = QLabel("Welcome back")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #0f172a;")
        form_layout.addWidget(title)

        subtitle = QLabel("Sign in to your account to continue")
        subtitle.setStyleSheet("font-size: 14px; color: #64748b; margin-bottom: 28px;")
        form_layout.addWidget(subtitle)

        email_label = QLabel("Email address")
        email_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        form_layout.addWidget(email_label)
        self.email = QLineEdit()
        self.email.setPlaceholderText("admin@admin.com")
        self.email.setText("admin@admin.com")
        self.email.setMinimumHeight(40)
        form_layout.addWidget(self.email)
        form_layout.addSpacing(16)

        pwd_label = QLabel("Password")
        pwd_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        form_layout.addWidget(pwd_label)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Enter your password")
        self.password.setText("admin123")
        self.password.setMinimumHeight(40)
        form_layout.addWidget(self.password)
        form_layout.addSpacing(28)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet(
            BTN_PRIMARY.replace("padding: 8px 18px", "padding: 10px 18px")
            + "QPushButton { font-size: 14px; }"
        )
        self.login_btn.clicked.connect(self._on_login)
        form_layout.addWidget(self.login_btn)
        form_layout.addSpacing(10)

        self.server_label = QLabel("")
        self.server_label.setWordWrap(True)
        self.server_label.setStyleSheet("font-size: 11px; color: #475569;")
        form_layout.addWidget(self.server_label)

        self.log_label = QLabel("")
        self.log_label.setWordWrap(True)
        self.log_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log_label.setStyleSheet("font-size: 10px; color: #64748b;")
        form_layout.addWidget(self.log_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px; color: #64748b;")
        form_layout.addWidget(self.status_label)

        retry_btn = QPushButton("Test Server Connection")
        retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        retry_btn.clicked.connect(self._refresh_connection_status)
        form_layout.addWidget(retry_btn)

        open_log_btn = QPushButton("Open Log Folder")
        open_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_log_btn.clicked.connect(self._open_log_folder)
        form_layout.addWidget(open_log_btn)
        form_layout.addStretch()

        footer = QLabel("© Hospital Management System")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #94a3b8;")
        form_layout.addWidget(footer)
        root.addWidget(form_panel, stretch=6)

        self.password.returnPressed.connect(self._on_login)
        self.email.returnPressed.connect(self._on_login)

    def _open_log_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        folder = log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _refresh_connection_status(self) -> None:
        cfg = get_config()
        summary = resolve_config_summary()
        log_path = log_dir() / "desktop.log"
        self.server_label.setText(f"Server: {cfg.api_url}")
        self.log_label.setText(f"Logs: {log_path}")
        ok, detail = self.controller.check_connection()
        log_info("Connection check", ok=ok, detail=detail, **summary)
        if ok:
            self.status_label.setStyleSheet("font-size: 11px; color: #15803d;")
            self.status_label.setText("Connected to server.")
        else:
            self.status_label.setStyleSheet("font-size: 11px; color: #b91c1c;")
            self.status_label.setText(
                "Cannot reach server. On a client PC edit config\\hms.env:\n"
                "BASE_URL=http://SERVER_IP:8010\n"
                f"Detail: {detail}"
            )

    def _on_login(self) -> None:
        begin_flow("login_click_to_main_window")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        QApplication.processEvents()
        try:
            step("UI updated — calling login API")
            cfg = get_config()
            log_info("Login attempt", api_url=cfg.api_url, email=self.email.text().strip())
            ok, detail = self.controller.check_connection()
            if not ok:
                message = (
                    f"Cannot connect to server:\n{cfg.api_url}\n\n"
                    f"{detail}\n\n"
                    "Client PC checklist:\n"
                    "1. Server HMS is running (Start HMS on server PC)\n"
                    "2. Edit config\\hms.env → BASE_URL=http://SERVER_IP:8010\n"
                    "3. Windows Firewall allows port 8010 on the server\n"
                    f"4. See log: {log_dir() / 'desktop.log'}"
                )
                log_info("Login blocked — server unreachable", detail=detail)
                QMessageBox.warning(self, "Server Not Reachable", message)
                end_flow("FAILED — server unreachable")
                self._refresh_connection_status()
                return
            error = self.controller.login(self.email.text(), self.password.text())
            if error:
                log_info("Login failed", error=error)
                QMessageBox.warning(
                    self,
                    "Login Failed",
                    f"{error}\n\nServer: {cfg.api_url}\nLog: {log_dir() / 'desktop.log'}",
                )
                end_flow("FAILED — login error")
                return
            step("Login controller finished — opening main window")
            self.login_success.emit()
        finally:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign In")

    def closeEvent(self, event) -> None:
        self.controller.close()
        super().closeEvent(event)
