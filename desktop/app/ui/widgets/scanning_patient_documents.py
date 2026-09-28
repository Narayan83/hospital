from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.services.pdf_optimizer import images_to_pdf, normalize_to_pdf
from app.services.scanner import list_scanners, scan_images
from app.services.scanner_prefs import ScannerDevice, ScannerPreferences
from app.ui.widgets.opd_bill import HEADER_BTN_STYLE

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    _HAS_PDF_VIEW = True
except ImportError:
    QPdfDocument = None  # type: ignore[misc, assignment]
    QPdfView = None  # type: ignore[misc, assignment]
    _HAS_PDF_VIEW = False

HISTORY_ROW_COLOR = QColor("#f1f5f9")


def _pdf_load_ok(error) -> bool:
    """QPdfDocument.load() returns an enum that is not int-convertible in PySide6."""
    if QPdfDocument is None:
        return False
    return error == QPdfDocument.Error.None_


def _render_pdf_page(path: Path, page_index: int, *, max_width: int = 780) -> QPixmap | None:
    if QPdfDocument is None or not path.exists():
        return None
    doc = QPdfDocument()
    err = doc.load(str(path))
    if not _pdf_load_ok(err) or page_index < 0 or page_index >= doc.pageCount():
        doc.close()
        return None
    point = doc.pagePointSize(page_index)
    if point.width() <= 0 or point.height() <= 0:
        doc.close()
        return None
    scale = max_width / float(point.width())
    target = QSize(max(1, int(point.width() * scale)), max(1, int(point.height() * scale)))
    image: QImage = doc.render(page_index, target)
    doc.close()
    if image.isNull():
        return None
    return QPixmap.fromImage(image)


def _print_pdf_paths(parent: QWidget, paths: list[Path], *, title: str = "Print Documents") -> None:
    existing = [path for path in paths if path and path.exists()]
    if not existing:
        QMessageBox.information(parent, title, "No documents available to print.")
        return
    if QPdfDocument is None:
        # Fallback: open first externally for manual print.
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(existing[0])))
        QMessageBox.information(
            parent,
            title,
            "PDF print preview is unavailable. Opened the first file — use the system print dialog.",
        )
        return

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(title)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(title)
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return

    painter = QPainter()
    if not painter.begin(printer):
        QMessageBox.warning(parent, title, "Could not start printer.")
        return

    first_page = True
    try:
        for path in existing:
            doc = QPdfDocument()
            err = doc.load(str(path))
            if not _pdf_load_ok(err):
                continue
            for page_index in range(doc.pageCount()):
                if not first_page:
                    printer.newPage()
                first_page = False
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                point = doc.pagePointSize(page_index)
                if point.width() <= 0 or point.height() <= 0:
                    continue
                scale = min(
                    page_rect.width() / float(point.width()),
                    page_rect.height() / float(point.height()),
                )
                target = QSize(
                    max(1, int(point.width() * scale)),
                    max(1, int(point.height() * scale)),
                )
                image = doc.render(page_index, target)
                if image.isNull():
                    continue
                x = int((page_rect.width() - image.width()) / 2)
                y = int((page_rect.height() - image.height()) / 2)
                painter.drawImage(x, y, image)
            doc.close()
    finally:
        painter.end()


class ViewAllDocumentsDialog(QDialog):
    """Scrollable gallery of all documents (every page stacked vertically)."""

    def __init__(
        self,
        parent: QWidget | None,
        items: list[tuple[str, Path]],
    ):
        super().__init__(parent)
        self.setWindowTitle("View All Scanned Documents")
        self.resize(860, 720)
        self.setMinimumSize(640, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QLabel(f"All documents — scroll to review ({len(items)} file(s))")
        header.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f766e;")
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(4, 4, 12, 4)
        host_layout.setSpacing(16)

        if not items:
            empty = QLabel("No documents to show.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #64748b; padding: 40px;")
            host_layout.addWidget(empty)
        else:
            for index, (label, path) in enumerate(items, start=1):
                section = QFrame()
                section.setStyleSheet(
                    "QFrame { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; }"
                )
                section_layout = QVBoxLayout(section)
                section_layout.setContentsMargins(12, 10, 12, 12)
                section_layout.setSpacing(8)

                title = QLabel(f"{index}. {label}")
                title.setWordWrap(True)
                title.setStyleSheet(
                    "font-weight: 700; color: #0f172a; font-size: 13px; border: none; background: transparent;"
                )
                section_layout.addWidget(title)

                meta = QLabel(str(path.name))
                meta.setStyleSheet("color: #64748b; font-size: 11px; border: none; background: transparent;")
                section_layout.addWidget(meta)

                if QPdfDocument is None or not path.exists():
                    note = QLabel("Preview unavailable for this file.")
                    note.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
                    section_layout.addWidget(note)
                else:
                    doc = QPdfDocument()
                    err = doc.load(str(path))
                    page_count = doc.pageCount() if _pdf_load_ok(err) else 0
                    doc.close()
                    if page_count <= 0:
                        note = QLabel("Could not load PDF pages.")
                        note.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
                        section_layout.addWidget(note)
                    else:
                        for page_index in range(page_count):
                            page_label = QLabel(f"Page {page_index + 1} of {page_count}")
                            page_label.setStyleSheet(
                                "color: #475569; font-size: 11px; font-weight: 600; "
                                "border: none; background: transparent;"
                            )
                            section_layout.addWidget(page_label)
                            pixmap = _render_pdf_page(path, page_index, max_width=760)
                            image_label = QLabel()
                            image_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                            image_label.setStyleSheet(
                                "background: white; border: 1px solid #e2e8f0; border-radius: 4px;"
                            )
                            if pixmap is not None:
                                image_label.setPixmap(pixmap)
                            else:
                                image_label.setText("(page could not be rendered)")
                                image_label.setMinimumHeight(120)
                            section_layout.addWidget(image_label)

                host_layout.addWidget(section)

        host_layout.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


@dataclass
class PendingDocument:
    pdf_path: Path
    page_count: int
    file_size: int
    source_label: str
    status: str = "Pending"


class ScannerSelectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Scanner")
        self._selected: ScannerDevice | None = None
        self._devices = list_scanners()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the scanning machine to use:"))
        self.combo = QComboBox()
        for device in self._devices:
            self.combo.addItem(device.name, device.device_id)
        layout.addWidget(self.combo)
        if not self._devices:
            layout.addWidget(
                QLabel(
                    "No WIA scanners detected. Install scanner drivers or use "
                    "'Add from File' after scanning to disk."
                )
            )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_device(self) -> ScannerDevice | None:
        if not self._devices:
            return None
        idx = self.combo.currentIndex()
        if idx < 0:
            return None
        return ScannerDevice(
            device_id=self.combo.itemData(idx),
            name=self.combo.itemText(idx),
        )


class ScanningPatientDocumentsWidget(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._prefs = ScannerPreferences()
        self._scanner: ScannerDevice | None = self._prefs.get_default()
        self._patient: dict | None = None
        self._pending: list[PendingDocument] = []
        self._history: list[dict] = []
        self._history_cache: dict[str, Path] = {}
        self._history_load_errors: dict[str, str] = {}
        self._pdf_doc = None
        self._build_ui()
        self._refresh_scanner_label()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Scanning Patient Documents")
        heading.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f766e;")
        layout.addWidget(heading)

        scanner_row = QHBoxLayout()
        self.scanner_label = QLabel()
        self.scanner_label.setStyleSheet("font-weight: 600;")
        select_scanner_btn = QPushButton("Select Scanner")
        select_scanner_btn.setStyleSheet(HEADER_BTN_STYLE)
        select_scanner_btn.clicked.connect(self._select_scanner)
        scanner_row.addWidget(QLabel("Scanner"))
        scanner_row.addWidget(self.scanner_label, stretch=1)
        scanner_row.addWidget(select_scanner_btn)
        layout.addLayout(scanner_row)

        patient_row = QHBoxLayout()
        self.patient_no = QLineEdit()
        self.patient_no.setPlaceholderText("Enter Patient ID")
        self.patient_no.returnPressed.connect(lambda: self._lookup_patient(show_errors=True))
        self.patient_no.editingFinished.connect(self._on_patient_id_finished)
        lookup_btn = QPushButton("Lookup")
        lookup_btn.setStyleSheet(HEADER_BTN_STYLE)
        # clicked passes a checked bool — do not bind _lookup_patient directly.
        lookup_btn.clicked.connect(lambda: self._lookup_patient(show_errors=True))
        self.patient_name = QLineEdit()
        self.patient_name.setReadOnly(True)
        self.patient_name.setPlaceholderText("Patient name")
        patient_row.addWidget(QLabel("Patient ID"))
        patient_row.addWidget(self.patient_no, stretch=1)
        patient_row.addWidget(lookup_btn)
        patient_row.addWidget(QLabel("Patient Name"))
        patient_row.addWidget(self.patient_name, stretch=2)
        layout.addLayout(patient_row)

        hint = QLabel(
            "Enter Patient ID and press Lookup (or Enter) to load saved history (latest first). "
            "Scan / Add from File saves immediately — documents remain available after logout."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        for label, handler in (
            ("Scan", self._scan_document),
            ("Add from File", self._add_from_file),
            ("Submit Selected", self._submit_selected),
            ("Submit All", self._submit_all),
            ("Remove Selected", self._remove_selected),
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(HEADER_BTN_STYLE)
            btn.clicked.connect(handler)
            action_row.addWidget(btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        view_row = QHBoxLayout()
        for label, handler in (
            ("View All", self._view_all),
            ("Download Selected", self._download_selected),
            ("Download All", self._download_all),
            ("Print Single", self._print_single),
            ("Print Selected", self._print_selected),
            ("Print All", self._print_all),
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(HEADER_BTN_STYLE)
            btn.clicked.connect(handler)
            view_row.addWidget(btn)
        view_row.addStretch()
        layout.addLayout(view_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_title = QLabel("Documents — new scans + old history (latest on top)")
        left_title.setStyleSheet("font-weight: 600; color: #334155;")
        left_layout.addWidget(left_title)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Slno", "File", "Pages", "Size (KB)", "Status", "Source", "Date"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.table, stretch=1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        preview_header = QHBoxLayout()
        preview_title = QLabel("Preview")
        preview_title.setStyleSheet("font-weight: 600; color: #334155;")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()
        open_btn = QPushButton("Open Externally")
        open_btn.setStyleSheet(HEADER_BTN_STYLE)
        open_btn.clicked.connect(self._open_selected_externally)
        preview_header.addWidget(open_btn)
        right_layout.addLayout(preview_header)

        if _HAS_PDF_VIEW:
            self._pdf_doc = QPdfDocument(self)
            self.preview = QPdfView(self)
            self.preview.setDocument(self._pdf_doc)
            self.preview.setZoomMode(QPdfView.ZoomMode.FitInView)
            # Scroll through all pages of the selected PDF in the side preview.
            self.preview.setPageMode(QPdfView.PageMode.MultiPage)
            self.preview.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1;")
            right_layout.addWidget(self.preview, stretch=1)
            self.preview_fallback = None
        else:
            self.preview = None
            self.preview_fallback = QLabel("Select a document to preview")
            self.preview_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_fallback.setWordWrap(True)
            self.preview_fallback.setStyleSheet(
                "background: #f8fafc; border: 1px solid #cbd5e1; color: #64748b; padding: 12px;"
            )
            self.preview_fallback.setMinimumWidth(320)
            right_layout.addWidget(self.preview_fallback, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([560, 420])
        layout.addWidget(splitter, stretch=1)

        self.status = QLabel()
        self.status.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status)

    def refresh(self) -> None:
        self._refresh_scanner_label()

    def _refresh_scanner_label(self) -> None:
        if self._scanner:
            self.scanner_label.setText(self._scanner.name)
        else:
            self.scanner_label.setText("Not selected — click Select Scanner")

    def _select_scanner(self) -> None:
        dialog = ScannerSelectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        device = dialog.selected_device()
        if not device:
            QMessageBox.warning(self, "Scanner", "No scanner selected.")
            return
        self._scanner = device
        self._prefs.set_default(device)
        self._refresh_scanner_label()

    @staticmethod
    def _patient_display_name(patient: dict) -> str:
        parts = [patient.get("first_name"), patient.get("middle_name"), patient.get("last_name")]
        name = " ".join(p for p in parts if p).strip()
        if name:
            return name
        return (patient.get("full_name") or patient.get("patient_name") or "").strip()

    def _on_patient_id_finished(self) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            self._clear_patient_docs()
            return
        current = (self._patient or {}).get("patient_no") or ""
        if current.strip().upper() == patient_no.upper():
            if not self.patient_name.text().strip() and self._patient:
                self.patient_name.setText(self._patient_display_name(self._patient))
            self._load_history()
            return
        self._lookup_patient(show_errors=False)

    def _clear_patient_docs(self) -> None:
        self._patient = None
        self.patient_name.clear()
        self._history = []
        self._pending = []
        self._history_cache.clear()
        self._history_load_errors.clear()
        self._reload_table()
        self.status.clear()

    def _lookup_patient(self, *, show_errors: bool = True) -> None:
        patient_no = self.patient_no.text().strip()
        if not patient_no:
            self._clear_patient_docs()
            return

        same_patient = (
            self._patient
            and (self._patient.get("patient_no") or "").strip().upper() == patient_no.upper()
        )
        if same_patient:
            self.patient_name.setText(self._patient_display_name(self._patient))
            self._load_history()
            return

        try:
            result = self.api.search_patients(patient_no=patient_no, page_size=10)
            items = [
                item
                for item in (result.get("items") or [])
                if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
            ]
            if not items:
                result = self.api.list_patients(search=patient_no, page_size=20)
                items = [
                    item
                    for item in (result.get("items") or [])
                    if (item.get("patient_no") or "").strip().upper() == patient_no.upper()
                ]
            patient = items[0] if items else None
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Patient", str(exc))
            return
        except Exception as exc:
            if show_errors:
                QMessageBox.warning(self, "Patient", f"Connection error: {exc}")
            return

        if not patient:
            self._clear_patient_docs()
            if show_errors:
                QMessageBox.warning(self, "Patient", f"No patient found for ID '{patient_no}'.")
            return

        # Switching patient clears pending scans for the previous patient.
        self._pending = []
        self._patient = patient
        self.patient_no.setText(patient.get("patient_no", patient_no))
        self.patient_name.setText(self._patient_display_name(patient))
        self._load_history()

    def _load_history(self) -> None:
        if not self._patient or not self._patient.get("id"):
            self._history = []
            self._reload_table()
            return
        try:
            docs = self.api.list_patient_documents(patient_id=self._patient["id"]) or []
        except ApiError as exc:
            self._history = []
            self.status.setText(f"Could not load history: {exc}")
            self._reload_table()
            return
        except Exception as exc:
            self._history = []
            self.status.setText(f"Could not load history: {exc}")
            self._reload_table()
            return
        # Newest document_date first, then newest created_at.
        self._history = sorted(
            list(docs),
            key=lambda doc: (
                str(doc.get("document_date") or ""),
                str(doc.get("created_at") or ""),
            ),
            reverse=True,
        )
        self._history_load_errors.clear()
        self._reload_table(select_row=0 if (self._pending or self._history) else None)
        pending_n = len(self._pending)
        hist_n = len(self._history)
        name = self.patient_name.text().strip() or self._patient_display_name(self._patient)
        self.status.setText(
            f"{name}: {hist_n} saved document(s)"
            + (f" · {pending_n} pending to submit" if pending_n else "")
            + " (latest on top)."
        )

    def _require_patient(self) -> dict | None:
        patient_no = self.patient_no.text().strip()
        if (
            self._patient
            and (self._patient.get("patient_no") or "").strip().upper() == patient_no.upper()
        ):
            if not self.patient_name.text().strip():
                self.patient_name.setText(self._patient_display_name(self._patient))
            return self._patient
        self._lookup_patient(show_errors=True)
        if not self._patient:
            QMessageBox.warning(self, "Validation", "Enter a valid Patient ID first.")
        return self._patient

    def _scan_document(self) -> None:
        if not self._require_patient():
            return
        if not self._scanner:
            QMessageBox.warning(self, "Scanner", "Select a scanner machine first.")
            return
        try:
            images = scan_images(self._scanner.device_id)
            pdf_path, page_count = images_to_pdf(images)
            self._add_pending(
                pdf_path,
                page_count=page_count,
                source_label=f"Scanner: {self._scanner.name}",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Scan Failed",
                f"{exc}\n\nYou can scan to disk and use 'Add from File' instead.",
            )

    def _add_from_file(self) -> None:
        if not self._require_patient():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Scanned Images or PDF",
            "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp);;All Files (*.*)",
        )
        if not paths:
            return
        image_paths = [Path(p) for p in paths if Path(p).suffix.lower() != ".pdf"]
        pdf_paths = [Path(p) for p in paths if Path(p).suffix.lower() == ".pdf"]
        try:
            if image_paths:
                pdf_path, page_count = images_to_pdf(image_paths)
                self._add_pending(pdf_path, page_count=page_count, source_label="File import")
            for pdf_path in pdf_paths:
                normalized, page_count = normalize_to_pdf(pdf_path)
                self._add_pending(normalized, page_count=page_count, source_label=pdf_path.name)
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))

    def _add_pending(self, pdf_path: Path, *, page_count: int, source_label: str) -> None:
        """Queue a local PDF, then immediately persist it so history survives logout."""
        size = pdf_path.stat().st_size
        pending = PendingDocument(
            pdf_path=pdf_path,
            page_count=page_count,
            file_size=size,
            source_label=source_label,
        )
        self._pending.insert(0, pending)
        self._reload_table(select_row=0)
        self.status.setText(
            f"Saving… · {len(self._pending)} pending · {len(self._history)} previously saved."
        )
        self._auto_submit_pending(pending)

    def _auto_submit_pending(self, item: PendingDocument) -> None:
        """Upload one pending scan right away; keep it pending if upload fails."""
        patient = self._require_patient()
        if not patient:
            return
        scanner_name = self._scanner.name if self._scanner else None
        try:
            self.api.upload_patient_document(
                patient_id=patient["id"],
                file_path=str(item.pdf_path),
                page_count=item.page_count,
                scanner_name=scanner_name or (
                    item.source_label if item.source_label.startswith("Scanner:") else None
                ),
                document_date=date.today().isoformat(),
                original_name=item.pdf_path.name,
                remarks=item.source_label or None,
            )
            item.status = "Submitted"
            self._pending = [row for row in self._pending if row is not item]
            self._load_history()
            self.status.setText(
                f"Saved. {len(self._history)} document(s) on file for this patient (latest on top)."
            )
        except ApiError as exc:
            item.status = "Error"
            self._reload_table(select_row=0)
            self.status.setText(f"Save failed — use Submit All to retry. {exc}")
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Document stayed as pending.\n\n{exc}\n\nUse Submit All to retry.",
            )
        except Exception as exc:
            item.status = "Error"
            self._reload_table(select_row=0)
            self.status.setText(f"Save failed — use Submit All to retry. {exc}")
            QMessageBox.warning(
                self,
                "Save Failed",
                f"Document stayed as pending.\n\n{exc}\n\nUse Submit All to retry.",
            )

    def _display_rows(self) -> list[tuple[str, object]]:
        """Pending (newest first) then saved history (newest first)."""
        rows: list[tuple[str, object]] = [("pending", item) for item in self._pending]
        rows.extend(("history", doc) for doc in self._history)
        return rows

    def _reload_table(self, *, select_row: int | None = None) -> None:
        rows = self._display_rows()
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for row, (kind, payload) in enumerate(rows):
            if kind == "pending":
                item = payload  # PendingDocument
                values = [
                    str(row + 1),
                    item.pdf_path.name,
                    str(item.page_count),
                    f"{item.file_size // 1024}",
                    item.status,
                    item.source_label,
                    date.today().isoformat(),
                ]
                bg = None
            else:
                doc = payload  # dict
                values = [
                    str(row + 1),
                    doc.get("original_name") or Path(doc.get("file_path") or "").name or "document.pdf",
                    str(doc.get("page_count") or ""),
                    str((doc.get("file_size_bytes") or 0) // 1024),
                    "Saved",
                    doc.get("scanner_name") or "History",
                    str(doc.get("document_date") or "")[:10],
                ]
                bg = HISTORY_ROW_COLOR
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setData(Qt.ItemDataRole.UserRole, kind)
                if bg is not None:
                    cell.setBackground(bg)
                self.table.setItem(row, col, cell)
        self.table.blockSignals(False)

        if select_row is not None and 0 <= select_row < len(rows):
            self.table.selectRow(select_row)
            self._preview_row(select_row)
        elif rows:
            current = self.table.currentRow()
            if current < 0 or current >= len(rows):
                self.table.selectRow(0)
                self._preview_row(0)
            else:
                self._preview_row(current)
        else:
            self._clear_preview()

    def _on_selection_changed(self) -> None:
        rows = self._selected_rows()
        if not rows:
            self._clear_preview()
            return
        self._preview_row(rows[0])

    def _preview_row(self, row: int) -> None:
        rows = self._display_rows()
        if row < 0 or row >= len(rows):
            self._clear_preview()
            return
        kind, payload = rows[row]
        if kind == "pending":
            self._show_preview_path(payload.pdf_path, payload.page_count)
            return
        doc = payload
        path = self._history_local_path(doc)
        if path:
            self._show_preview_path(path, int(doc.get("page_count") or 1))
        else:
            err = self._history_load_errors.get(str(doc.get("id") or ""))
            self._set_fallback_text(
                "Could not load saved document for preview."
                + (f"\n{err}" if err else "\nFile may be missing on the server.")
            )

    def _history_local_path(self, doc: dict) -> Path | None:
        doc_id = doc.get("id")
        if not doc_id:
            return None
        cached = self._history_cache.get(doc_id)
        if cached and cached.exists():
            return cached
        try:
            content = self.api.download_patient_document_file(doc_id)
            path = Path(tempfile.gettempdir()) / f"hms_hist_{doc_id}.pdf"
            path.write_bytes(content)
            self._history_cache[doc_id] = path
            return path
        except Exception as exc:
            name = doc.get("original_name") or str(doc_id)
            self._history_load_errors[str(doc_id)] = f"{name}: {exc}"
            return None

    def _show_preview_path(self, path: Path, page_count: int = 1) -> None:
        if not path.exists():
            self._clear_preview()
            return
        if self._pdf_doc is not None and self.preview is not None:
            err = self._pdf_doc.load(str(path))
            if not _pdf_load_ok(err):
                self._set_fallback_text(f"Could not preview PDF.\n{path.name}")
            return
        self._set_fallback_text(
            f"Preview: {path.name}\n({page_count} page(s))\nUse Open Externally."
        )

    def _set_fallback_text(self, text: str) -> None:
        if self.preview_fallback is not None:
            self.preview_fallback.setText(text)

    def _clear_preview(self) -> None:
        if self._pdf_doc is not None:
            self._pdf_doc.close()
        self._set_fallback_text("Select a document to preview")

    def _open_selected_externally(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Preview", "Select a document first.")
            return
        display = self._display_rows()
        row = rows[0]
        if row < 0 or row >= len(display):
            return
        kind, payload = display[row]
        if kind == "pending":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(payload.pdf_path)))
            return
        path = self._history_local_path(payload)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            err = self._history_load_errors.get(str(payload.get("id") or ""))
            QMessageBox.warning(
                self,
                "Preview",
                "Could not download document."
                + (f"\n\n{err}" if err else ""),
            )

    def _path_for_display_row(self, row: int) -> tuple[str, Path] | None:
        display = self._display_rows()
        if row < 0 or row >= len(display):
            return None
        kind, payload = display[row]
        if kind == "pending":
            path = payload.pdf_path
            label = f"Pending — {path.name}"
            return (label, path) if path.exists() else None
        path = self._history_local_path(payload)
        if not path:
            return None
        name = payload.get("original_name") or path.name
        date_text = str(payload.get("document_date") or "")[:10]
        label = f"Saved — {name}" + (f" ({date_text})" if date_text else "")
        return label, path

    def _items_for_rows(self, rows: list[int]) -> list[tuple[str, Path]]:
        items: list[tuple[str, Path]] = []
        for row in rows:
            item = self._path_for_display_row(row)
            if item:
                items.append(item)
        return items

    def _all_document_items(self) -> list[tuple[str, Path]]:
        return self._items_for_rows(list(range(len(self._display_rows()))))

    def _view_all(self) -> None:
        if not self._display_rows():
            QMessageBox.information(self, "View All", "No documents to show. Lookup a patient first.")
            return
        self._history_load_errors.clear()
        items = self._all_document_items()
        if not items:
            errors = list(self._history_load_errors.values())
            detail = (
                "Documents are listed for this patient, but the files could not be loaded "
                "from the server."
            )
            if errors:
                detail += "\n\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    detail += f"\n…and {len(errors) - 5} more."
            QMessageBox.warning(self, "View All", detail)
            return
        dialog = ViewAllDocumentsDialog(self, items)
        dialog.exec()

    def _download_items(self, items: list[tuple[str, Path]], *, title: str) -> None:
        if not items:
            errors = list(self._history_load_errors.values())
            detail = "No documents available to download."
            if errors:
                detail += "\n\n" + "\n".join(errors[:5])
            QMessageBox.information(self, title, detail)
            return
        if len(items) == 1:
            _label, src = items[0]
            target, _ = QFileDialog.getSaveFileName(
                self,
                title,
                src.name if src.suffix.lower() == ".pdf" else f"{src.stem}.pdf",
                "PDF Files (*.pdf);;All Files (*.*)",
            )
            if not target:
                return
            try:
                shutil.copy2(src, target)
            except Exception as exc:
                QMessageBox.warning(self, title, str(exc))
                return
            QMessageBox.information(self, title, f"Saved:\n{target}")
            return

        folder = QFileDialog.getExistingDirectory(self, f"{title} — choose folder")
        if not folder:
            return
        folder_path = Path(folder)
        saved = 0
        errors: list[str] = []
        used_names: set[str] = set()
        for index, (_label, src) in enumerate(items, start=1):
            base = src.name if src.suffix.lower() == ".pdf" else f"{src.stem}.pdf"
            name = f"{index:02d}_{base}"
            if name in used_names:
                name = f"{index:02d}_{src.stem}_{src.stat().st_mtime_ns}.pdf"
            used_names.add(name)
            dest = folder_path / name
            try:
                shutil.copy2(src, dest)
                saved += 1
            except Exception as exc:
                errors.append(f"{base}: {exc}")
        if errors:
            QMessageBox.warning(
                self,
                title,
                f"Downloaded {saved} file(s). Errors:\n" + "\n".join(errors[:5]),
            )
        else:
            QMessageBox.information(self, title, f"Downloaded {saved} file(s) to:\n{folder}")

    def _download_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Download", "Select one or more documents in the list.")
            return
        self._download_items(self._items_for_rows(rows), title="Download Selected")

    def _download_all(self) -> None:
        self._history_load_errors.clear()
        items = self._all_document_items()
        if not items:
            errors = list(self._history_load_errors.values())
            detail = "No documents to download."
            if errors:
                detail += "\n\n" + "\n".join(errors[:5])
            QMessageBox.information(self, "Download All", detail)
            return
        self._download_items(items, title="Download All")

    def _print_single(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Print Single", "Select one document to print.")
            return
        items = self._items_for_rows([rows[0]])
        _print_pdf_paths(self, [path for _, path in items], title="Print Single")

    def _print_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(
                self,
                "Print Selected",
                "Select one or more documents (Ctrl+click / Shift+click).",
            )
            return
        items = self._items_for_rows(rows)
        _print_pdf_paths(self, [path for _, path in items], title="Print Selected")

    def _print_all(self) -> None:
        self._history_load_errors.clear()
        items = self._all_document_items()
        if not items:
            errors = list(self._history_load_errors.values())
            detail = "No documents to print."
            if errors:
                detail += "\n\n" + "\n".join(errors[:5])
            QMessageBox.information(self, "Print All", detail)
            return
        _print_pdf_paths(self, [path for _, path in items], title="Print All")

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def _selected_pending_indexes(self) -> list[int]:
        """Map selected table rows to indexes in _pending (skip history rows)."""
        display = self._display_rows()
        pending_indexes: list[int] = []
        for row in self._selected_rows():
            if row < 0 or row >= len(display):
                continue
            kind, _payload = display[row]
            if kind != "pending":
                continue
            # Pending rows occupy the first len(_pending) display slots, newest first.
            pending_indexes.append(row)
        return pending_indexes

    def _remove_selected(self) -> None:
        pending_rows = self._selected_pending_indexes()
        if not pending_rows:
            QMessageBox.information(
                self,
                "Remove",
                "Select pending (unsaved) rows to remove.\nSaved history cannot be removed here.",
            )
            return
        for row in reversed(pending_rows):
            if 0 <= row < len(self._pending):
                self._pending.pop(row)
        self._reload_table(select_row=0 if (self._pending or self._history) else None)
        self.status.setText(
            f"{len(self._pending)} pending to submit · {len(self._history)} previously saved."
        )

    def _submit_selected(self) -> None:
        pending_rows = self._selected_pending_indexes()
        if not pending_rows:
            QMessageBox.information(
                self,
                "Submit",
                "Select pending (unsaved) rows to submit.\nSaved history is already on file.",
            )
            return
        self._submit_pending_indexes(pending_rows)

    def _submit_all(self) -> None:
        if not self._pending:
            QMessageBox.information(self, "Submit", "No pending documents to submit.")
            return
        self._submit_pending_indexes(list(range(len(self._pending))))

    def _submit_pending_indexes(self, pending_indexes: list[int]) -> None:
        patient = self._require_patient()
        if not patient:
            return
        scanner_name = self._scanner.name if self._scanner else None
        submitted = 0
        errors: list[str] = []
        for idx in pending_indexes:
            if idx < 0 or idx >= len(self._pending):
                continue
            item = self._pending[idx]
            if item.status == "Submitted":
                continue
            try:
                self.api.upload_patient_document(
                    patient_id=patient["id"],
                    file_path=str(item.pdf_path),
                    page_count=item.page_count,
                    scanner_name=scanner_name,
                    document_date=date.today().isoformat(),
                    original_name=item.pdf_path.name,
                )
                item.status = "Submitted"
                submitted += 1
            except ApiError as exc:
                item.status = "Error"
                errors.append(str(exc))
            except Exception as exc:
                item.status = "Error"
                errors.append(str(exc))
        self._pending = [item for item in self._pending if item.status != "Submitted"]
        self._load_history()
        if errors:
            QMessageBox.warning(
                self, "Submit", f"Submitted {submitted}. Errors:\n" + "\n".join(errors[:5])
            )
        else:
            QMessageBox.information(
                self, "Submit", f"Submitted {submitted} document(s) successfully."
            )
