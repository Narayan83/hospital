from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.session import get_session, set_hospital_profile
from app.ui.responsive_layout import get_density


class HospitalProfileWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._fields: list[QLineEdit] = []
        self._build_ui()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Global form styling caps inputs at 360px — force full-row width on Settings.
        self._force_wide_fields()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._force_wide_fields)

    def _force_wide_fields(self) -> None:
        for field in self._fields:
            field.setProperty("hmsAllowWide", True)
            field.setMaximumWidth(16777215)
            field.setMinimumWidth(0)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _build_ui(self) -> None:
        d = get_density()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        host = QWidget()
        scroll.setWidget(host)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(d.content_margin, d.content_margin, d.content_margin, d.content_margin)
        layout.setSpacing(d.section_spacing)

        heading = QLabel("Settings")
        heading.setStyleSheet(
            f"font-size: {max(16, d.font_size + 5)}px; font-weight: bold; color: #1e40af;"
        )
        layout.addWidget(heading)

        hint = QLabel(
            "Basic hospital configuration. The company name and address appear as the "
            "report heading on printouts. Pathology and medical shop bills can use "
            "their own names while keeping the same address/contact details."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: #64748b; font-size: {max(11, d.font_size - 1)}px;")
        layout.addWidget(hint)

        form_box = QGroupBox("Hospital / Company Details")
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form_box.setProperty("hmsExpandFormFields", True)
        grid = QGridLayout(form_box)
        grid.setVerticalSpacing(d.form_v_spacing)
        grid.setHorizontalSpacing(d.form_h_spacing)
        grid.setContentsMargins(10, 12, 10, 10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Company / hospital name shown on report headings")
        self.pathology_name = QLineEdit()
        self.pathology_name.setPlaceholderText("Name shown at top of pathology bills/reports")
        self.medical_shop_name = QLineEdit()
        self.medical_shop_name.setPlaceholderText("Name shown at top of medical shop bills")
        self.address_line1 = QLineEdit()
        self.address_line1.setPlaceholderText("Address line 1")
        self.address_line2 = QLineEdit()
        self.address_line2.setPlaceholderText("Address line 2")
        self.address_line3 = QLineEdit()
        self.address_line3.setPlaceholderText("Address line 3")
        self.address_line4 = QLineEdit()
        self.address_line4.setPlaceholderText("Address line 4")
        self.city = QLineEdit()
        self.city.setPlaceholderText("City")
        self.state = QLineEdit()
        self.state.setPlaceholderText("State")
        self.pin_code = QLineEdit()
        self.phone = QLineEdit()
        self.mobile = QLineEdit()
        self.mobile.setMaxLength(100)
        self.mobile.setPlaceholderText("Mobile")
        self.email = QLineEdit()
        self.website = QLineEdit()
        self.website.setPlaceholderText("Website")
        self.gstin = QLineEdit()
        self.gstin.setPlaceholderText("GSTIN")
        self.software_id = QLineEdit()
        self.software_id.setPlaceholderText("Software ID (enter manually)")

        rows = (
            ("Company / Hospital Name *", self.name),
            ("Pathology Name", self.pathology_name),
            ("Medical Shop Name", self.medical_shop_name),
            ("Address 1", self.address_line1),
            ("Address 2", self.address_line2),
            ("Address 3", self.address_line3),
            ("Address 4", self.address_line4),
            ("City", self.city),
            ("State", self.state),
            ("PIN", self.pin_code),
            ("Phone", self.phone),
            ("Mobile", self.mobile),
            ("Email", self.email),
            ("Website", self.website),
            ("GSTIN", self.gstin),
            ("Software ID", self.software_id),
        )
        self._fields = [field for _, field in rows]
        for row, (label_text, field) in enumerate(rows):
            field.setProperty("hmsAllowWide", True)
            field.setMaximumWidth(16777215)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        if get_session().is_admin_user_type():
            self._build_danger_zone(layout)

        layout.addStretch(1)

    def _build_danger_zone(self, layout) -> None:
        danger_box = QGroupBox("Database Maintenance")
        danger_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        danger_box.setStyleSheet(
            "QGroupBox { border: 2px solid #fca5a5; border-radius: 8px; margin-top: 16px;"
            " font-weight: 600; color: #991b1b; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        danger_layout = QVBoxLayout(danger_box)
        info = QLabel(
            "Reset transactional data, or import from the old MySQL hospital software. "
            "Hospital information, users and menus are always kept on reset. "
            "Both tools require the maintenance password."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748b; font-size: 11px;")
        danger_layout.addWidget(info)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Reset Database…")
        clear_btn.setMaximumWidth(200)
        clear_btn.setStyleSheet(
            "QPushButton { background: #991b1b; color: white; border: none;"
            " border-radius: 6px; padding: 8px 18px; font-weight: 600; }"
            "QPushButton:hover { background: #b91c1c; }"
        )
        clear_btn.clicked.connect(self._open_clear_database)
        btn_row.addWidget(clear_btn)

        migrate_btn = QPushButton("Database Migration…")
        migrate_btn.setMaximumWidth(220)
        migrate_btn.setStyleSheet(
            "QPushButton { background: #1e3a5f; color: white; border: none;"
            " border-radius: 6px; padding: 8px 18px; font-weight: 600; }"
            "QPushButton:hover { background: #274b7a; }"
        )
        migrate_btn.clicked.connect(self._open_database_migration)
        btn_row.addWidget(migrate_btn)
        btn_row.addStretch()
        danger_layout.addLayout(btn_row)
        layout.addWidget(danger_box)

    def _open_clear_database(self) -> None:
        from app.ui.widgets.clear_database_dialog import ClearDatabaseDialog

        dialog = ClearDatabaseDialog(self.api, self)
        dialog.exec()

    def _open_database_migration(self) -> None:
        from app.ui.widgets.database_migration import DatabaseMigrationWidget

        # Open as a dialog-sized window so Settings stays available.
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Database Migration")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(DatabaseMigrationWidget(self.api, dialog))
        self._fill_content_area(dialog)
        dialog.exec()

    def _fill_content_area(self, dialog: QWidget) -> None:
        """Cover the main window area to the right of the left navigation pane."""
        from PySide6.QtCore import QPoint

        window = self.window()
        if window is None:
            dialog.resize(1100, 760)
            return
        sidebar = getattr(window, "sidebar", None)
        left = sidebar.width() if sidebar is not None else 0
        origin = window.mapToGlobal(QPoint(left, 0))
        dialog.setGeometry(
            origin.x(),
            origin.y(),
            max(760, window.width() - left),
            max(560, window.height()),
        )

    def refresh(self) -> None:
        try:
            profile = self.api.get_hospital_profile()
        except ApiError as exc:
            QMessageBox.warning(self, "Settings", str(exc))
            return
        self._load_form(profile)
        set_hospital_profile(profile)

    def _load_form(self, profile: dict) -> None:
        self.name.setText(profile.get("name") or "")
        self.pathology_name.setText(profile.get("pathology_name") or "")
        self.medical_shop_name.setText(profile.get("medical_shop_name") or "")
        self.address_line1.setText(profile.get("address_line1") or "")
        self.address_line2.setText(profile.get("address_line2") or "")
        self.address_line3.setText(profile.get("address_line3") or "")
        self.address_line4.setText(profile.get("address_line4") or "")
        self.city.setText(profile.get("city") or "")
        self.state.setText(profile.get("state") or "")
        self.pin_code.setText(profile.get("pin_code") or "")
        self.phone.setText(profile.get("phone") or "")
        self.mobile.setText(profile.get("mobile") or "")
        self.email.setText(profile.get("email") or "")
        self.website.setText(profile.get("website") or "")
        self.gstin.setText(profile.get("gstin") or "")
        self.software_id.setText(profile.get("software_id") or "")

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Company / hospital name is required.")
            return
        payload = {
            "name": name,
            "pathology_name": self.pathology_name.text().strip() or None,
            "medical_shop_name": self.medical_shop_name.text().strip() or None,
            "address_line1": self.address_line1.text().strip() or None,
            "address_line2": self.address_line2.text().strip() or None,
            "address_line3": self.address_line3.text().strip() or None,
            "address_line4": self.address_line4.text().strip() or None,
            "city": self.city.text().strip() or None,
            "state": self.state.text().strip() or None,
            "pin_code": self.pin_code.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "mobile": self.mobile.text().strip() or None,
            "email": self.email.text().strip() or None,
            "website": self.website.text().strip() or None,
            "gstin": self.gstin.text().strip() or None,
            "software_id": self.software_id.text().strip() or None,
        }
        try:
            profile = self.api.update_hospital_profile(payload)
        except ApiError as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self._load_form(profile)
        set_hospital_profile(profile)
        main_window = self.window()
        if main_window and hasattr(main_window, "apply_hospital_branding"):
            main_window.apply_hospital_branding()
        QMessageBox.information(
            self,
            "Saved",
            "Settings saved. Report headings will use the updated company name and address.",
        )
