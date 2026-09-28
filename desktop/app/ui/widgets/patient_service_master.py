from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.master_cache import refresh_patient_services_cache
from app.session import get_session


def _make_yn_combo(default_y: bool = False) -> QComboBox:
    combo = QComboBox()
    combo.addItem("N", False)
    combo.addItem("Y", True)
    combo.setCurrentIndex(1 if default_y else 0)
    combo.setMaximumWidth(70)
    return combo


def _yn_value(combo: QComboBox) -> bool:
    return bool(combo.currentData())


def _set_yn(combo: QComboBox, value: bool) -> None:
    combo.setCurrentIndex(1 if value else 0)


class PatientServiceMasterWidget(QWidget):
    MODE_CREATE = "Create"
    MODE_MODIFY = "Modify"
    MODE_DELETE = "Delete"

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._items: list[dict] = []
        self._doctors: list[dict] = []
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        from app.ui.responsive_layout import (
            configure_form_layout,
            get_density,
            paint_page_surface,
            wrap_widget_in_scroll,
        )
        from app.ui.styles import PAGE_TITLE, SUBTITLE
        from PySide6.QtWidgets import QSplitter

        d = get_density()
        paint_page_surface(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(d.content_margin, d.content_margin, d.content_margin, d.content_margin)
        layout.setSpacing(d.section_spacing)

        heading = QLabel("Patient Service Master")
        heading.setStyleSheet(PAGE_TITLE + " color: #1e40af;")
        layout.addWidget(heading)

        top = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([self.MODE_CREATE, self.MODE_MODIFY, self.MODE_DELETE])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top.addWidget(QLabel("Action"))
        top.addWidget(self.mode_combo)
        top.addStretch()
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setProperty("hmsSkipAutoSize", True)
        layout.addWidget(splitter, stretch=1)

        list_box = QGroupBox("Service List")
        list_layout = QVBoxLayout(list_box)
        list_layout.setSpacing(d.section_spacing)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by code or name — e.g. PS1, Registration…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_search)
        self._compact_field(self.search)
        search_row.addWidget(self.search, stretch=1)
        list_layout.addLayout(search_row)

        self.list_hint = QLabel("Click a row to load the service for modify or delete.")
        self.list_hint.setStyleSheet(SUBTITLE)
        list_layout.addWidget(self.list_hint)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Code",
                "Name",
                "Category",
                "Sub Cat",
                "Charge / Dr%",
                "Rate",
                "Sharing",
                "Dr Report Col",
                "Renewal",
                "Status",
            ]
        )
        self.table.setProperty(
            "hmsColumnKinds",
            ["code", "text", "text", "text", "number", "number", "code", "code", "code", "code"],
        )
        self.table.setProperty("hmsStretchColumn", 1)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        self.table.cellDoubleClicked.connect(self._on_table_double_click)
        # Keep list small (~4–5 visible rows); form gets the rest of the page.
        row_h = max(22, self.table.verticalHeader().defaultSectionSize())
        self.table.setMaximumHeight(row_h * 5 + 36)
        self.table.setMinimumHeight(row_h * 4 + 36)
        list_layout.addWidget(self.table, stretch=0)

        self.list_count = QLabel("")
        self.list_count.setStyleSheet(SUBTITLE)
        list_layout.addWidget(self.list_count)
        splitter.addWidget(list_box)

        form_host = QWidget()
        form_outer = QVBoxLayout(form_host)
        form_outer.setContentsMargins(0, 0, 0, 0)
        form_outer.setSpacing(d.section_spacing)

        form_box = QGroupBox("Service Details")
        form = QFormLayout(form_box)
        configure_form_layout(form)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setVerticalSpacing(max(4, d.form_v_spacing - 4))

        self.code = QLineEdit()
        self.code.setPlaceholderText("Leave blank for next number (e.g. PS101)")
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Admission Charges")
        self.service_charge = QLineEdit("0")
        self.rate = QLineEdit("0")
        self.doctor_share_percent = QLineEdit("0")
        self.doctor_share_percent.setPlaceholderText("e.g. 50")
        self._compact_field(self.code, width=140)
        self._compact_field(self.name, min_width=420)
        self._compact_field(self.service_charge, width=120)
        self._compact_field(self.rate, width=120)
        self._compact_field(self.doctor_share_percent, width=120)

        form.addRow("Code", self.code)
        form.addRow("Name *", self.name)
        self.category = QComboBox()
        self.category.currentIndexChanged.connect(self._on_category_changed)
        self.sub_category = QComboBox()
        self._compact_field(self.category, min_width=320)
        self._compact_field(self.sub_category, min_width=320)
        form.addRow("Category", self.category)
        form.addRow("Sub Category", self.sub_category)
        self.service_charge_row_label = QLabel("Service Charge *")
        form.addRow(self.service_charge_row_label, self.service_charge)
        self.rate_row_label = QLabel("Rate *")
        form.addRow(self.rate_row_label, self.rate)

        self.sharing = _make_yn_combo(default_y=False)
        self.sharing.currentIndexChanged.connect(self._toggle_conditional_fields)
        self.discount_apply = _make_yn_combo(default_y=False)
        self.show_in_doctor_collection = _make_yn_combo(default_y=False)
        self.renewal = _make_yn_combo(default_y=False)
        self.renewal.currentIndexChanged.connect(self._toggle_conditional_fields)
        self.status = _make_yn_combo(default_y=True)
        self.status.currentIndexChanged.connect(self._toggle_conditional_fields)
        self._compact_field(self.sharing, width=70)
        self._compact_field(self.discount_apply, width=70)
        self._compact_field(self.show_in_doctor_collection, width=70)
        self._compact_field(self.renewal, width=70)
        self._compact_field(self.status, width=70)

        # Keep short Y/N flags on one row so the form fits on one page.
        flags_row = QWidget()
        flags_layout = QHBoxLayout(flags_row)
        flags_layout.setContentsMargins(0, 0, 0, 0)
        flags_layout.setSpacing(12)
        for label_text, combo in (
            ("Sharing ?", self.sharing),
            ("Discount", self.discount_apply),
            ("Dr Collection Col ?", self.show_in_doctor_collection),
            ("Renewal", self.renewal),
            ("Status", self.status),
        ):
            pair = QWidget()
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(4)
            pair_layout.addWidget(QLabel(label_text))
            pair_layout.addWidget(combo)
            flags_layout.addWidget(pair)
        flags_layout.addStretch()
        form.addRow("Flags", flags_row)

        self.doctor_share_label = QLabel("Doctor Share % *")
        form.addRow(self.doctor_share_label, self.doctor_share_percent)

        self.doctor = QComboBox()
        self._compact_field(self.doctor, min_width=320)
        self.doctor_row_label = QLabel("Doctor *")
        form.addRow(self.doctor_row_label, self.doctor)
        # Back-compat aliases used by older toggle helpers
        self.doctor_status_label = self.doctor_row_label
        self.doctor_status_row = self.doctor

        self.renewal_days = QSpinBox()
        self.renewal_days.setRange(0, 9999)
        self._compact_field(self.renewal_days, width=120)
        self.renewal_days_row = QWidget()
        renewal_layout = QHBoxLayout(self.renewal_days_row)
        renewal_layout.setContentsMargins(0, 0, 0, 0)
        renewal_layout.addWidget(self.renewal_days)
        renewal_layout.addStretch()
        form.addRow("Renewal Days *", self.renewal_days_row)

        self.close_date = QDateEdit()
        self.close_date.setCalendarPopup(True)
        self.close_date.setDisplayFormat("dd/MM/yyyy")
        self.close_date.setDate(QDate.currentDate())
        self._compact_field(self.close_date, width=160)
        self.close_date_row = QWidget()
        close_layout = QHBoxLayout(self.close_date_row)
        close_layout.setContentsMargins(0, 0, 0, 0)
        close_layout.addWidget(self.close_date)
        close_layout.addStretch()
        form.addRow("Close Date *", self.close_date_row)

        form_outer.addWidget(form_box)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        form_outer.addLayout(btn_row)

        splitter.addWidget(wrap_widget_in_scroll(form_host))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([220, 520])

        self._toggle_conditional_fields()

    def _compact_field(
        self,
        widget: QWidget,
        *,
        width: int | None = None,
        min_width: int | None = None,
    ) -> None:
        """Lower field *height* only; keep code/amount narrow and names wide."""
        from app.ui.responsive_layout import get_density
        from app.ui.styles import BORDER, INPUT_BG, TEXT

        d = get_density()
        # Global density fields are tall; use a shorter fixed row height here.
        height = max(22, min(26, d.compact_field_height - 6))
        font_size = max(11, d.compact_font_size - 1)

        # Prevent apply_form_field_style() from lifting max-height again.
        widget.setProperty("hmsSkipFormStyle", True)
        widget.setMinimumHeight(height)
        widget.setMaximumHeight(height)
        if width is not None:
            widget.setFixedWidth(width)
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            if min_width is not None:
                widget.setMinimumWidth(min_width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        compact = f"""
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 1px 8px;
    min-height: {height}px;
    max-height: {height}px;
    font-size: {font_size}px;
    color: {TEXT};
}}
QComboBox::drop-down {{
    width: 16px;
    border-left: 1px solid {BORDER};
}}
QDateEdit {{
    padding-right: 22px;
}}
"""
        widget.setStyleSheet(compact.strip())

    def _toggle_conditional_fields(self) -> None:
        sharing_on = _yn_value(self.sharing)
        renewal_on = _yn_value(self.renewal)
        active = _yn_value(self.status)

        self.doctor.setVisible(sharing_on)
        self.doctor_row_label.setVisible(sharing_on)
        self.doctor_share_label.setVisible(sharing_on)
        self.doctor_share_percent.setVisible(sharing_on)
        self.doctor_share_percent.setEnabled(sharing_on)
        self.service_charge.setVisible(not sharing_on)
        self.service_charge_row_label.setVisible(not sharing_on)
        if sharing_on:
            self.rate_row_label.setText("Service Rate *")
        else:
            self.rate_row_label.setText("Rate *")
        self.renewal_days_row.setVisible(renewal_on)
        self.close_date_row.setVisible(not active)

        if sharing_on and self.doctor.count() <= 1:
            self._load_doctors()
        if not active and not self.close_date.date().isValid():
            self.close_date.setDate(QDate.currentDate())
        if active:
            self.close_date.setDate(QDate.currentDate())

    def refresh(self) -> None:
        cache = get_session().cache
        self._load_doctors()
        self._load_categories()
        if cache.loaded:
            self._items = list(cache.patient_services)
        else:
            try:
                self._items = self.api.list_patient_services()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._apply_search()

    def _filtered_items(self) -> list[dict]:
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        rows = list(self._items)
        if query:
            rows = [
                item
                for item in rows
                if query in str(item.get("code") or "").lower()
                or query in str(item.get("name") or "").lower()
            ]
        return sorted(rows, key=lambda item: str(item.get("code") or "").casefold())

    def _apply_search(self) -> None:
        self._load_table()
        total = len(self._items)
        shown = self.table.rowCount()
        if total == shown:
            self.list_count.setText(f"Showing {shown} service(s).")
        else:
            self.list_count.setText(f"Showing {shown} of {total} service(s).")

    def _load_categories(self) -> None:
        cache = get_session().cache
        categories = list(cache.service_categories) if cache.loaded else []
        if not categories:
            try:
                categories = self.api.list_service_categories()
            except ApiError:
                categories = []
        categories = [cat for cat in categories if cat.get("code") != "LAB"]
        current = self.category.currentData()
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("— None —", None)
        for cat in categories:
            self.category.addItem(f"{cat.get('code')} — {cat.get('name')}", cat.get("id"))
        if current:
            idx = self.category.findData(current)
            if idx >= 0:
                self.category.setCurrentIndex(idx)
        self.category.blockSignals(False)
        self._on_category_changed()

    def _on_category_changed(self) -> None:
        cache = get_session().cache
        category_id = self.category.currentData()
        current = self.sub_category.currentData()
        self.sub_category.clear()
        self.sub_category.addItem("— None —", None)
        subs = list(cache.service_sub_categories) if cache.loaded else []
        if category_id:
            subs = [s for s in subs if s.get("category_id") == category_id]
        elif not subs and cache.loaded:
            subs = []
        if not subs and category_id:
            try:
                subs = self.api.list_service_sub_categories(category_id=category_id)
            except ApiError:
                subs = []
        for sub in subs:
            self.sub_category.addItem(f"{sub.get('code')} — {sub.get('name')}", sub.get("id"))
        if current:
            idx = self.sub_category.findData(current)
            if idx >= 0:
                self.sub_category.setCurrentIndex(idx)

    def _load_doctors(self) -> None:
        cache = get_session().cache
        if cache.loaded:
            self._doctors = list(cache.doctors)
        else:
            try:
                result = self.api.list_doctors(page_size=500)
                self._doctors = result.get("items", []) if isinstance(result, dict) else result
            except ApiError:
                self._doctors = []
        current = self.doctor.currentData()
        self.doctor.clear()
        self.doctor.addItem("— Select Doctor —", None)
        for doc in self._doctors:
            label = f"{doc.get('doctor_code')} — {doc.get('full_name', doc.get('first_name', ''))}"
            self.doctor.addItem(label, doc.get("id"))
        if current:
            idx = self.doctor.findData(current)
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)

    def _load_table(self) -> None:
        items = self._filtered_items()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("category_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("sub_category_name") or ""))
            charge_display = str(item.get("service_charge", ""))
            if item.get("is_sharing") and charge_display not in ("", "None"):
                charge_display = f"{charge_display}%"
            self.table.setItem(row, 4, QTableWidgetItem(charge_display))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.get("rate", ""))))
            self.table.setItem(row, 6, QTableWidgetItem("Y" if item.get("is_sharing") else "N"))
            self.table.setItem(
                row,
                7,
                QTableWidgetItem("Y" if item.get("show_in_doctor_collection") else "N"),
            )
            self.table.setItem(row, 8, QTableWidgetItem("Y" if item.get("is_renewal") else "N"))
            status = "Y" if item.get("is_service_active") else "N"
            self.table.setItem(row, 9, QTableWidgetItem(status))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.get("id"))

    def _on_mode_changed(self, mode: str) -> None:
        is_create = mode == self.MODE_CREATE
        is_delete = mode == self.MODE_DELETE
        self.code.setReadOnly(not is_create)
        if is_create:
            self.list_hint.setText("Browse the list or search while creating a new service.")
        else:
            self.list_hint.setText("Search by code or name, then click a row to load the service.")
        self.save_btn.setText("Delete" if is_delete else "Save")
        enabled = not is_delete
        for widget in (
            self.name,
            self.service_charge,
            self.rate,
            self.doctor_share_percent,
            self.sharing,
            self.discount_apply,
            self.show_in_doctor_collection,
            self.renewal,
            self.renewal_days,
            self.status,
            self.close_date,
            self.doctor,
            self.category,
            self.sub_category,
        ):
            widget.setEnabled(enabled)
        if is_create:
            self._clear_form()

    def _on_table_select(self) -> None:
        if self.mode_combo.currentText() == self.MODE_CREATE:
            return
        service_id = self._selected_table_service_id()
        if service_id:
            self._load_item(service_id)

    def _on_table_double_click(self, row: int, _column: int) -> None:
        if self.mode_combo.currentText() == self.MODE_CREATE:
            return
        code_item = self.table.item(row, 0)
        if not code_item:
            return
        service_id = code_item.data(Qt.ItemDataRole.UserRole)
        if service_id:
            self._load_item(service_id)

    def _selected_table_service_id(self) -> str | None:
        items = self.table.selectedItems()
        if not items:
            return self._selected_id
        service_id = self.table.item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return str(service_id) if service_id else None

    def _select_table_row(self, service_id: str | None) -> None:
        if not service_id:
            return
        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                code_item = self.table.item(row, 0)
                if code_item and code_item.data(Qt.ItemDataRole.UserRole) == service_id:
                    self.table.selectRow(row)
                    self.table.scrollToItem(code_item)
                    return
        finally:
            self.table.blockSignals(False)

    def _load_item(self, service_id: str) -> None:
        item = next((i for i in self._items if i.get("id") == service_id), None)
        if not item:
            try:
                item = self.api.get_patient_service(service_id)
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
                return
        self._selected_id = service_id
        self._select_table_row(service_id)
        self.code.setText(item.get("code", ""))
        self.name.setText(item.get("name", ""))
        if item.get("is_sharing"):
            share_value = item.get("service_charge", "0")
            try:
                share_num = float(share_value)
                if share_num > 100 and float(item.get("rate") or 0) == share_num:
                    share_value = "0"
            except (TypeError, ValueError):
                pass
            self.doctor_share_percent.setText(str(share_value))
            self.service_charge.setText("0")
        else:
            self.service_charge.setText(str(item.get("service_charge", "0")))
            self.doctor_share_percent.setText("0")
        self.rate.setText(str(item.get("rate", "0")))
        _set_yn(self.sharing, bool(item.get("is_sharing")))
        _set_yn(self.discount_apply, bool(item.get("discount_apply")))
        _set_yn(self.show_in_doctor_collection, bool(item.get("show_in_doctor_collection")))
        _set_yn(self.renewal, bool(item.get("is_renewal")))
        _set_yn(self.status, bool(item.get("is_service_active", True)))
        self.renewal_days.setValue(int(item.get("renewal_days") or 0))
        doctor_id = item.get("doctor_id")
        if doctor_id:
            idx = self.doctor.findData(doctor_id)
            if idx < 0:
                label = item.get("doctor_name") or "Doctor"
                self.doctor.addItem(label, doctor_id)
                idx = self.doctor.count() - 1
            self.doctor.setCurrentIndex(idx)
        else:
            self.doctor.setCurrentIndex(0)
        category_id = item.get("category_id")
        if category_id:
            idx = self.category.findData(category_id)
            if idx < 0 and item.get("category_name"):
                self.category.addItem(item.get("category_name"), category_id)
                idx = self.category.count() - 1
            if idx >= 0:
                self.category.setCurrentIndex(idx)
        else:
            self.category.setCurrentIndex(0)
        self._on_category_changed()
        sub_category_id = item.get("sub_category_id")
        if sub_category_id:
            idx = self.sub_category.findData(sub_category_id)
            if idx < 0 and item.get("sub_category_name"):
                self.sub_category.addItem(item.get("sub_category_name"), sub_category_id)
                idx = self.sub_category.count() - 1
            if idx >= 0:
                self.sub_category.setCurrentIndex(idx)
        else:
            self.sub_category.setCurrentIndex(0)
        close = item.get("close_date")
        if close:
            parts = str(close).split("-")
            if len(parts) == 3:
                self.close_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self._toggle_conditional_fields()

    def _clear_form(self) -> None:
        self._selected_id = None
        self.code.clear()
        self.name.clear()
        self.service_charge.setText("0")
        self.rate.setText("0")
        self.doctor_share_percent.setText("0")
        _set_yn(self.sharing, False)
        _set_yn(self.discount_apply, False)
        _set_yn(self.show_in_doctor_collection, False)
        _set_yn(self.renewal, False)
        _set_yn(self.status, True)
        self.renewal_days.setValue(0)
        self.doctor.setCurrentIndex(0)
        self.category.setCurrentIndex(0)
        self.sub_category.setCurrentIndex(0)
        self.close_date.setDate(QDate.currentDate())
        self.table.clearSelection()
        self._toggle_conditional_fields()

    def _parse_amount(self, text: str, label: str) -> float | None:
        raw = text.strip()
        if not raw:
            QMessageBox.warning(self, "Validation", f"{label} is required.")
            return None
        try:
            value = float(raw)
        except ValueError:
            QMessageBox.warning(self, "Validation", f"{label} must be a number.")
            return None
        if value < 0:
            QMessageBox.warning(self, "Validation", f"{label} cannot be negative.")
            return None
        return value

    def _build_payload(self) -> dict | None:
        code = self.code.text().strip()
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return None
        if self.mode_combo.currentText() != self.MODE_CREATE and not code:
            QMessageBox.warning(self, "Validation", "Select a service from the list.")
            return None

        sharing = _yn_value(self.sharing)
        rate = self._parse_amount(
            self.rate.text(),
            "Service rate" if sharing else "Rate",
        )
        if rate is None:
            return None

        if sharing:
            doctor_share = self._parse_amount(self.doctor_share_percent.text(), "Doctor share %")
            if doctor_share is None:
                return None
            if doctor_share > 100:
                QMessageBox.warning(self, "Validation", "Doctor share % cannot be more than 100.")
                return None
            service_charge = doctor_share
        else:
            service_charge = self._parse_amount(self.service_charge.text(), "Service charge")
            if service_charge is None:
                return None

        renewal = _yn_value(self.renewal)
        active = _yn_value(self.status)
        doctor_id = self.doctor.currentData() if sharing else None

        if sharing and not doctor_id:
            QMessageBox.warning(self, "Validation", "Select a doctor when sharing is Y.")
            return None
        if renewal and self.renewal_days.value() <= 0:
            QMessageBox.warning(self, "Validation", "Enter renewal days when renewal is Y.")
            return None

        close_date = None
        if not active:
            qd = self.close_date.date()
            close_date = date(qd.year(), qd.month(), qd.day()).isoformat()

        payload = {
            "name": name,
            "service_charge": service_charge,
            "rate": rate,
            "is_sharing": sharing,
            "doctor_id": doctor_id,
            "discount_apply": _yn_value(self.discount_apply),
            "show_in_doctor_collection": _yn_value(self.show_in_doctor_collection),
            "is_renewal": renewal,
            "renewal_days": self.renewal_days.value() if renewal else None,
            "is_service_active": active,
            "close_date": close_date,
            "category_id": self.category.currentData(),
            "sub_category_id": self.sub_category.currentData(),
        }
        if self.mode_combo.currentText() == self.MODE_CREATE and code:
            payload["code"] = code
        return payload

    def _save(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == self.MODE_DELETE:
            service_id = self._selected_table_service_id() or self._selected_id
            if not service_id:
                QMessageBox.warning(self, "Validation", "Search and select a service from the list to delete.")
                return
            if QMessageBox.question(self, "Confirm", "Deactivate this service?") != QMessageBox.StandardButton.Yes:
                return
            try:
                self.api.delete_patient_service(service_id)
                QMessageBox.information(self, "Success", "Service deactivated.")
                self._clear_form()
                self.refresh()
            except ApiError as exc:
                QMessageBox.warning(self, "Error", str(exc))
            return

        payload = self._build_payload()
        if not payload:
            return

        try:
            if mode == self.MODE_CREATE:
                created = self.api.create_patient_service(payload)
                assigned = (created or {}).get("code") or ""
                msg = f"Service created (code {assigned})." if assigned else "Service created."
                QMessageBox.information(self, "Success", msg)
                self._clear_form()
            else:
                service_id = self._selected_table_service_id() or self._selected_id
                if not service_id:
                    QMessageBox.warning(self, "Validation", "Search and select a service from the list to modify.")
                    return
                payload.pop("code", None)
                self.api.update_patient_service(service_id, payload)
                QMessageBox.information(self, "Success", "Service updated.")
            refresh_patient_services_cache(self.api)
            self.refresh()
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
