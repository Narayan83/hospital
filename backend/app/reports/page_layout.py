"""Normalize report HTML so tables and headers use the full printable page width."""

from __future__ import annotations

import re

_PAGE_SHELL_MARKER = 'class="page-shell"'

_PAGE_LAYOUT_STYLES = """
<style id="hms-page-layout">
@page {
  margin: 8mm;
}
html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  color: #000000;
}
body {
  font-family: "Times New Roman", Times, serif;
  color: #000000;
}
table.page-shell {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
table.page-shell > tbody > tr > td {
  width: 100%;
  vertical-align: top;
  text-align: left;
}
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
table[width="100%"], table.data-full, table.meta, table.results {
  width: 100%;
}
td, th, p, span {
  color: #000000;
  word-wrap: break-word;
  overflow-wrap: anywhere;
}
.header-title, .header-sub, .header-meta {
  text-align: center;
  width: 100%;
  color: #000000;
}
</style>
"""


def _inject_layout_styles(html: str) -> str:
    if "hms-page-layout" in html:
        return html
    match = re.search(r"</head>", html, re.IGNORECASE)
    if not match:
        return _PAGE_LAYOUT_STYLES + html
    return html[: match.start()] + _PAGE_LAYOUT_STYLES + html[match.start() :]


def _wrap_body_content(html: str) -> str:
    if _PAGE_SHELL_MARKER in html:
        return html
    match = re.search(r"(<body[^>]*>)(.*?)(</body>)", html, re.DOTALL | re.IGNORECASE)
    if not match:
        return html
    inner = match.group(2).strip()
    wrapped = (
        f"{match.group(1)}"
        f'<table {_PAGE_SHELL_MARKER} width="100%" border="0" cellspacing="0" cellpadding="0">'
        f'<tr><td width="100%" style="width:100%;">'
        f"{inner}"
        f"</td></tr></table>"
        f"{match.group(3)}"
    )
    return html[: match.start()] + wrapped + html[match.end() :]


def _ensure_table_widths(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r"\bwidth\s*=", tag, re.IGNORECASE):
            return tag
        return tag[:-1] + ' width="100%">'

    return re.sub(r"<table\b[^>]*>", repl, html, flags=re.IGNORECASE)


def prepare_report_html(html: str) -> str:
    """Apply shared full-page layout rules to any rendered report template."""
    prepared = _inject_layout_styles(html)
    wrapped = _wrap_body_content(prepared)
    return _ensure_table_widths(wrapped)


def apply_qt_page_width(html: str, page_width_px: float) -> str:
    """Qt QTextDocument resolves percentage table widths against an explicit px shell."""
    width = max(int(round(page_width_px)), 1)
    if _PAGE_SHELL_MARKER not in html:
        html = prepare_report_html(html)
    html = re.sub(
        rf"<table {_PAGE_SHELL_MARKER}[^>]*>",
        f'<table {_PAGE_SHELL_MARKER} width="{width}" border="0" cellspacing="0" '
        f'cellpadding="0" style="width:{width}px;max-width:{width}px;margin:0;padding:0;">',
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    for pattern in (
        '<tr><td width="100%" style="width:100%;">',
        '<tr><td width="100%">',
    ):
        if pattern in html:
            html = html.replace(
                pattern,
                f'<tr><td width="{width}" style="width:{width}px;max-width:{width}px;'
                f'margin:0;padding:0;">',
                1,
            )
            break
    extra_style = (
        f'<style id="hms-qt-page-width">'
        f"html,body{{margin:0;padding:0;width:{width}px;max-width:{width}px;color:#000000;}}"
        f"table.page-shell{{width:{width}px;max-width:{width}px;}}"
        f"table.page-shell > tbody > tr > td{{width:{width}px;max-width:{width}px;}}"
        f"table{{width:100%;table-layout:fixed;border-collapse:collapse;}}"
        f"td,th,p,span{{color:#000000;}}"
        f"</style>"
    )
    if "hms-qt-page-width" not in html:
        html = re.sub(r"</head>", extra_style + "</head>", html, count=1, flags=re.IGNORECASE)
    else:
        html = re.sub(
            r'<style id="hms-qt-page-width">.*?</style>',
            extra_style,
            html,
            count=1,
            flags=re.DOTALL,
        )
    return html
