from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QMarginsF, QObject, QSizeF, Qt, QTimer
from PySide6.QtGui import QPageLayout, QPageSize, QWheelEvent, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.print_config_store import ResolvedPrintSettings, get_print_settings
from app.ui.responsive_layout import fit_dialog_size

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


_BILL_REPORT_CODES = frozenset(
    {
        "OPD_BILL",
        "IPD_BILL",
        "PATHOLOGY_BILL",
        "PATHOLOGY_REPORT",
        "PHARMACY_BILL",
        "ADVANCE_RECEIPT",
        "SHORT_BILL",
    }
)
_BILL_MAX_SIDE_MARGIN_MM = 8.0
_BILL_MAX_TOP_MARGIN_MM = 8.0
_BILL_MAX_BOTTOM_MARGIN_MM = 8.0


def _clamp_bill_margins(
    settings: ResolvedPrintSettings | None,
    report_code: str | None,
) -> ResolvedPrintSettings | None:
    if not settings or not report_code:
        return settings
    if report_code.upper() not in _BILL_REPORT_CODES:
        return settings
    left = min(settings.margin_left_mm, _BILL_MAX_SIDE_MARGIN_MM)
    right = min(settings.margin_right_mm, _BILL_MAX_SIDE_MARGIN_MM)
    top = min(settings.margin_top_mm, _BILL_MAX_TOP_MARGIN_MM)
    bottom = min(settings.margin_bottom_mm, _BILL_MAX_BOTTOM_MARGIN_MM)
    if (
        left == settings.margin_left_mm
        and right == settings.margin_right_mm
        and top == settings.margin_top_mm
        and bottom == settings.margin_bottom_mm
    ):
        return settings
    return ResolvedPrintSettings(
        printer_name=settings.printer_name,
        paper_size=settings.paper_size,
        custom_width_mm=settings.custom_width_mm,
        custom_height_mm=settings.custom_height_mm,
        orientation=settings.orientation,
        print_mode=settings.print_mode,
        margin_top_mm=top,
        margin_right_mm=right,
        margin_bottom_mm=bottom,
        margin_left_mm=left,
        copies=settings.copies,
    )


def _resolve_print_settings(
    api: ApiClient | None,
    report_code: str | None,
) -> ResolvedPrintSettings | None:
    settings = get_print_settings(api, report_code)
    return _clamp_bill_margins(settings, report_code)


def _append_report_format(endpoint: str, suffix: str) -> str:
    base = endpoint.rstrip("/")
    if "?" in base:
        path, query = base.split("?", 1)
        return f"{path.rstrip('/')}/{suffix}?{query}"
    return f"{base}/{suffix}"


def _html_endpoint(endpoint: str) -> str:
    return _append_report_format(endpoint, "html")


def _excel_endpoint(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/html"):
        base = base[:-5]
    return _append_report_format(base, "excel")


def _default_export_stem(report_endpoint: str | None, title: str) -> str:
    if report_endpoint:
        parts = [part for part in report_endpoint.strip("/").split("/") if part]
        if parts:
            tail = parts[-1]
            if tail not in {"html", "excel"} and len(parts) >= 2:
                return f"{parts[-2]}_{tail}"
            if tail not in {"html", "excel"}:
                return tail
    match = re.search(r"Bill\s+([A-Za-z0-9_-]+)", title)
    if match:
        return match.group(1)
    return "bill_export"


def _installed_printers() -> tuple[list[str], str | None]:
    names = list(QPrinterInfo.availablePrinterNames())
    default_info = QPrinterInfo.defaultPrinter()
    default_name = None if default_info.isNull() else default_info.printerName()
    return names, default_name


def _populate_printer_combo(combo: QComboBox) -> str | None:
    combo.clear()
    names, default_name = _installed_printers()
    if not names:
        combo.addItem("No printer installed", None)
        combo.setEnabled(False)
        return None
    selected_index = 0
    for index, name in enumerate(names):
        label = f"{name} (Default)" if name == default_name else name
        combo.addItem(label, name)
        if name == default_name:
            selected_index = index
    combo.setCurrentIndex(selected_index)
    combo.setEnabled(True)
    return default_name


_PAPER_SIZE_MAP = {
    "A4": QPageSize.PageSizeId.A4,
    "A5": QPageSize.PageSizeId.A5,
    "A6": QPageSize.PageSizeId.A6,
    "LETTER": QPageSize.PageSizeId.Letter,
    "LEGAL": QPageSize.PageSizeId.Legal,
}


def _resolve_page_size(settings: ResolvedPrintSettings | None) -> QPageSize:
    if settings and settings.paper_size == "CUSTOM":
        width = settings.custom_width_mm or 105.0
        height = settings.custom_height_mm or 74.0
        return QPageSize(
            QSizeF(width, height),
            QPageSize.Unit.Millimeter,
            "Custom",
            QPageSize.SizeMatchPolicy.ExactMatch,
        )
    size_id = _PAPER_SIZE_MAP.get(
        (settings.paper_size if settings else "A4").upper(),
        QPageSize.PageSizeId.A4,
    )
    return QPageSize(size_id)


def _is_landscape(settings: ResolvedPrintSettings | None, *, landscape: bool) -> bool:
    if settings:
        return settings.orientation == "landscape"
    return landscape


def _configure_printer(
    printer: QPrinter,
    *,
    landscape: bool = False,
    settings: ResolvedPrintSettings | None = None,
) -> None:
    page_size = _resolve_page_size(settings)
    use_landscape = _is_landscape(settings, landscape=landscape)
    if settings:
        margins = QMarginsF(
            settings.margin_left_mm,
            settings.margin_top_mm,
            settings.margin_right_mm,
            settings.margin_bottom_mm,
        )
    else:
        margins = QMarginsF(5, 8, 5, 10)
    page_layout = QPageLayout(
        page_size,
        QPageLayout.Orientation.Landscape if use_landscape else QPageLayout.Orientation.Portrait,
        margins,
        QPageLayout.Unit.Millimeter,
    )
    printer.setPageLayout(page_layout)
    # Paint inside margins so document width matches the printable area.
    printer.setFullPage(False)
    printer.setResolution(96)
    if settings and settings.copies > 1:
        printer.setCopyCount(settings.copies)


def _build_printer(
    *,
    for_preview: bool = True,
    pdf_path: str | None = None,
    landscape: bool = False,
    settings: ResolvedPrintSettings | None = None,
    printer_name: str | None = None,
) -> QPrinter:
    mode = QPrinter.PrinterMode.ScreenResolution if for_preview else QPrinter.PrinterMode.HighResolution
    printer = QPrinter(mode)
    if pdf_path:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
    _configure_printer(printer, landscape=landscape, settings=settings)
    resolved_name = printer_name
    if settings and settings.printer_name:
        resolved_name = settings.printer_name
    if resolved_name:
        printer.setPrinterName(resolved_name)
    return printer


def _ensure_table_widths(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r"\bwidth\s*=", tag, re.IGNORECASE):
            return tag
        return tag[:-1] + ' width="100%">'

    return re.sub(r"<table\b[^>]*>", repl, html, flags=re.IGNORECASE)


def _printable_size_px(printer: QPrinter) -> tuple[float, float]:
    """QTextDocument lays out HTML at 96 DPI; size from page points keeps fonts correct."""
    paint = printer.pageLayout().paintRect(QPageLayout.Unit.Point)
    # 1 CSS px == 1/96 in; 1 pt == 1/72 in → px = pt * 96/72
    width = max(paint.width() * 96.0 / 72.0, 1.0)
    height = max(paint.height() * 96.0 / 72.0, 1.0)
    return width, height


def _apply_qt_page_width(html: str, page_width_px: float) -> str:
    """Constrain bill HTML to the printable width without overflowing."""
    # Leave 2px slack so cell borders do not clip on the right edge.
    width = max(int(page_width_px) - 2, 1)
    marker = 'class="page-shell"'
    if marker not in html:
        match = re.search(r"(<body[^>]*>)(.*?)(</body>)", html, re.DOTALL | re.IGNORECASE)
        if match:
            inner = match.group(2).strip()
            wrapped = (
                f"{match.group(1)}"
                f'<table {marker} width="{width}" border="0" cellspacing="0" cellpadding="0">'
                f'<tr><td width="{width}">'
                f"{inner}"
                f"</td></tr></table>"
                f"{match.group(3)}"
            )
            html = html[: match.start()] + wrapped + html[match.end() :]
        else:
            return html
    else:
        html = re.sub(
            rf"<table {re.escape(marker)}[^>]*>",
            f'<table {marker} width="{width}" border="0" cellspacing="0" cellpadding="0">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r'(<table class="page-shell"[^>]*>\s*<tr>\s*)<td[^>]*>',
            rf'\1<td width="{width}">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    # Force every top-level-looking table to percentage width (not a pixel guess).
    def _table_to_pct(match: re.Match[str]) -> str:
        tag = match.group(0)
        if 'class="page-shell"' in tag or "class='page-shell'" in tag:
            return tag
        tag = re.sub(r'\swidth="[^"]*"', "", tag, flags=re.IGNORECASE)
        return tag[:-1] + ' width="100%">'

    html = re.sub(r"<table\b[^>]*>", _table_to_pct, html, flags=re.IGNORECASE)

    qt_style = (
        f'<style id="hms-qt-page-width">'
        f"body{{margin:0;padding:0;color:#000000;"
        f"font-family:'Times New Roman',Times,serif;font-weight:bold;}}"
        f"table{{border-collapse:collapse;}}"
        f"td,th,p{{color:#000000;}}"
        f"</style>"
    )
    if "hms-qt-page-width" not in html:
        html = re.sub(r"</head>", qt_style + "</head>", html, count=1, flags=re.IGNORECASE)
    else:
        html = re.sub(
            r'<style id="hms-qt-page-width">.*?</style>',
            qt_style,
            html,
            count=1,
            flags=re.DOTALL,
        )
    return html


def _build_document(html: str, printer: QPrinter) -> QTextDocument:
    document = QTextDocument()
    width, height = _printable_size_px(printer)
    prepared = _apply_qt_page_width(html, width)
    document.setDocumentMargin(0)
    document.setHtml(prepared)
    document.setDocumentMargin(0)
    document.setTextWidth(width)
    document.setPageSize(QSizeF(width, height))
    return document


class ZoomablePrintPreviewWidget(QPrintPreviewWidget):
    """Print preview with Ctrl+wheel and mouse-wheel zoom."""

    _MIN_ZOOM = 0.25
    _MAX_ZOOM = 5.0
    _ZOOM_STEP = 0.1

    def __init__(self, printer: QPrinter, parent: QWidget | None = None) -> None:
        super().__init__(printer, parent)
        self._wheel_filters_installed = False
        QTimer.singleShot(0, self._install_wheel_zoom_filters)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._install_wheel_zoom_filters()

    def _install_wheel_zoom_filters(self) -> None:
        targets = {self, *self.findChildren(QWidget)}
        for widget in targets:
            widget.installEventFilter(self)
        self._wheel_filters_installed = True

    def _should_zoom_wheel(self, event: QWheelEvent) -> bool:
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return True
        return not (
            modifiers
            & (
                Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )

    def _apply_wheel_zoom(self, delta: int) -> None:
        if delta == 0:
            return
        self.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
        factor = self.zoomFactor()
        if delta > 0:
            self.setZoomFactor(min(factor + self._ZOOM_STEP, self._MAX_ZOOM))
        else:
            self.setZoomFactor(max(factor - self._ZOOM_STEP, self._MIN_ZOOM))
        self.updatePreview()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel and (
            watched is self or self.isAncestorOf(watched)
        ):
            wheel = event
            if isinstance(wheel, QWheelEvent) and self._should_zoom_wheel(wheel):
                self._apply_wheel_zoom(wheel.angleDelta().y())
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._should_zoom_wheel(event):
            self._apply_wheel_zoom(event.angleDelta().y())
            event.accept()
            return
        super().wheelEvent(event)


class BillPrintPreviewDialog(QDialog):
    """Bill preview with export, zoom, and print actions."""

    def __init__(
        self,
        html: str,
        *,
        api: ApiClient | None = None,
        report_endpoint: str | None = None,
        parent: QWidget | None = None,
        title: str = "Bill Preview",
        landscape: bool = False,
        printer_name: str | None = None,
        settings: ResolvedPrintSettings | None = None,
        default_copies: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._html = html
        self._api = api
        self._report_endpoint = report_endpoint
        self._landscape = landscape
        self._settings = settings
        self._initial_printer_name = printer_name or (settings.printer_name if settings else None)
        self._default_copies = max(int(default_copies or (settings.copies if settings else 1)), 1)
        self._export_stem = _default_export_stem(report_endpoint, title)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(*fit_dialog_size(1020, 780))

        self._printer = _build_printer(
            for_preview=True,
            landscape=landscape,
            settings=settings,
            printer_name=self._initial_printer_name,
        )
        layout = QVBoxLayout(self)

        export_row = QHBoxLayout()
        save_pdf_btn = QPushButton("Save to PDF")
        save_excel_btn = QPushButton("Save to Excel")
        save_pdf_btn.clicked.connect(self._save_pdf)
        save_excel_btn.clicked.connect(self._save_excel)
        export_row.addWidget(save_pdf_btn)
        export_row.addWidget(save_excel_btn)
        export_row.addStretch()
        layout.addLayout(export_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        self._preview = ZoomablePrintPreviewWidget(self._printer, self)
        self._preview.paintRequested.connect(self._render_to_printer)
        self._preview.setZoomMode(QPrintPreviewWidget.ZoomMode.FitInView)
        self._preview.setViewMode(QPrintPreviewWidget.ViewMode.SinglePageView)
        self._preview.previewChanged.connect(self._update_page_nav)

        zoom_row = QHBoxLayout()
        zoom_label = QLabel("View:")
        fit_btn = QPushButton("Fit Page")
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        actual_btn = QPushButton("100%")
        self._expand_btn = QToolButton()
        self._expand_btn.setAutoRaise(True)
        self._expand_btn.clicked.connect(self._toggle_expand)
        self._update_expand_icon()
        fit_btn.clicked.connect(self._fit_page)
        zoom_in_btn.clicked.connect(self._preview.zoomIn)
        zoom_out_btn.clicked.connect(self._preview.zoomOut)
        actual_btn.clicked.connect(self._actual_size)
        zoom_row.addWidget(zoom_label)
        zoom_row.addWidget(fit_btn)
        zoom_row.addWidget(zoom_in_btn)
        zoom_row.addWidget(zoom_out_btn)
        zoom_row.addWidget(actual_btn)
        zoom_row.addWidget(self._expand_btn)
        zoom_row.addStretch()

        # Page navigation (shared for all report previews).
        page_label = QLabel("Page:")
        self._first_page_btn = QPushButton("First")
        self._prev_page_btn = QPushButton("Previous")
        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.setFixedWidth(64)
        self._page_spin.setToolTip("Go to page")
        self._page_count_label = QLabel("of 1")
        self._next_page_btn = QPushButton("Next")
        self._last_page_btn = QPushButton("Last")
        self._first_page_btn.clicked.connect(self._go_first_page)
        self._prev_page_btn.clicked.connect(self._go_prev_page)
        self._next_page_btn.clicked.connect(self._go_next_page)
        self._last_page_btn.clicked.connect(self._go_last_page)
        self._page_spin.valueChanged.connect(self._go_to_page)
        zoom_row.addWidget(page_label)
        zoom_row.addWidget(self._first_page_btn)
        zoom_row.addWidget(self._prev_page_btn)
        zoom_row.addWidget(self._page_spin)
        zoom_row.addWidget(self._page_count_label)
        zoom_row.addWidget(self._next_page_btn)
        zoom_row.addWidget(self._last_page_btn)
        layout.addLayout(zoom_row)

        layout.addWidget(self._preview, stretch=1)

        actions = QHBoxLayout()
        printer_label = QLabel("Printer:")
        self._printer_combo = QComboBox()
        self._printer_combo.setMinimumWidth(320)
        _populate_printer_combo(self._printer_combo)
        if self._initial_printer_name:
            idx = self._printer_combo.findData(self._initial_printer_name)
            if idx >= 0:
                self._printer_combo.setCurrentIndex(idx)
        copies_label = QLabel("Copies:")
        self._copies_spin = QSpinBox()
        self._copies_spin.setRange(1, 99)
        self._copies_spin.setValue(self._default_copies)
        print_btn = QPushButton("Print")
        more_btn = QPushButton("Print Setup...")
        close_btn = QPushButton("Close")
        print_btn.clicked.connect(self._print)
        more_btn.clicked.connect(self._print_with_dialog)
        close_btn.clicked.connect(self.accept)
        actions.addWidget(printer_label)
        actions.addWidget(self._printer_combo, stretch=1)
        actions.addWidget(copies_label)
        actions.addWidget(self._copies_spin)
        actions.addWidget(print_btn)
        actions.addWidget(more_btn)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        self._fit_page()
        QTimer.singleShot(0, self._update_page_nav)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_expand_icon()
        super().changeEvent(event)

    def _update_expand_icon(self) -> None:
        style = QApplication.style()
        if self.isMaximized():
            self._expand_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton))
            self._expand_btn.setToolTip("Restore")
        else:
            self._expand_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
            self._expand_btn.setToolTip("Expand")

    def _toggle_expand(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_expand_icon()

    def _fit_page(self) -> None:
        self._preview.setZoomMode(QPrintPreviewWidget.ZoomMode.FitInView)
        self._preview.updatePreview()

    def _actual_size(self) -> None:
        self._preview.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
        self._preview.setZoomFactor(1.0)
        self._preview.updatePreview()

    def _update_page_nav(self) -> None:
        total = max(int(self._preview.pageCount() or 1), 1)
        current = int(self._preview.currentPage() or 1)
        current = min(max(current, 1), total)
        self._page_spin.blockSignals(True)
        self._page_spin.setRange(1, total)
        self._page_spin.setValue(current)
        self._page_spin.blockSignals(False)
        self._page_count_label.setText(f"of {total}")
        multi = total > 1
        self._first_page_btn.setEnabled(multi and current > 1)
        self._prev_page_btn.setEnabled(multi and current > 1)
        self._next_page_btn.setEnabled(multi and current < total)
        self._last_page_btn.setEnabled(multi and current < total)
        self._page_spin.setEnabled(multi)

    def _go_to_page(self, page: int) -> None:
        total = max(int(self._preview.pageCount() or 1), 1)
        page = min(max(int(page), 1), total)
        if page != self._preview.currentPage():
            self._preview.setCurrentPage(page)
        self._update_page_nav()

    def _go_first_page(self) -> None:
        self._go_to_page(1)

    def _go_prev_page(self) -> None:
        self._go_to_page(self._preview.currentPage() - 1)

    def _go_next_page(self) -> None:
        self._go_to_page(self._preview.currentPage() + 1)

    def _go_last_page(self) -> None:
        self._go_to_page(self._preview.pageCount())

    def _render_to_printer(self, target: QPrinter) -> None:
        _configure_printer(target, landscape=self._landscape, settings=self._settings)
        target.setCopyCount(self._copies_spin.value())
        document = _build_document(self._html, target)
        document.print_(target)
        # Ensure page nav refreshes after layout/print paint.
        QTimer.singleShot(0, self._update_page_nav)

    def _save_pdf(self) -> None:
        default_name = f"{self._export_stem}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Bill as PDF",
            str(Path.home() / default_name),
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"
        printer = _build_printer(
            for_preview=False,
            pdf_path=path,
            landscape=self._landscape,
            settings=self._settings,
        )
        self._render_to_printer(printer)
        QMessageBox.information(self, "Saved", f"PDF saved successfully:\n{path}")

    def _save_excel(self) -> None:
        default_name = f"{self._export_stem}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save as Excel",
            str(Path.home() / default_name),
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"

        content: bytes | None = None
        errors: list[str] = []

        if self._api and self._report_endpoint:
            try:
                content = self._api.download_report_file(_excel_endpoint(self._report_endpoint))
            except ApiError as exc:
                errors.append(str(exc))

        if content is None and self._api and self._html:
            try:
                content = self._api.export_html_to_excel(
                    html=self._html,
                    title=self.windowTitle() or "Report",
                )
            except ApiError as exc:
                errors.append(str(exc))

        if content is None:
            message = "Excel export is not available for this preview."
            if errors:
                message = f"{message}\n\n{errors[0]}"
            QMessageBox.warning(self, "Save to Excel", message)
            return

        try:
            Path(path).write_bytes(content)
        except OSError as exc:
            QMessageBox.warning(self, "Save to Excel", str(exc))
            return
        QMessageBox.information(self, "Saved", f"Excel file saved successfully:\n{path}")

    def _selected_printer(self) -> QPrinter:
        printer = _build_printer(
            for_preview=False,
            landscape=self._landscape,
            settings=self._settings,
        )
        printer_name = self._printer_combo.currentData()
        if printer_name:
            printer.setPrinterName(printer_name)
        return printer

    def _print(self) -> None:
        printer_name = self._printer_combo.currentData()
        if not printer_name:
            QMessageBox.warning(self, "Print", "No printer is available. Install a printer first.")
            return
        printer = self._selected_printer()
        self._render_to_printer(printer)
        QMessageBox.information(self, "Print", f"Report sent to printer:\n{printer_name}")

    def _print_with_dialog(self) -> None:
        printer = self._selected_printer()
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print")
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        self._render_to_printer(printer)


def show_print_preview(
    html: str,
    *,
    api: ApiClient | None = None,
    report_endpoint: str | None = None,
    parent: QWidget | None = None,
    title: str = "Bill Preview",
    landscape: bool = False,
    printer_name: str | None = None,
    settings: ResolvedPrintSettings | None = None,
    default_copies: int | None = None,
) -> None:
    dialog = BillPrintPreviewDialog(
        html,
        api=api,
        report_endpoint=report_endpoint,
        parent=parent,
        title=title,
        landscape=landscape,
        printer_name=printer_name,
        settings=settings,
        default_copies=default_copies,
    )
    dialog.exec()


def _direct_print(
    html: str,
    *,
    parent: QWidget | None = None,
    landscape: bool = False,
    settings: ResolvedPrintSettings | None = None,
    title: str = "Print",
) -> bool:
    names, _ = _installed_printers()
    if not names:
        QMessageBox.warning(parent, "Print", "No printer is available. Install a printer first.")
        return False
    printer_name = settings.printer_name if settings and settings.printer_name else None
    if printer_name and printer_name not in names:
        QMessageBox.warning(
            parent,
            "Print",
            f"Configured printer not found:\n{printer_name}\n\n"
            "Check Print Master or install the printer on this PC.",
        )
        return False
    printer = _build_printer(
        for_preview=False,
        landscape=landscape,
        settings=settings,
        printer_name=printer_name,
    )
    _configure_printer(printer, landscape=landscape, settings=settings)
    document = _build_document(html, printer)
    document.print_(printer)
    display_name = printer_name or QPrinterInfo.defaultPrinter().printerName() or "default printer"
    QMessageBox.information(parent, title, f"Sent to printer:\n{display_name}")
    return True


def print_html(html: str, *, parent: QWidget | None = None) -> None:
    show_print_preview(html, parent=parent, title="Bill Preview")


def preview_report(
    api: ApiClient,
    endpoint: str,
    *,
    parent: QWidget | None = None,
    title: str = "Bill Preview",
    landscape: bool = False,
    printer_name: str | None = None,
    report_code: str | None = None,
    default_copies: int | None = None,
) -> None:
    settings = _resolve_print_settings(api, report_code)
    if settings:
        landscape = settings.orientation == "landscape"
    try:
        html = api.download_report_html(_html_endpoint(endpoint))
    except ApiError as exc:
        QMessageBox.warning(parent, "Preview", str(exc))
        return
    if not html.strip():
        QMessageBox.warning(parent, "Preview", "Empty bill preview received from server.")
        return
    show_print_preview(
        html,
        api=api,
        report_endpoint=endpoint,
        parent=parent,
        title=title,
        landscape=landscape,
        printer_name=printer_name,
        settings=settings,
        default_copies=default_copies,
    )


def print_report(
    api: ApiClient,
    endpoint: str,
    *,
    parent: QWidget | None = None,
    title: str = "Bill Preview",
    landscape: bool = False,
    report_code: str | None = None,
    silent_success: bool = False,
) -> None:
    settings = _resolve_print_settings(api, report_code)
    if settings:
        landscape = settings.orientation == "landscape"
    try:
        html = api.download_report_html(_html_endpoint(endpoint))
    except ApiError as exc:
        QMessageBox.warning(parent, "Print", str(exc))
        return
    if not html.strip():
        QMessageBox.warning(parent, "Print", "Empty report received from server.")
        return
    if settings and settings.print_mode == "direct":
        if silent_success:
            names, _ = _installed_printers()
            if not names:
                QMessageBox.warning(parent, "Print", "No printer is available. Install a printer first.")
                return
            printer_name = settings.printer_name
            if printer_name and printer_name not in names:
                QMessageBox.warning(
                    parent,
                    "Print",
                    f"Configured printer not found:\n{printer_name}",
                )
                return
            printer = _build_printer(for_preview=False, landscape=landscape, settings=settings)
            _configure_printer(printer, landscape=landscape, settings=settings)
            document = _build_document(html, printer)
            document.print_(printer)
            return
        _direct_print(html, parent=parent, landscape=landscape, settings=settings, title=title)
        return
    show_print_preview(
        html,
        api=api,
        report_endpoint=endpoint,
        parent=parent,
        title=title,
        landscape=landscape,
        settings=settings,
    )
