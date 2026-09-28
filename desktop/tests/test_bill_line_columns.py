"""Bill-lines Service must stay wide; Category stays compact on every screen."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DESKTOP_ROOT = Path(__file__).resolve().parents[1]
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget

from app.ui.table_utils import _kind_from_label, enable_column_resize


def _app() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


class BillLinesColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def test_category_header_is_short(self) -> None:
        self.assertEqual(_kind_from_label("category"), "short")
        self.assertEqual(_kind_from_label("service"), "text")

    def test_bill_lines_columns_are_draggable_with_compact_category(self) -> None:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Code", "Service", "Category", "Rate", "Qty", "Amount"])
        table.setProperty("hmsColumnKinds", ["code", "text", "short", "number", "number", "number"])
        table.setProperty("hmsNoStretch", True)
        table.setColumnWidth(1, 260)
        table.setColumnWidth(2, 140)
        enable_column_resize(table)
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
            )
        self.assertGreaterEqual(header.sectionSize(1), 260)
        self.assertLessEqual(header.sectionSize(2), 90)
        table.deleteLater()


if __name__ == "__main__":
    unittest.main()
