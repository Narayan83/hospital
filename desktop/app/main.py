import sys
import traceback

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.hms_env import apply_install_config, resolve_config_summary
from app.perf_log import end_flow, init_app_log, log_exception, log_info, step
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow
from app.ui.styles import apply_global_theme


def _show_fatal(message: str, log_path: str | None = None) -> None:
    text = message
    if log_path:
        text = f"{message}\n\nLog file:\n{log_path}"
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "HMS Desktop — Startup Error", text)
    except Exception:
        print(text, file=sys.stderr, flush=True)


def main() -> int:
    log_path = None
    try:
        # Logs first — even if config/API setup fails, clients get a file to open.
        log_path = str(init_app_log())
        apply_install_config()
        summary = resolve_config_summary()
        log_info("Config loaded", **summary)

        app = QApplication(sys.argv)
        app.setApplicationName("Hospital Management System")
        app.setOrganizationName("HMS")
        app.setFont(QFont("Segoe UI", 10))
        apply_global_theme(app)

        login = LoginWindow()
        main_window: MainWindow | None = None

        def show_login() -> None:
            nonlocal main_window
            if main_window is not None:
                main_window.close()
                main_window.deleteLater()
                main_window = None
            login.email.setFocus()
            login.show()
            login.raise_()
            login.activateWindow()

        def on_login_success() -> None:
            nonlocal main_window
            step("Creating MainWindow")
            login.hide()
            step("Login window hidden")
            main_window = MainWindow()
            main_window.logout_requested.connect(show_login)
            step("MainWindow.showMaximized()")
            main_window.showMaximized()
            QApplication.processEvents()
            step("processEvents after show")
            end_flow("Main window visible")

        login.login_success.connect(on_login_success)
        login.show()
        log_info("Login window shown")
        return app.exec()
    except Exception as exc:
        path = log_exception("Desktop startup failed", exc)
        _show_fatal(
            "HMS Desktop could not start.\n\n"
            f"{exc}\n\n"
            "On a client PC, open config\\hms.env and set:\n"
            "  BASE_URL=http://SERVER_IP:8010\n"
            "  UPDATE_PATH=\\\\SERVER-PC\\HMSUpdates\n"
            "Then run Start HMS Desktop again.",
            str(path),
        )
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise
