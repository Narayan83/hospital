"""Legacy MySQL → PostgreSQL database migration screen."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.styles import (
    BORDER,
    BTN_PRIMARY,
    BTN_SECONDARY,
    INPUT_BG,
    PRIMARY,
    SURFACE,
    TEXT,
    TEXT_MUTED,
)


class _MigrationThread(QThread):
    """Run the migration off the UI thread and forward progress events."""

    progressed = Signal(dict)
    failed = Signal(str)

    def __init__(self, api: ApiClient, payload: dict):
        super().__init__()
        self._api = api
        self._payload = payload

    def run(self) -> None:
        try:
            for event in self._api.legacy_migrate_run_stream(**self._payload):
                self.progressed.emit(event)
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class DatabaseMigrationWidget(QWidget):
    """Admin tool: map legacy MySQL tables to HMS PostgreSQL and migrate."""

    def __init__(self, api: ApiClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._mappings: list[dict] = []
        self._checks: dict[str, QCheckBox] = {}
        self._legacy_edits: dict[str, QLineEdit] = {}
        self._filter_edits: dict[str, QLineEdit] = {}
        self._row_labels: dict[str, QLabel] = {}
        self._migration_thread: _MigrationThread | None = None
        self._running = False
        self._finished_notified = False
        self.setProperty("hmsExpandFormFields", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {SURFACE}; color: {TEXT};")
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        heading = QLabel("Database Migration")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(heading)

        intro = QLabel(
            "Import data from the old MySQL 5.6 hospital software into this PostgreSQL "
            "database. Edit connection strings if needed. Tick the tables to migrate "
            "(or Select all). Pathology is optional because it is usually already mapped."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        root.addWidget(intro)

        conn_box = QGroupBox("Connection strings")
        conn_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        conn_box.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {BORDER}; border-radius: 8px; margin-top: 6px;"
            " font-weight: 600; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )
        form = QFormLayout(conn_box)
        form.setSpacing(4)
        form.setContentsMargins(8, 10, 8, 8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.mysql_edit = self._wide_edit(
            "Driver={MySQL ODBC 3.51 Driver};Server=localhost;Database=hsp;User=root;Password=;"
        )
        mysql_row = QHBoxLayout()
        mysql_row.setSpacing(6)
        mysql_row.addWidget(self.mysql_edit, stretch=1)
        test_mysql = QPushButton("Test MySQL")
        test_mysql.setStyleSheet(BTN_SECONDARY)
        test_mysql.setCursor(Qt.CursorShape.PointingHandCursor)
        test_mysql.clicked.connect(self._test_mysql)
        mysql_row.addWidget(test_mysql)
        form.addRow("MySQL (source):", mysql_row)

        self.pg_edit = self._wide_edit("postgresql://user:pass@127.0.0.1:5432/hms")
        pg_row = QHBoxLayout()
        pg_row.setSpacing(6)
        pg_row.addWidget(self.pg_edit, stretch=1)
        test_pg = QPushButton("Test PostgreSQL")
        test_pg.setStyleSheet(BTN_SECONDARY)
        test_pg.setCursor(Qt.CursorShape.PointingHandCursor)
        test_pg.clicked.connect(self._test_postgres)
        pg_row.addWidget(test_pg)
        form.addRow("PostgreSQL (target):", pg_row)

        self.password = self._wide_edit("Required to run migration (same as Reset Database)")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Maintenance password:", self.password)
        root.addWidget(conn_box)

        tools = QHBoxLayout()
        for text, handler in (
            ("Select all", self._select_all),
            ("Select defaults", self._select_defaults),
            ("Clear selection", self._select_none),
            ("Refresh source counts", self._preview_counts),
        ):
            btn = QPushButton(text)
            btn.setStyleSheet(BTN_SECONDARY)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            tools.addWidget(btn)
        tools.addStretch()
        root.addLayout(tools)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        root.addWidget(self.summary_label)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        self._set_status("Ready.", kind="muted")
        root.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {BORDER}; border-radius: 3px; margin: 2px 0; }}"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(160)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 2px solid {BORDER}; border-radius: 8px; background: {INPUT_BG}; }}"
        )
        self._list_host = QWidget()
        self._list_host.setStyleSheet(f"background: {INPUT_BG};")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(8, 6, 8, 6)
        self._list_layout.setSpacing(2)
        scroll.setWidget(self._list_host)
        splitter.addWidget(scroll)

        log_host = QWidget()
        log_layout = QVBoxLayout(log_host)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        opts = QHBoxLayout()
        self.replace_cb = QCheckBox("Replace existing rows for selected targets")
        self.replace_cb.setToolTip(
            "When checked, clears related target data before importing. "
            "Leave unchecked to skip duplicates / upsert safely."
        )
        self.dry_run_cb = QCheckBox("Dry run (preview only — no writes)")
        opts.addWidget(self.replace_cb)
        opts.addWidget(self.dry_run_cb)
        opts.addStretch()
        drag_hint = QLabel("Drag the divider above to resize the log ↕")
        drag_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        opts.addWidget(drag_hint)
        log_layout.addLayout(opts)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(40)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log.setPlaceholderText("Migration log…")
        self.log.setStyleSheet(
            f"QTextEdit {{ background: {INPUT_BG}; border: 1px solid {BORDER};"
            " border-radius: 4px; font-family: Consolas, monospace; font-size: 10px;"
            " padding: 2px 4px; }"
        )
        log_layout.addWidget(self.log)

        log_host.setMinimumHeight(78)
        splitter.addWidget(log_host)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 110])
        root.addWidget(splitter, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.run_btn = QPushButton("Run Migration")
        self.run_btn.setStyleSheet(BTN_PRIMARY)
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self._run_migration)
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)

    def _wide_edit(self, placeholder: str = "") -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setProperty("hmsAllowWide", True)
        edit.setMaximumWidth(16777215)
        edit.setMinimumHeight(24)
        edit.setMaximumHeight(26)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        edit.setStyleSheet(self._input_ss())
        return edit

    @staticmethod
    def _input_ss() -> str:
        return (
            f"QLineEdit {{ background: {INPUT_BG}; border: 1px solid {BORDER};"
            " border-radius: 4px; padding: 2px 6px; font-size: 12px; min-height: 22px;"
            " max-height: 26px; }"
        )

    def _load_defaults(self) -> None:
        try:
            data = self.api.legacy_migrate_defaults()
        except ApiError as exc:
            QMessageBox.warning(self, "Database Migration", str(exc))
            self.run_btn.setEnabled(False)
            return

        self.mysql_edit.setText(data.get("mysql_connection_string") or "")
        self.pg_edit.setText(data.get("postgres_connection_string") or "")
        self._mappings = list(data.get("mappings") or [])
        self._rebuild_mapping_list()

    def _clear_list(self) -> None:
        self._checks.clear()
        self._legacy_edits.clear()
        self._filter_edits.clear()
        self._row_labels.clear()
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_mapping_list(self) -> None:
        self._clear_list()
        current_group: str | None = None
        for item in self._mappings:
            group = item.get("group") or "Other"
            if group != current_group:
                current_group = group
                header = QLabel(group)
                header.setStyleSheet(
                    f"font-weight: 700; color: {TEXT}; margin-top: 4px;"
                    f" border-bottom: 1px solid {BORDER}; padding-bottom: 1px;"
                )
                self._list_layout.addWidget(header)

            key = item["key"]
            row = QWidget()
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(6)

            tip_parts = [p for p in (item.get("filter_note"), item.get("notes")) if p]
            tip = " — ".join(tip_parts)

            cb = QCheckBox(item.get("label") or key)
            cb.setChecked(bool(item.get("default_selected")))
            cb.setToolTip(tip)
            cb.toggled.connect(self._update_summary)
            self._checks[key] = cb
            row_l.addWidget(cb, stretch=2)

            arrow = QLabel("→")
            arrow.setStyleSheet(f"color: {TEXT_MUTED};")
            row_l.addWidget(arrow)

            targets = ", ".join(item.get("target_tables") or [])
            tgt = QLabel(targets)
            tgt.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            tgt.setWordWrap(True)
            tgt.setToolTip(tip)
            row_l.addWidget(tgt, stretch=2)

            legacy = QLineEdit(item.get("legacy_table") or "")
            legacy.setFixedWidth(100)
            legacy.setMinimumHeight(24)
            legacy.setMaximumHeight(26)
            legacy.setStyleSheet(self._input_ss())
            legacy.setToolTip("Legacy MySQL source table name")
            self._legacy_edits[key] = legacy
            row_l.addWidget(legacy)

            where_lbl = QLabel("WHERE")
            where_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600;")
            row_l.addWidget(where_lbl)

            filt = QLineEdit(item.get("source_filter") or item.get("filter_note") or "")
            filt.setProperty("hmsAllowWide", True)
            filt.setMaximumWidth(16777215)
            filt.setMinimumHeight(24)
            filt.setMaximumHeight(26)
            filt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            filt.setStyleSheet(self._input_ss())
            filt.setToolTip(
                "SQL WHERE condition for this table (defaults to active / non-deleted rows). "
                + (tip or "")
            )
            self._filter_edits[key] = filt
            row_l.addWidget(filt, stretch=4)

            count_lbl = QLabel("")
            count_lbl.setMinimumWidth(130)
            count_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            self._row_labels[key] = count_lbl
            row_l.addWidget(count_lbl)

            self._list_layout.addWidget(row)

        self._list_layout.addStretch()
        self._update_summary()

    def _selected_keys(self) -> list[str]:
        return [k for k, cb in self._checks.items() if cb.isChecked()]

    def _mapping_payload(self) -> list[dict]:
        out = []
        for key, edit in self._legacy_edits.items():
            filt = self._filter_edits.get(key)
            out.append(
                {
                    "key": key,
                    "legacy_table": edit.text().strip(),
                    "source_filter": filt.text().strip() if filt else "",
                }
            )
        return out

    def _update_summary(self) -> None:
        selected = self._selected_keys()
        self.summary_label.setText(f"{len(selected)} mapping(s) selected for migration.")
        self.run_btn.setEnabled(bool(selected))

    def _select_all(self) -> None:
        for cb in self._checks.values():
            cb.setChecked(True)

    def _select_none(self) -> None:
        for cb in self._checks.values():
            cb.setChecked(False)

    def _select_defaults(self) -> None:
        defaults = {m["key"]: bool(m.get("default_selected")) for m in self._mappings}
        for key, cb in self._checks.items():
            cb.setChecked(defaults.get(key, False))

    def _append_log(self, text: str) -> None:
        self.log.append(text)
        self.log.ensureCursorVisible()

    def _set_status(self, text: str, *, kind: str = "info") -> None:
        colors = {
            "info": PRIMARY,
            "ok": "#15803d",
            "error": "#b91c1c",
            "muted": TEXT_MUTED,
        }
        color = colors.get(kind, TEXT)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 700;"
            f" background: {INPUT_BG}; border: 1px solid {BORDER};"
            " border-radius: 4px; padding: 4px 8px;"
        )

    def _set_row_progress(self, key: str | None, text: str, *, ok: bool | None = None) -> None:
        if not key:
            return
        label = self._row_labels.get(key)
        if label is None:
            return
        if ok is True:
            color = "#15803d"
        elif ok is False:
            color = "#b91c1c"
        else:
            color = PRIMARY
        label.setText(text)
        label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")

    @staticmethod
    def _detail_text(detail: dict) -> str:
        error = str(detail.get("error") or "").strip()
        error_type = str(detail.get("error_type") or "").strip()
        if error or error_type:
            if error and error_type and error_type not in error:
                return f"{error_type}: {error}"
            return error or error_type
        parts = []
        for field, label in (
            ("source_rows", "source"),
            ("imported", "imported"),
            ("imported_lines", "lines"),
            ("converted_to_pdf", "converted to PDF"),
            ("skipped", "skipped"),
            ("missing_patients", "patient not found"),
            ("failed", "failed"),
        ):
            if field not in detail:
                continue
            value = detail[field]
            if not value and not (field == "imported" and value == 0):
                continue
            parts.append(f"{label}={value}")
        summary = ", ".join(parts)
        message = detail.get("message")
        if message and summary:
            return f"{summary} — {message}"
        return message or summary or "done"

    def _test_mysql(self) -> None:
        try:
            result = self.api.legacy_migrate_test_mysql(self.mysql_edit.text().strip())
        except ApiError as exc:
            QMessageBox.warning(self, "MySQL", str(exc))
            return
        msg = result.get("message") or "OK"
        tables = result.get("table_count")
        if tables is not None:
            msg += f"\n{tables} table(s) found."
        QMessageBox.information(self, "MySQL", msg)
        self._append_log(f"MySQL: {result.get('message')}")

    def _test_postgres(self) -> None:
        try:
            result = self.api.legacy_migrate_test_postgres(self.pg_edit.text().strip())
        except ApiError as exc:
            QMessageBox.warning(self, "PostgreSQL", str(exc))
            return
        QMessageBox.information(self, "PostgreSQL", result.get("message") or "OK")
        self._append_log(f"PostgreSQL: {result.get('message')}")

    def _preview_counts(self) -> None:
        try:
            result = self.api.legacy_migrate_preview(
                mysql_connection_string=self.mysql_edit.text().strip(),
                mappings=self._mapping_payload(),
            )
        except ApiError as exc:
            QMessageBox.warning(self, "Preview", str(exc))
            return
        for info in result.get("counts") or []:
            key = info.get("key")
            lbl = self._row_labels.get(key)
            if not lbl:
                continue
            if not info.get("exists"):
                lbl.setText("missing")
                lbl.setStyleSheet("color: #b91c1c; font-size: 11px;")
            else:
                rows = info.get("source_rows")
                extra = ""
                if "opd_rows" in info:
                    extra = f" (OPD {info['opd_rows']}/IPD {info.get('ipd_rows', 0)})"
                lbl.setText(f"{rows:,} rows{extra}" if isinstance(rows, int) else "n/a")
                lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._append_log("Source row counts refreshed.")

    def _run_migration(self) -> None:
        selected = self._selected_keys()
        if not selected:
            QMessageBox.information(self, "Database Migration", "Select at least one mapping.")
            return
        password = self.password.text()
        if not password:
            QMessageBox.warning(self, "Database Migration", "Enter the maintenance password.")
            self.password.setFocus()
            return

        dry = self.dry_run_cb.isChecked()
        action = "dry-run" if dry else "migrate"
        confirm = QMessageBox.question(
            self,
            "Confirm Migration",
            f"You are about to {action} {len(selected)} mapping(s) from MySQL to PostgreSQL.\n\n"
            "Recommended order is already applied (masters before transactions).\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._running = True
        self._finished_notified = False
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Migrating…")
        self.log.clear()
        self._set_status("Starting migration…", kind="info")
        self._append_log("Starting migration…")

        payload = {
            "password": password,
            "mysql_connection_string": self.mysql_edit.text().strip(),
            "postgres_connection_string": self.pg_edit.text().strip(),
            "selected_keys": selected,
            "mappings": self._mapping_payload(),
            "replace_existing": self.replace_cb.isChecked(),
            "dry_run": dry,
        }
        thread = _MigrationThread(self.api, payload)
        thread.progressed.connect(self._on_migration_event)
        thread.failed.connect(self._on_migration_failed)
        thread.finished.connect(self._on_migration_thread_done)
        self._migration_thread = thread
        thread.start()

    def _on_migration_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "rows":
            self._set_status(self._event_status(event), kind="info")
            processed = event.get("processed")
            total = event.get("total")
            unit = event.get("unit") or "rows"
            converted = event.get("converted_to_pdf")
            if isinstance(processed, int) and isinstance(total, int):
                if isinstance(converted, int):
                    text = f"{processed:,}/{total:,} · {converted:,} PDF"
                else:
                    text = f"{processed:,}/{total:,} {unit}"
                self._set_row_progress(event.get("key"), text)
            return

        if kind == "table":
            text = self._event_status(event)
            self._set_status(text, kind="info")
            self._append_log(text)
            if event.get("phase") == "reading":
                self._set_row_progress(event.get("key"), "reading…")
            elif isinstance(event.get("source_rows"), int):
                self._set_row_progress(event.get("key"), f"0/{event['source_rows']:,}")
            return

        if kind == "table_done":
            text = self._event_status(event)
            ok = bool(event.get("ok"))
            self._set_status(text, kind="ok" if ok else "error")
            status = "OK" if ok else "FAIL"
            label = event.get("label") or event.get("key")
            self._append_log(f"  [{status}] {label}: {self._detail_text(event)}")
            trace = event.get("traceback")
            if trace:
                self._append_log(f"      {trace.strip().replace(chr(10), chr(10) + '      ')}")
            if ok:
                imported = event.get("imported")
                source = event.get("source_rows")
                if isinstance(imported, int) and isinstance(source, int):
                    self._set_row_progress(event.get("key"), f"{imported:,} / {source:,}", ok=True)
                elif isinstance(imported, int):
                    self._set_row_progress(event.get("key"), f"{imported:,} imported", ok=True)
                else:
                    self._set_row_progress(event.get("key"), "done", ok=True)
            else:
                self._set_row_progress(event.get("key"), "failed", ok=False)
            return

        if kind == "complete":
            self._show_migration_result(event)
            return

        if kind == "error":
            message = event.get("message") or "Migration failed."
            self._show_migration_failure(message)
            return

        text = self._event_status(event)
        self._set_status(text, kind="info")
        if text:
            self._append_log(text)

    def _event_status(self, event: dict) -> str:
        kind = event.get("type")
        if kind == "start":
            count = event.get("table_total") or 0
            word = "Dry run" if event.get("dry_run") else "Migration"
            return f"{word} started — {count} table(s)."
        if kind == "status":
            return str(event.get("message") or "Working…")
        if kind == "complete":
            return str(event.get("message") or "Migration completed.")
        if kind == "error":
            return str(event.get("message") or "Migration failed.")

        label = event.get("label") or event.get("key") or "Table"
        table = event.get("legacy_table") or ""
        name = f"{label} ({table})" if table else str(label)
        index = event.get("table_index")
        total_tables = event.get("table_total")
        prefix = f"[{index}/{total_tables}] " if index and total_tables else ""

        if kind == "table" and event.get("message"):
            return f"{prefix}{event['message']}"
        if kind == "table" and event.get("phase") == "reading":
            return f"{prefix}Reading {name} from MySQL…"
        if kind == "table":
            rows = event.get("source_rows")
            extra = f" — {rows:,} source rows" if isinstance(rows, int) else ""
            return f"{prefix}Migrating {name}{extra}"
        if kind == "rows":
            activity = str(event.get("activity") or f"Migrating {name}")
            processed = event.get("processed")
            denom = event.get("total")
            unit = event.get("unit") or "rows"
            imported = event.get("imported")
            converted = event.get("converted_to_pdf")
            bits: list[str] = []
            if isinstance(processed, int) and isinstance(denom, int):
                bits.append(f"{processed:,} / {denom:,} {unit}")
            if isinstance(converted, int):
                bits.append(f"{converted:,} converted to PDF")
            elif isinstance(imported, int):
                bits.append(f"{imported:,} imported")
            detail = ", ".join(bits)
            current = str(event.get("detail") or "").strip()
            text = f"{prefix}{activity}"
            if detail:
                text += f": {detail}"
            if current:
                text += f" — {current}"
            return text
        if kind == "table_done":
            if event.get("ok"):
                return f"{prefix}Finished {name}: {self._detail_text(event)}"
            return f"{prefix}Failed {name}: {self._detail_text(event)}"
        return str(event.get("message") or "Working…")

    def _show_migration_result(self, event: dict) -> None:
        if self._finished_notified:
            return
        self._finished_notified = True
        message = event.get("message") or "Migration completed."
        lines = []
        for key, detail in (event.get("results") or {}).items():
            status = "OK" if detail.get("ok") else "FAILED"
            lines.append(f"{status}  {detail.get('label', key)}: {self._detail_text(detail)}")
        body = f"{message}\n\n" + "\n".join(lines) if lines else message
        ok = bool(event.get("ok"))
        self._running = False
        self._set_status(message, kind="ok" if ok else "error")
        self._append_log(message)
        if event.get("dry_run") and ok:
            QMessageBox.information(self, "Dry Run Completed", body)
        elif ok:
            QMessageBox.information(self, "Migration Completed", body)
        else:
            QMessageBox.warning(self, "Migration Finished", body)
        self._end_run()

    def _show_migration_failure(self, message: str) -> None:
        if self._finished_notified:
            return
        self._finished_notified = True
        self._running = False
        self._set_status(message, kind="error")
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Migration Failed", message)
        self._end_run()

    def _on_migration_failed(self, message: str) -> None:
        self._show_migration_failure(message)

    def _on_migration_thread_done(self) -> None:
        if self._finished_notified:
            return
        if self._running:
            self._show_migration_failure("Migration stopped before it finished.")
        else:
            self._end_run()

    def _end_run(self) -> None:
        self._running = False
        self.run_btn.setText("Run Migration")
        self.run_btn.setEnabled(bool(self._selected_keys()))
