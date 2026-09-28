from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient, ApiError
from app.ui.components.medicine_search_dialog import pick_medicine


class MedicineIncrementalSearch(QWidget):
    """Live medicine search — results appear as you type."""

    def __init__(
        self,
        api: ApiClient,
        on_selected: Callable[[dict], None],
        parent: QWidget | None = None,
        *,
        local_catalog: Callable[[], list[dict]] | None = None,
    ):
        super().__init__(parent)
        self.api = api
        self._on_selected = on_selected
        self._local_catalog = local_catalog or (lambda: [])
        self._results: list[dict] = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._run_search)
        self._build_ui()

    def focus_search(self) -> None:
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type medicine name or code — results appear as you type...")
        self.search_box.textChanged.connect(self._on_text_changed)
        self.search_box.returnPressed.connect(self._accept_highlighted)

        browse_btn = QPushButton("Browse (F3)")
        browse_btn.clicked.connect(self._browse_all)
        row.addWidget(self.search_box, stretch=1)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(self.status)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(160)
        self.results_list.setAlternatingRowColors(True)
        self.results_list.itemDoubleClicked.connect(self._accept_item)
        self.results_list.itemActivated.connect(self._accept_item)
        self.results_list.hide()
        layout.addWidget(self.results_list)

        self.search_box.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.search_box and self.results_list.isVisible():
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self.results_list.setFocus()
                    if self.results_list.count():
                        self.results_list.setCurrentRow(0 if key == Qt.Key.Key_Down else self.results_list.count() - 1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._accept_highlighted()
                    return True
                if key == Qt.Key.Key_Escape:
                    self._hide_results()
                    return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text: str) -> None:
        query = text.strip()
        if len(query) < 2:
            self._hide_results()
            self.status.setText("")
            return
        self.status.setText("Searching...")
        self._debounce.start(280)

    def _run_search(self) -> None:
        query = self.search_box.text().strip()
        if len(query) < 2:
            self._hide_results()
            return
        self._results = self._search(query)
        self.results_list.clear()
        if not self._results:
            self.status.setText(f"No match for '{query}'")
            self._hide_results()
            return
        self.status.setText(f"{len(self._results)} match(es) — select one, then enter quantity")
        for item in self._results:
            rate = item.get("sale_rate") or item.get("mrp") or 0
            label = (
                f"{item.get('code', '')}  |  {item.get('name', '')}  |  "
                f"Rate {float(rate):.2f}  |  Stock {item.get('stock_qty', 0)}"
            )
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.results_list.addItem(row)
        self.results_list.show()

    def _search(self, query: str) -> list[dict]:
        try:
            return self.api.search_pharmacy_medicines(query)
        except ApiError:
            pass
        needle = query.lower()
        local: list[dict] = []
        for item in self._local_catalog():
            hay = " ".join(
                [item.get("code", ""), item.get("name", ""), item.get("generic_name") or ""]
            ).lower()
            if needle in hay:
                local.append({**item, "stock_qty": item.get("stock_qty", 0)})
        return local[:25]

    def _accept_highlighted(self) -> None:
        if self.results_list.isVisible() and self.results_list.currentItem():
            self._accept_item(self.results_list.currentItem())
            return
        if len(self._results) == 1:
            self._select_medicine(self._results[0])
            return
        if self._results:
            self.results_list.setFocus()
            self.results_list.setCurrentRow(0)
            return
        self._browse_all()

    def _accept_item(self, item: QListWidgetItem | None) -> None:
        if not item:
            return
        medicine = item.data(Qt.ItemDataRole.UserRole)
        if medicine:
            self._select_medicine(medicine)

    def _select_medicine(self, medicine: dict) -> None:
        self._hide_results()
        self.search_box.clear()
        self.status.setText(f"Selected: {medicine.get('name', '')}")
        self._on_selected(medicine)

    def _browse_all(self) -> None:
        initial = self.search_box.text().strip()
        chosen = pick_medicine(
            self.api,
            self,
            initial=initial,
            matches=self._results if self._results else None,
        )
        if chosen:
            self._select_medicine(chosen)

    def _hide_results(self) -> None:
        self.results_list.clear()
        self.results_list.hide()
