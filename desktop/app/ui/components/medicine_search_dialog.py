from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.responsive_layout import fit_dialog_size

GRID_STYLE = """
QTableWidget {
    gridline-color: #94a3b8;
    font-size: 11px;
}
QHeaderView::section {
    background: #e2e8f0;
    border: 1px solid #94a3b8;
    padding: 4px;
    font-weight: bold;
}
"""


def pick_medicine(
    api: ApiClient,
    parent: QWidget | None = None,
    *,
    initial: str = "",
    matches: list[dict] | None = None,
) -> dict | None:
    dialog = MedicineSearchDialog(api, parent, initial=initial, matches=matches)
    return dialog.selected_medicine() if dialog.exec() == QDialog.DialogCode.Accepted else None


class MedicineSearchDialog(QDialog):
    def __init__(
        self,
        api: ApiClient,
        parent: QWidget | None = None,
        *,
        initial: str = "",
        matches: list[dict] | None = None,
    ):
        super().__init__(parent)
        self.api = api
        self._selected: dict | None = None
        self._matches = matches
        self.setWindowTitle("Medicine Search")
        self.resize(*fit_dialog_size(760, 480))
        self._build_ui()
        if initial:
            self.search_box.setText(initial)
        if matches is not None:
            self._show_results(matches)
        elif initial:
            self._run_search()
        QShortcut(QKeySequence("Alt+S"), self, self._run_search)

    def selected_medicine(self) -> dict | None:
        return self._selected

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Search by medicine name, generic name, or code (partial match):"))

        row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("e.g. para, cipla, PCM")
        self.search_box.returnPressed.connect(self._run_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._run_search)
        row.addWidget(self.search_box, stretch=1)
        row.addWidget(search_btn)
        layout.addLayout(row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Generic", "Unit", "Rate", "Stock"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setStyleSheet(GRID_STYLE)
        self.table.doubleClicked.connect(self._accept_selection)
        layout.addWidget(self.table, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _run_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            return
        try:
            results = self.api.search_pharmacy_medicines(query)
        except ApiError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self._show_results(results)

    def _show_results(self, results: list[dict]) -> None:
        self.table.setRowCount(len(results))
        for row, item in enumerate(results):
            rate = item.get("sale_rate") or item.get("mrp")
            self.table.setItem(row, 0, QTableWidgetItem(item.get("code", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("generic_name") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("unit") or ""))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(rate):.2f}" if rate else ""))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.get("stock_qty", 0))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item)
        if results:
            self.table.selectRow(0)

    def _accept_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Select", "Select a medicine from the list.")
            return
        item = self.table.item(rows[0].row(), 0)
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
