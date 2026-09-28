from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient
from app.controllers.patient_controller import PatientController
from app.perf_log import step
from app.session import get_session, hospital_display_name
from app.ui.module_lifecycle import deactivate_module
from app.ui.styles import BG, apply_form_field_style
from app.ui.widgets.dashboard import DashboardWidget
from app.ui.widgets.module_placeholder import ModulePlaceholderWidget
from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.top_header import TopHeader

from app.ui.module_registry import MODULE_ALIASES


class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self):
        step("MainWindow.__init__ start")
        super().__init__()
        self.api = ApiClient()
        self.controller = PatientController(self.api)
        self._pages: dict[str, QWidget] = {}
        self._module_refresh_at: dict[str, float] = {}
        self._current_module: str | None = None
        self._logging_out = False
        self.setWindowTitle(hospital_display_name())
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.setMinimumSize(
                min(1100, max(900, available.width() - 80)),
                min(700, max(600, available.height() - 80)),
            )
        else:
            self.setMinimumSize(1100, 700)
        self._setup_ui()
        step("MainWindow.__init__ done")

    def _setup_ui(self) -> None:
        step("MainWindow._setup_ui start")
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        step("Sidebar build start")
        self.sidebar = Sidebar()
        self.sidebar.ensure_expanded()
        self.sidebar.module_selected.connect(self._on_module_selected)
        root.addWidget(self.sidebar)
        step("Sidebar build done")

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.header = TopHeader()
        self.header.notifications_clicked.connect(lambda: self._show_module("notifications"))
        self.header.settings_clicked.connect(lambda: self._show_module("hospital_profile"))
        self.header.profile_clicked.connect(lambda: self._show_module("profile"))
        self.header.logout_clicked.connect(self._on_logout)
        self.header.set_hospital_name(hospital_display_name())
        right.addWidget(self.header)

        content = QWidget()
        content.setStyleSheet(f"background: {BG};")
        content_layout = QVBoxLayout(content)
        from app.ui.responsive_layout import get_density

        _m = get_density().content_margin
        content_layout.setContentsMargins(_m, max(6, _m - 2), _m, max(6, _m - 2))
        content_layout.setSpacing(0)

        from app.ui.widgets.menu_shortcut_bar import MenuShortcutBar

        self.shortcut_bar = MenuShortcutBar(self.api)
        self.shortcut_bar.module_requested.connect(self._open_pinned_module)
        self.shortcut_bar.configure_requested.connect(self._open_shortcut_setup)
        self.shortcut_bar.setVisible(False)
        content_layout.addWidget(self.shortcut_bar)

        self.stack = QStackedWidget()
        step("Dashboard widget build start")
        self._add_page("dashboard", DashboardWidget(self.api))
        dashboard = self._pages["dashboard"]
        if hasattr(dashboard, "module_requested"):
            dashboard.module_requested.connect(self._show_module)
        step("Dashboard widget build done")
        content_layout.addWidget(self.stack)
        right.addWidget(content, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        root.addWidget(right_widget, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        session = get_session()
        self.status_bar.showMessage(f"Ready — logged in as {session.full_name}")

        step("Show dashboard start")
        self.apply_hospital_branding()
        self._show_module("dashboard")
        step("Show dashboard done")
        step("MainWindow._setup_ui done")

    def _create_page(self, module_id: str) -> QWidget | None:
        step(f"Lazy import/build page: {module_id}")
        from app.ui.module_pages import create_module_widget

        return create_module_widget(
            module_id,
            api=self.api,
            controller=self.controller,
            on_navigate=self._show_module,
            logout_callback=self._on_logout,
        )

    def _add_page(self, code: str, widget: QWidget) -> None:
        apply_form_field_style(widget)
        self._pages[code] = widget
        self.stack.addWidget(widget)

    def _resolve_page(self, module_id: str) -> QWidget | None:
        module_id = MODULE_ALIASES.get(module_id, module_id)
        widget = self._pages.get(module_id)
        if widget:
            return widget

        widget = self._create_page(module_id)
        if widget:
            self._add_page(module_id, widget)
            return widget

        menu = get_session().get_menu(module_id)
        if not menu:
            return None

        widget = ModulePlaceholderWidget(
            code=module_id,
            label=menu.get("label", module_id.replace("_", " ").title()),
            legacy_form=menu.get("legacy_form"),
            parameters=menu.get("parameters"),
        )
        self._add_page(module_id, widget)
        return widget

    def _needs_refresh(self, module_id: str) -> bool:
        cache = get_session().cache
        if not cache.loaded:
            return True
        return self._module_refresh_at.get(module_id, 0) < cache.loaded_at

    def _deferred_refresh(self, module_id: str, widget: QWidget) -> None:
        if self._current_module != module_id:
            return
        if hasattr(widget, "refresh"):
            widget.refresh()
            self._module_refresh_at[module_id] = get_session().cache.loaded_at

    def _deactivate_module(self, module_id: str | None) -> None:
        if not module_id:
            return
        deactivate_module(module_id, self._pages.get(module_id))

    def apply_hospital_branding(self) -> None:
        self.sidebar.apply_hospital_branding()
        self.header.set_hospital_name(hospital_display_name())
        dashboard = self._pages.get("dashboard")
        if dashboard and hasattr(dashboard, "apply_hospital_branding"):
            dashboard.apply_hospital_branding()
        if self._current_module:
            menu = get_session().get_menu(self._current_module)
            title = menu["label"] if menu else self._current_module.replace("_", " ").title()
            if self._current_module == "diagnose_management":
                title = "Discharge Summary"
            self.setWindowTitle(f"{hospital_display_name()} - {title}")

    def _open_pinned_module(self, module_id: str) -> None:
        from app.ui.navigation import navigate_shortcut

        navigate_shortcut(module_id, parent=self, api=self.api, on_navigate=self._show_module)

    def _open_shortcut_setup(self, host_code: str) -> None:
        self._show_module("dashboard_shortcut_setup")
        widget = self._pages.get("dashboard_shortcut_setup")
        if widget and hasattr(widget, "set_host"):
            widget.set_host(host_code)

    def _sync_shortcut_bar(self, module_id: str) -> None:
        hidden = module_id in {"dashboard", "dashboard_shortcut_setup", "print_template_designer"}
        self.shortcut_bar.setVisible(not hidden)
        if not hidden:
            self.shortcut_bar.set_host(module_id)

    def _show_module(self, module_id: str) -> None:
        module_id = MODULE_ALIASES.get(module_id, module_id)
        previous_module = self._current_module
        if previous_module and previous_module != module_id:
            self._deactivate_module(previous_module)

        utility_modules = {"profile", "settings", "notifications"}
        allowed = get_session().allowed_menu_codes()
        if module_id not in utility_modules and module_id not in allowed:
            self.status_bar.showMessage(f"Access denied for '{module_id}'.")
            return

        widget = self._resolve_page(module_id)
        if not widget:
            self.status_bar.showMessage(f"Module '{module_id}' is not available.")
            return

        menu = get_session().get_menu(module_id)
        title = menu["label"] if menu else module_id.replace("_", " ").title()
        # Backward-compat: legacy menu code was created as "diagnose_management".
        # Keep UX aligned to "Discharge Summary" regardless of stored menu label.
        if module_id == "diagnose_management":
            title = "Discharge Summary"

        self._current_module = module_id
        self.sidebar.reveal_module(module_id)
        self.stack.setCurrentWidget(widget)
        self._sync_shortcut_bar(module_id)
        self.header.set_page_title(title)
        if hasattr(widget, "build_header_actions"):
            actions = widget.build_header_actions()
            if actions is not None:
                self.header.set_page_actions(actions)
            else:
                self.header.clear_page_actions()
        else:
            self.header.clear_page_actions()
        self.setWindowTitle(f"{hospital_display_name()} - {title}")
        self.status_bar.showMessage(title)

        refresh_modules = {
            "dashboard",
            "modify_bill",
            "opd_bill",
            "opd_bill_reprint",
            "opd_bill_modification",
            "ipd_bill_modification",
            "ipd_bill_reprint",
            "in_patient_admission",
            "in_patient_discharge",
            "diagnose_management",
            "ipd_bill",
            "pathology_bill",
            "pathology_bill_reprint",
            "pathology_bill_cancel",
            "pathology_bill_modification",
            "pathology_work_list",
            "patient_history_opd",
            "patient_list",
            "scanning_patient_documents",
            "unit_creation",
            "parameter_mapping",
            "normal_range_creation",
            "custom_template_creation",
            "service_creation_pathology",
            "letter_master",
            "print_master",
            "ledger_master",
            "cashbook",
            "short_bill_master",
            "single_service_opd_setup",
            "scan_bill",
            "xray_bill",
            "observation_bill",
            "immunization_bill",
            "form_3c_report",
            "user_wise_cash_transaction_report",
            "doctor_wise_collection_report",
            "pathology_doctor_wise_collection_report",
            "hospital_profile",
            "payment_mode_creation",
            "medical_shop",
            "medicine_master",
            "surgicals_master",
            "disposables_master",
            "consumables_master",
            "implants_master",
            "manufacturer_master",
            "marketing_agency_master",
            "distributors_master",
            "drug_category_master",
            "medicine_group_creation",
            "supplier_master",
            "assign_medicine_to_group",
            "medicine_sale_bill",
            "medicine_purchase_bill_109",
            "sales_register",
            "sales_summary",
            "schedule_h_drug_report",
            "consolidated_stock_report",
        }
        if hasattr(widget, "refresh") and (
            module_id in refresh_modules
            or module_id.startswith("sso_")
            or module_id.startswith("sbt_")
            or self._needs_refresh(module_id)
        ):
            QTimer.singleShot(0, lambda: self._deferred_refresh(module_id, widget))

    def _on_module_selected(self, module_id: str) -> None:
        self._show_module(module_id)

    def _on_logout(self) -> None:
        from app.controllers.auth_controller import AuthController

        self._deactivate_module(self._current_module)
        self._logging_out = True
        AuthController(self.api).logout()
        self.logout_requested.emit()
        self.close()

    def closeEvent(self, event) -> None:
        if not self._logging_out:
            reply = QMessageBox.question(
                self,
                "Exit HMS",
                "Close HMS Desktop?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.controller.close()
        self.api.close()
        if not self._logging_out:
            QApplication.instance().quit()
        super().closeEvent(event)
