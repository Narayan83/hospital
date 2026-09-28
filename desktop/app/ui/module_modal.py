"""Open HMS modules in a modal dialog (used by screen shortcuts)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.controllers.patient_controller import PatientController
from app.session import get_session
from app.ui.module_registry import MODULE_ALIASES
from app.ui.module_pages import create_module_widget
from app.ui.navigation import make_shortcut_navigator
from app.ui.styles import apply_form_field_style
from app.ui.table_utils import apply_resizable_columns

if TYPE_CHECKING:
    from app.api_client.client import ApiClient


def _resolve_api(parent: QWidget, api: ApiClient | None) -> ApiClient | None:
    if api is not None:
        return api
    if hasattr(parent, "api"):
        return parent.api
    window = parent.window()
    if hasattr(window, "api"):
        return window.api
    return None


def open_module_modal(
    module_id: str,
    *,
    parent: QWidget,
    api: ApiClient | None = None,
    on_navigate: Callable[[str], None] | None = None,
    before_show: Callable[[QWidget], None] | None = None,
    title: str | None = None,
    size: tuple[int, int] = (1150, 760),
) -> None:
    module_id = MODULE_ALIASES.get(module_id, module_id)
    resolved_api = _resolve_api(parent, api)
    if resolved_api is None:
        QMessageBox.warning(parent, "Navigation", "Unable to open this screen.")
        return

    utility_modules = {"profile", "settings", "notifications"}
    allowed = get_session().allowed_menu_codes()
    if module_id not in utility_modules and module_id not in allowed:
        QMessageBox.warning(parent, "Access Denied", f"You do not have access to '{module_id}'.")
        return

    shortcut_navigate = make_shortcut_navigator(parent)
    controller = PatientController(resolved_api)
    widget = create_module_widget(
        module_id,
        api=resolved_api,
        controller=controller,
        on_navigate=shortcut_navigate,
    )
    if widget is None:
        QMessageBox.warning(parent, "Navigation", f"Module '{module_id}' is not available.")
        return

    if before_show is not None:
        before_show(widget)

    menu = get_session().get_menu(module_id)
    dialog_title = title or (menu["label"] if menu else module_id.replace("_", " ").title())
    if module_id == "diagnose_management":
        dialog_title = "Discharge Summary"

    dialog = QDialog(parent)
    dialog.setWindowTitle(dialog_title)
    dialog.setModal(True)
    screen = dialog.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        dialog.setMaximumSize(max(640, avail.width() - 40), max(480, avail.height() - 40))
        dialog.resize(min(size[0], avail.width() - 80), min(size[1], avail.height() - 80))
    else:
        dialog.resize(*size)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(8, 8, 8, 8)

    widget.setMinimumHeight(0)
    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(widget)
    layout.addWidget(scroll, stretch=1)

    apply_form_field_style(widget)
    apply_resizable_columns(widget)

    if hasattr(widget, "refresh"):
        widget.refresh()

    close_row = QHBoxLayout()
    close_row.addStretch()
    close_btn = QPushButton("Close")
    close_btn.setMinimumWidth(120)
    close_btn.setAutoDefault(False)
    close_btn.setDefault(False)
    close_btn.clicked.connect(dialog.reject)
    close_row.addWidget(close_btn)
    layout.addLayout(close_row)
    for button in dialog.findChildren(QPushButton):
        button.setAutoDefault(False)
        button.setDefault(False)

    dialog.exec()
