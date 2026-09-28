"""Responsive layout helpers — applied automatically to every HMS form page.

Spacing and field sizes scale from the primary screen's available height so
short displays stay readable (no clipped inputs) and tall displays use space
instead of leaving large empty gaps or overlapping controls.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class UiDensity:
    """Viewport-derived spacing tokens used by styles and form pages.

    field_min_height and compact_field_height are kept equal so compact
    stylesheets never clip text under the global form field style.
    """

    name: str
    field_min_height: int
    field_v_pad: int
    field_h_pad: int
    font_size: int
    title_font_size: int
    label_font_size: int
    form_v_spacing: int
    form_h_spacing: int
    group_margin_top: int
    group_pad_top: int
    group_pad_sides: int
    group_pad_bottom: int
    compact_field_height: int
    compact_v_pad: int
    compact_font_size: int
    date_height: int
    date_compact_height: int
    content_margin: int
    section_spacing: int
    payment_row_height: int
    payment_row_compact: int
    btn_pad_v: int
    btn_pad_h: int


# Short laptop / remote desktop (~768), normal (~900–1080), tall / 1440+
# Font and field height always move together so text never clips inside boxes.
# Kept deliberately compact across every tier so forms/dialogs fit on screen
# without scrolling and fields don't balloon on taller/high-res displays.
_DENSITY_COMPACT = UiDensity(
    name="compact",
    field_min_height=21,
    field_v_pad=1,
    field_h_pad=6,
    font_size=11,
    title_font_size=14,
    label_font_size=11,
    form_v_spacing=3,
    form_h_spacing=8,
    group_margin_top=5,
    group_pad_top=5,
    group_pad_sides=6,
    group_pad_bottom=5,
    compact_field_height=21,
    compact_v_pad=1,
    compact_font_size=11,
    date_height=21,
    date_compact_height=21,
    content_margin=5,
    section_spacing=3,
    payment_row_height=23,
    payment_row_compact=21,
    btn_pad_v=3,
    btn_pad_h=9,
)

_DENSITY_NORMAL = UiDensity(
    name="normal",
    field_min_height=23,
    field_v_pad=1,
    field_h_pad=7,
    font_size=11,
    title_font_size=15,
    label_font_size=11,
    form_v_spacing=4,
    form_h_spacing=8,
    group_margin_top=6,
    group_pad_top=6,
    group_pad_sides=6,
    group_pad_bottom=6,
    compact_field_height=23,
    compact_v_pad=1,
    compact_font_size=11,
    date_height=23,
    date_compact_height=23,
    content_margin=6,
    section_spacing=4,
    payment_row_height=25,
    payment_row_compact=23,
    btn_pad_v=4,
    btn_pad_h=10,
)

_DENSITY_COMFORTABLE = UiDensity(
    name="comfortable",
    field_min_height=24,
    field_v_pad=2,
    field_h_pad=8,
    font_size=12,
    title_font_size=16,
    label_font_size=11,
    form_v_spacing=4,
    form_h_spacing=9,
    group_margin_top=7,
    group_pad_top=7,
    group_pad_sides=7,
    group_pad_bottom=7,
    compact_field_height=24,
    compact_v_pad=1,
    compact_font_size=12,
    date_height=24,
    date_compact_height=24,
    content_margin=7,
    section_spacing=4,
    payment_row_height=26,
    payment_row_compact=24,
    btn_pad_v=4,
    btn_pad_h=11,
)

_density: UiDensity = _DENSITY_NORMAL

# Back-compat module constants (updated whenever density refreshes)
FORM_VERTICAL_SPACING = _DENSITY_NORMAL.form_v_spacing
FORM_HORIZONTAL_SPACING = _DENSITY_NORMAL.form_h_spacing
SIDE_PANE_MIN_WIDTH = 280
DEFAULT_SPLITTER_LEFT_RATIO = 0.30

_RESPONSIVE_FILTERS: dict[int, QObject] = {}


def _pick_density(available_height: int) -> UiDensity:
    if available_height > 0 and available_height < 800:
        return _DENSITY_COMPACT
    if available_height >= 1050:
        return _DENSITY_COMFORTABLE
    return _DENSITY_NORMAL


def refresh_ui_density(available_height: int | None = None) -> UiDensity:
    """Recompute density from the primary screen (or an explicit height)."""
    global _density, FORM_VERTICAL_SPACING, FORM_HORIZONTAL_SPACING
    if available_height is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is not None:
            available_height = screen.availableGeometry().height()
        else:
            available_height = 900
    _density = _pick_density(int(available_height))
    FORM_VERTICAL_SPACING = _density.form_v_spacing
    FORM_HORIZONTAL_SPACING = _density.form_h_spacing
    return _density


def get_density() -> UiDensity:
    return _density


def compact_group_style(d: UiDensity | None = None) -> str:
    d = d or _density
    return f"""
QGroupBox {{
    margin-top: {d.group_margin_top}px;
    padding: {d.group_pad_top}px {d.group_pad_sides}px {d.group_pad_bottom}px {d.group_pad_sides}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
"""


# Kept for imports that still reference the name; prefer compact_group_style().
COMPACT_GROUP_STYLE = compact_group_style(_DENSITY_NORMAL)


def configure_form_layout(form: QFormLayout, *, wrap_all: bool = False) -> None:
    """Stack labels above fields when rows are tight so controls do not overlap."""
    d = _density
    form.setVerticalSpacing(d.form_v_spacing)
    form.setHorizontalSpacing(d.form_h_spacing)
    # Keep inputs compact (Patient Service style) instead of stretching full width.
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    policy = (
        QFormLayout.RowWrapPolicy.WrapAllRows
        if wrap_all
        else QFormLayout.RowWrapPolicy.WrapLongRows
    )
    form.setRowWrapPolicy(policy)
    form.setProperty("hmsResponsive", True)


def configure_compact_group_box(box: QGroupBox) -> None:
    if box.property("hmsResponsive"):
        return
    existing = box.styleSheet().strip()
    style = compact_group_style()
    box.setStyleSheet(f"{style}\n{existing}".strip() if existing else style)
    box.setProperty("hmsResponsive", True)


def configure_splitter(
    splitter: QSplitter,
    *,
    left_ratio: float = DEFAULT_SPLITTER_LEFT_RATIO,
) -> None:
    if splitter.property("hmsResponsive"):
        return
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(5)
    splitter.setProperty("hmsLeftRatio", left_ratio)
    splitter.setProperty("hmsResponsive", True)


def size_splitter(splitter: QSplitter, total_width: int | None = None) -> None:
    if splitter.property("hmsSkipAutoSize"):
        return
    if total_width is None or total_width <= 0:
        total_width = splitter.width()
    if total_width <= 0:
        return
    count = splitter.count()
    if count < 2:
        return
    ratio = float(splitter.property("hmsLeftRatio") or DEFAULT_SPLITTER_LEFT_RATIO)
    left_w = max(SIDE_PANE_MIN_WIDTH, int(total_width * ratio))
    remaining = max(280, total_width - left_w)
    if count == 2:
        splitter.setSizes([left_w, remaining])
        return
    sizes = [left_w]
    other = max(200, (total_width - left_w) // (count - 1))
    sizes.extend([other] * (count - 1))
    splitter.setSizes(sizes)


def create_scroll_panel(
    *,
    min_width: int = SIDE_PANE_MIN_WIDTH,
) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    d = _density
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setMinimumWidth(min_width)
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(d.content_margin, d.content_margin, d.content_margin, d.content_margin)
    layout.setSpacing(d.section_spacing)
    scroll.setWidget(host)
    return scroll, host, layout


def paint_page_surface(widget: QWidget, *, color: str | None = None) -> None:
    """Opaque page fill so stacked/transparent widgets cannot ghost through."""
    from app.ui.styles import BG

    fill = color or BG
    widget.setAutoFillBackground(True)
    existing = widget.styleSheet().strip()
    rule = f"background-color: {fill};"
    widget.setStyleSheet(f"{rule}\n{existing}".strip() if existing else rule)


def fit_dialog_size(preferred_w: int, preferred_h: int) -> tuple[int, int]:
    """Clamp a dialog's preferred size to the current screen.

    Prevents modals (Edit Patient, document/search pickers, report preview...)
    from exceeding the visible desktop, which otherwise hides action buttons
    below the fold inside a scroll area.
    """
    app = QApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return preferred_w, preferred_h
    available = screen.availableGeometry()
    width = min(preferred_w, max(700, available.width() - 60))
    height = min(preferred_h, max(480, available.height() - 60))
    return width, height


def wrap_widget_in_scroll(child: QWidget) -> QScrollArea:
    """Put an existing form host inside a scroll area (prevents crush/overlap)."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(child)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return scroll


def configure_stretch_grid(grid: QGridLayout, *, value_column: int = 1) -> None:
    grid.setColumnStretch(value_column, 1)


def mark_stretch_field(field: QTextEdit) -> None:
    field.setProperty("hmsStretchField", True)
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    field.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    field.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class ResponsivePageWidget(QWidget):
    """Optional base class for module pages that need splitter sizing on first show."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _size_page_splitters(self)


class _ResponsiveShowFilter(QObject):
    def __init__(self, root: QWidget):
        super().__init__(root)
        self._root = root

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._root and event.type() == QEvent.Type.Show:
            _size_page_splitters(self._root, only_if_unsized=True)
            _refresh_form_spacing(self._root)
        elif watched is self._root and event.type() == QEvent.Type.Resize:
            _size_page_splitters(self._root, only_if_unsized=False)
        return False


def _size_page_splitters(root: QWidget, *, only_if_unsized: bool = True) -> None:
    width = root.width()
    if width <= 0:
        return
    for splitter in root.findChildren(QSplitter):
        if only_if_unsized and splitter.property("hmsSized"):
            continue
        size_splitter(splitter, width)
        splitter.setProperty("hmsSized", True)


def _refresh_form_spacing(root: QWidget) -> None:
    """Keep form row gaps in sync with the current density band."""
    d = _density
    for form in root.findChildren(QFormLayout):
        parent = form.parentWidget()
        if parent is not None and parent.property("hmsSkipResponsive"):
            continue
        form.setVerticalSpacing(d.form_v_spacing)
        form.setHorizontalSpacing(d.form_h_spacing)


def apply_responsive_layout(root: QWidget) -> None:
    """Walk *root* and apply responsive rules to forms, group boxes, and splitters."""
    if root.property("hmsResponsiveRoot"):
        _refresh_form_spacing(root)
        return
    root.setProperty("hmsResponsiveRoot", True)
    root.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    for form in root.findChildren(QFormLayout):
        parent = form.parentWidget()
        if parent is not None and parent.property("hmsSkipResponsive"):
            continue
        if not form.property("hmsResponsive"):
            configure_form_layout(form)

    for box in root.findChildren(QGroupBox):
        if not box.property("hmsSkipResponsive"):
            configure_compact_group_box(box)

    for splitter in root.findChildren(QSplitter):
        configure_splitter(splitter)

    for field in root.findChildren(QTextEdit):
        if field.property("hmsStretchField"):
            mark_stretch_field(field)

    filt = _ResponsiveShowFilter(root)
    root.installEventFilter(filt)
    _RESPONSIVE_FILTERS[id(root)] = filt
