"""Convert HTML report tables into an Excel workbook."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


class _TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_parts: list[str] = []
        self.headings: list[str] = []
        self._capture_heading = False
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3"}:
            self._capture_heading = True
            self._heading_parts = []
        elif tag == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []
        elif self._in_cell and tag == "br":
            self._cell_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3"} and self._capture_heading:
            text = self._clean("".join(self._heading_parts))
            if text:
                self.headings.append(text)
            self._capture_heading = False
            self._heading_parts = []
        elif tag in {"td", "th"} and self._in_cell:
            self._current_row.append(self._clean("".join(self._cell_parts)))
            self._in_cell = False
            self._cell_parts = []
        elif tag == "tr" and self._in_row:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._in_row = False
            self._current_row = []
        elif tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False
            self._current_table = []

    def handle_data(self, data: str) -> None:
        if self._capture_heading:
            self._heading_parts.append(data)
        elif self._in_cell:
            self._cell_parts.append(data)

    @staticmethod
    def _clean(value: str) -> str:
        value = value.replace("\xa0", " ")
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n+", "\n", value)
        return value.strip()


def html_tables_to_excel(
    html: str,
    *,
    title: str = "Report",
    data_only: bool = False,
) -> bytes:
    """Convert HTML tables to Excel.

    When data_only=True, skips the window title, page headings (h1–h3), and
    "Table N" labels — useful for exports that should not carry print headers.
    """
    parser = _TableExtractor()
    parser.feed(html or "")
    parser.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    row = 1
    if not data_only:
        ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=14)
        row += 1
        for heading in parser.headings[:8]:
            ws.cell(row=row, column=1, value=heading).font = Font(bold=True)
            row += 1
        row += 1

    if not parser.tables:
        ws.cell(row=row, column=1, value="No tabular data found in preview.")
    else:
        max_col = 1
        for table_index, table in enumerate(parser.tables, start=1):
            if table_index > 1:
                row += 1
            if not data_only:
                ws.cell(row=row, column=1, value=f"Table {table_index}").font = Font(
                    bold=True, color="1E40AF"
                )
                row += 1
            for table_row in table:
                for col, value in enumerate(table_row, start=1):
                    ws.cell(row=row, column=col, value=value)
                    max_col = max(max_col, col)
                row += 1
            row += 1
        for col in range(1, max_col + 1):
            letter = get_column_letter(col)
            width = 12
            for cell in ws[letter]:
                if cell.value is not None:
                    width = max(width, min(len(str(cell.value)) + 2, 40))
            ws.column_dimensions[letter].width = width

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
