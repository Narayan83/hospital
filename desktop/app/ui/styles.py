"""Central theme and stylesheet helpers for HMS desktop UI."""

from pathlib import Path

from app.ui.responsive_layout import get_density, refresh_ui_density

# Light-dark slate palette — soft gray surfaces, high-contrast inputs
PRIMARY = "#1e40af"
PRIMARY_DARK = "#1e3a8a"
PRIMARY_LIGHT = "#3b82f6"
ACCENT = "#0ea5e9"

BG = "#d8dee9"              # page background
SURFACE = "#e8ecf3"         # panels, cards, group boxes
INPUT_BG = "#ffffff"        # inputs — white on gray for clear edges
BORDER = "#94a3b8"          # visible borders (lines, boxes)
BORDER_LIGHT = "#b8c4d4"
BORDER_FOCUS = "#2563eb"
TEXT = "#0f172a"
TEXT_MUTED = "#475569"
TEXT_LIGHT = "#64748b"
SIDEBAR_BG = "#0f172a"

# Dashboard — softer borders than forms (dashboard only)
DASHBOARD_BORDER = "#e2e8f0"
DASHBOARD_BORDER_HOVER = "#cbd5e1"
DASHBOARD_CARD_BG = "#ffffff"
BRAND = PRIMARY
BRAND_DARK = PRIMARY_DARK
BRAND_LIGHT = "#dbeafe"
MUTED = TEXT_MUTED
TRACK = BORDER_LIGHT
SIDEBAR_SURFACE = "#1e293b"
SIDEBAR_HOVER = "#334155"
SIDEBAR_ACTIVE = "#1e40af"

# Typography
TITLE = f"font-size: 20px; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px;"
PAGE_TITLE = f"font-size: 18px; font-weight: 700; color: {TEXT};"
SUBTITLE = f"font-size: 13px; color: {TEXT_MUTED};"
LABEL = f"font-size: 12px; color: {TEXT}; font-weight: 600;"
PANEL = f"background: {SURFACE}; border: 2px solid {BORDER}; border-radius: 10px;"

BTN_PRIMARY = ""
BTN_SECONDARY = ""
BTN_DANGER = ""
BTN_ICON = ""


def _build_button_styles() -> None:
    global BTN_PRIMARY, BTN_SECONDARY, BTN_DANGER, BTN_ICON
    d = get_density()
    BTN_PRIMARY = (
        f"QPushButton {{ background: {PRIMARY}; color: white; border: none; border-radius: 6px;"
        f" padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-weight: 600; font-size: {d.font_size}px; }}"
        f"QPushButton:hover {{ background: #1d4ed8; }}"
        f"QPushButton:pressed {{ background: {PRIMARY_DARK}; }}"
        "QPushButton:disabled { background: #94a3b8; color: #e2e8f0; }"
    )
    BTN_SECONDARY = (
        f"QPushButton {{ background: {INPUT_BG}; color: {TEXT}; border: 2px solid {BORDER};"
        f" border-radius: 6px; padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-size: {d.font_size}px; font-weight: 500; }}"
        f"QPushButton:hover {{ background: #f8fafc; border-color: #64748b; }}"
        f"QPushButton:pressed {{ background: {SURFACE}; }}"
    )
    BTN_DANGER = (
        f"QPushButton {{ background: #fff5f5; color: #991b1b; border: 2px solid #fca5a5;"
        f" border-radius: 6px; padding: {max(4, d.btn_pad_v - 1)}px {d.btn_pad_h}px; font-size: {max(11, d.font_size - 1)}px; }}"
        "QPushButton:hover { background: #fee2e2; border-color: #f87171; }"
    )
    BTN_ICON = (
        f"QPushButton {{ border: 2px solid {BORDER}; border-radius: 8px;"
        f" font-size: {d.font_size + 1}px; background: {INPUT_BG}; padding: 4px; color: {TEXT}; }}"
        f"QPushButton:hover {{ background: #f8fafc; border-color: #64748b; }}"
    )


_build_button_styles()

_CALENDAR_ICON = (Path(__file__).resolve().parent / "assets" / "calendar.svg").as_posix()


def date_edit_stylesheet(*, compact: bool = False) -> str:
    d = get_density()
    height = d.date_compact_height if compact else d.date_height
    drop_width = "22px" if compact else "26px"
    arrow = "12px" if compact else "14px"
    v_pad = "1px" if compact else "2px"
    h_pad = f"{d.field_h_pad}px"
    return f"""
QDateEdit {{
    min-height: {height}px;
    max-height: {height}px;
    padding: {v_pad} {drop_width} {v_pad} {h_pad};
}}
QDateEdit QLineEdit {{
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
    min-height: 0px;
    max-height: 16777215px;
}}
QDateEdit::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: center right;
    width: {drop_width};
    border-left: 1px solid {BORDER};
    background: {INPUT_BG};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}
QDateEdit::down-arrow {{
    width: {arrow};
    height: {arrow};
    image: url("{_CALENDAR_ICON}");
}}
"""


def form_field_style() -> str:
    """White input chrome — compact height like Patient Service Master fields."""
    d = get_density()
    h = d.field_min_height
    return f"""
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: {d.field_v_pad}px {d.field_h_pad}px;
    min-height: {h}px;
    max-height: {h}px;
    font-size: {d.font_size}px;
    color: {TEXT};
    selection-background-color: #bfdbfe;
    selection-color: {TEXT};
}}
QDateEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-height: {d.date_height}px;
    max-height: {d.date_height}px;
    font-size: {d.font_size}px;
    color: {TEXT};
    selection-background-color: #bfdbfe;
    selection-color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus {{
    border: 2px solid {BORDER_FOCUS};
    background-color: {INPUT_BG};
    background: {INPUT_BG};
}}
QLineEdit:read-only, QLineEdit[readOnly="true"] {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    color: {TEXT};
    border: 2px solid {BORDER};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled {{
    background-color: #f8fafc;
    background: #f8fafc;
    color: {TEXT_MUTED};
    border: 2px solid {BORDER_LIGHT};
}}
QComboBox::drop-down {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border-left: 1px solid {BORDER};
}}
{date_edit_stylesheet()}
QComboBox QAbstractItemView {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    color: {TEXT};
    selection-background-color: #dbeafe;
}}
QTextEdit, QPlainTextEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    font-size: {d.font_size}px;
    color: {TEXT};
}}
"""


def compact_field_style() -> str:
    """Dense left-pane / registration fields — still tall enough for the font."""
    d = get_density()
    h = d.compact_field_height
    return f"""
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    border-radius: 5px;
    padding: {d.compact_v_pad}px 6px;
    min-height: {h}px;
    max-height: {h}px;
    font-size: {d.compact_font_size}px;
    color: {TEXT};
}}
QComboBox::drop-down {{
    width: 18px;
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border-left: 1px solid {BORDER};
}}
"""


def left_pane_field_height() -> int:
    return get_density().compact_field_height


def build_app_stylesheet() -> str:
    """Global QSS sized for the current screen density."""
    d = get_density()
    return f"""
QWidget {{
    font-family: "Segoe UI", sans-serif;
    color: {TEXT};
    background: transparent;
}}

QMainWindow {{
    background: {BG};
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: {d.field_v_pad}px {d.field_h_pad}px;
    min-height: {d.field_min_height}px;
    max-height: {d.field_min_height}px;
    font-size: {d.font_size}px;
    color: {TEXT};
    selection-background-color: #bfdbfe;
    selection-color: {TEXT};
}}
QDateEdit {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-height: {d.date_height}px;
    max-height: {d.date_height}px;
    font-size: {d.font_size}px;
    color: {TEXT};
    selection-background-color: #bfdbfe;
    selection-color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus {{
    border: 2px solid {BORDER_FOCUS};
    background: {INPUT_BG};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QDateEdit:disabled {{
    background: #f1f5f9;
    color: {TEXT_MUTED};
    border: 2px solid {BORDER_LIGHT};
}}
QLineEdit:read-only {{
    background-color: {INPUT_BG};
    background: {INPUT_BG};
    color: {TEXT};
    border: 2px solid {BORDER};
}}

QComboBox::drop-down {{
    border-left: 1px solid {BORDER};
    width: 26px;
    background: {INPUT_BG};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}
{date_edit_stylesheet()}
QComboBox QAbstractItemView {{
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    selection-background-color: #dbeafe;
    selection-color: {TEXT};
    padding: 4px;
    color: {TEXT};
}}

QTextEdit, QPlainTextEdit {{
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    font-size: {d.font_size}px;
    color: {TEXT};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {BORDER_FOCUS};
}}

QGroupBox {{
    background: {SURFACE};
    border: 2px solid {BORDER};
    border-radius: 10px;
    margin-top: {d.group_margin_top}px;
    padding: {d.group_pad_top}px {d.group_pad_sides}px {d.group_pad_bottom}px {d.group_pad_sides}px;
    font-weight: 600;
    font-size: {d.font_size}px;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    color: {PRIMARY};
    font-weight: 700;
}}

QTableWidget {{
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER_LIGHT};
    font-size: {d.font_size}px;
    alternate-background-color: #f1f5f9;
    color: {TEXT};
}}
QTableWidget::item {{
    padding: {max(2, d.field_v_pad)}px {d.field_h_pad}px;
    border: none;
}}
QTableWidget::item:selected {{
    background: #dbeafe;
    color: {TEXT};
}}
QHeaderView::section {{
    background: #e2e8f0;
    color: {TEXT_MUTED};
    font-weight: 700;
    font-size: {max(10, d.font_size - 1)}px;
    letter-spacing: 0.3px;
    padding: {max(3, d.field_v_pad + 2)}px {d.field_h_pad}px;
    border: none;
    border-bottom: 2px solid {BORDER};
    border-right: 1px solid {BORDER_LIGHT};
}}

QTabWidget::pane {{
    background: {SURFACE};
    border: 2px solid {BORDER};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: #e2e8f0;
    color: {TEXT_MUTED};
    border: 2px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {SURFACE};
    color: {PRIMARY};
    border-bottom: 2px solid {SURFACE};
}}
QTabBar::tab:hover {{
    background: #f1f5f9;
    color: {TEXT};
}}

QCheckBox, QRadioButton {{
    color: {TEXT};
    spacing: 8px;
    font-size: {d.font_size}px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {BORDER};
    background: {INPUT_BG};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QRadioButton::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QSplitter::handle {{
    background: {BORDER};
    width: 3px;
}}

QScrollBar:vertical {{
    background: {SURFACE};
    width: 12px;
    margin: 2px;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #64748b;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {SURFACE};
    height: 12px;
    margin: 2px;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QStatusBar {{
    background: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 2px solid {BORDER};
    font-size: 12px;
    padding: 2px 8px;
}}

QToolTip {{
    background: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    padding: 6px 8px;
    border-radius: 4px;
}}

QMessageBox {{
    background: {SURFACE};
}}

QDialog {{
    background: {BG};
}}

QMenu {{
    background: {INPUT_BG};
    border: 2px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: #dbeafe;
    color: {TEXT};
}}
"""


def rebuild_style_tokens() -> None:
    """Refresh module-level style strings after density is computed."""
    global DATE_EDIT_FIELD_RULES, FORM_FIELD_STYLE, INPUT_STYLE, APP_STYLESHEET
    global TITLE, PAGE_TITLE, SUBTITLE, LABEL, HEADER_BTN_STYLE
    d = get_density()
    _build_button_styles()
    TITLE = (
        f"font-size: {d.title_font_size + 2}px; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px;"
    )
    PAGE_TITLE = f"font-size: {d.title_font_size}px; font-weight: 700; color: {TEXT};"
    SUBTITLE = f"font-size: {d.font_size}px; color: {TEXT_MUTED};"
    LABEL = f"font-size: {d.label_font_size}px; color: {TEXT}; font-weight: 600;"
    HEADER_BTN_STYLE = (
        f"QPushButton {{ font-size: {max(11, d.font_size - 1)}px; padding: {max(3, d.btn_pad_v - 2)}px "
        f"{max(8, d.btn_pad_h - 4)}px; border: 2px solid {BORDER}; "
        f"border-radius: 4px; background: {INPUT_BG}; color: {TEXT}; }}"
        f"QPushButton:hover {{ background: {SURFACE}; border-color: #64748b; }}"
    )
    DATE_EDIT_FIELD_RULES = date_edit_stylesheet()
    FORM_FIELD_STYLE = form_field_style()
    INPUT_STYLE = (
        f"background-color: {INPUT_BG}; background: {INPUT_BG}; border: 2px solid {BORDER};"
        f" border-radius: 6px; padding: {d.field_v_pad}px {d.field_h_pad}px; color: {TEXT};"
    )
    APP_STYLESHEET = build_app_stylesheet()


# Populated by rebuild_style_tokens() — safe defaults until apply_global_theme runs.
DATE_EDIT_FIELD_RULES = date_edit_stylesheet()
FORM_FIELD_STYLE = form_field_style()
INPUT_STYLE = (
    f"background-color: {INPUT_BG}; background: {INPUT_BG}; border: 2px solid {BORDER};"
    f" border-radius: 6px; padding: 5px 10px; color: {TEXT};"
)
APP_STYLESHEET = build_app_stylesheet()

TABLE_COMPACT_STYLE = f"""
QTableWidget {{
    font-size: 11px;
    gridline-color: {BORDER_LIGHT};
}}
QTableWidget::item {{
    padding: 0px 3px;
}}
QHeaderView::section {{
    font-size: 11px;
    padding: 1px 4px;
    background: #e2e8f0;
    border-bottom: 1px solid {BORDER};
}}
"""

HEADER_BTN_STYLE = (
    f"QPushButton {{ font-size: 11px; padding: 4px 10px; border: 2px solid {BORDER}; "
    f"border-radius: 4px; background: {INPUT_BG}; color: {TEXT}; }}"
    f"QPushButton:hover {{ background: {SURFACE}; border-color: #64748b; }}"
)

PANEL_CARD = (
    f"QFrame {{ background: {SURFACE}; border: 2px solid {BORDER}; border-radius: 8px; }}"
)


def apply_global_theme(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    refresh_ui_density()
    rebuild_style_tokens()

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(INPUT_BG))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_LIGHT))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)


def _apply_input_palette(
    widget,
    *,
    text: str = TEXT,
    base: str = INPUT_BG,
    placeholder: str = TEXT_LIGHT,
) -> None:
    from PySide6.QtGui import QColor, QPalette

    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(placeholder))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)


def apply_form_field_style(root) -> None:
    """Paint every text input under *root* with a white background."""
    from app.ui.responsive_layout import apply_responsive_layout
    from app.ui.components.date_edit import configure_date_edit, finalize_date_edit
    from PySide6.QtWidgets import (
        QComboBox,
        QDateEdit,
        QDoubleSpinBox,
        QFormLayout,
        QLabel,
        QLayout,
        QLineEdit,
        QPlainTextEdit,
        QSpinBox,
        QTextEdit,
        QTimeEdit,
        QWidget,
    )

    from PySide6.QtWidgets import QSizePolicy

    field_css = form_field_style()
    d = get_density()
    _DEFAULT_MAX_W = 16777215
    # Compact cap for standalone master-form fields only — not full-width page forms.
    _FORM_MAX_WIDTH = 360
    # Patient / customer names are long — keep these fields wide by default.
    _NAME_MIN_WIDTH = 480
    _NAME_LABEL_HINTS = {
        "name",
        "patient name",
        "patientname",
        "customer name",
        "customer / patient name",
        "full name",
    }
    _NAME_OBJECT_HINTS = (
        "patient_name",
        "patientname",
        "customer_name",
        "fullname_name",
        "fullname_name_input",
        "patient_name_input",
    )

    def _skip_line_edit(widget: QLineEdit) -> bool:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, (QDateEdit, QTimeEdit)):
                return True
            parent = parent.parentWidget()
        return False

    def _prop_true(widget, name: str) -> bool:
        val = widget.property(name)
        return val in (True, 1, "true", "True", "1")

    def _field_has_explicit_width(widget) -> bool:
        """Respect deliberately narrow/fixed controls (Patient Id, Age, Sex…)."""
        if _prop_true(widget, "hmsAllowWide") or _prop_true(widget, "hmsPatientName"):
            return False
        max_w = widget.maximumWidth()
        if max_w < _DEFAULT_MAX_W:
            return True
        min_w = widget.minimumWidth()
        return min_w == max_w and max_w < _DEFAULT_MAX_W

    def _widget_under(container: QWidget | None, widget: QWidget) -> bool:
        if container is None:
            return False
        current: QWidget | None = widget
        while current is not None:
            if current is container:
                return True
            current = current.parentWidget()
        return False

    def _form_row_label_text(widget: QWidget) -> str:
        parent = widget.parentWidget()
        while parent is not None:
            layout = parent.layout()
            if isinstance(layout, QFormLayout):
                for row in range(layout.rowCount()):
                    field_item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    field_widget = field_item.widget() if field_item else None
                    if field_widget is widget or _widget_under(field_widget, widget):
                        label_item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                        label_widget = label_item.widget() if label_item else None
                        if isinstance(label_widget, QLabel):
                            return (label_widget.text() or "").strip()
                        # Label may be plain text via addRow(str, widget)
                        if label_item is not None and label_item.layout() is None:
                            # Some Qt builds expose label as QLayoutItem with no widget;
                            # fall through to sibling scan.
                            pass
                    # Also handle addRow(label, QHBoxLayout) where field is a layout.
                    if field_item is not None and field_item.layout() is not None:
                        if _layout_contains_widget(field_item.layout(), widget):
                            label_item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                            label_widget = label_item.widget() if label_item else None
                            if isinstance(label_widget, QLabel):
                                return (label_widget.text() or "").strip()
            parent = parent.parentWidget()
        return ""

    def _layout_contains_widget(layout: QLayout | None, widget: QWidget) -> bool:
        if layout is None:
            return False
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            child = item.widget()
            if child is widget or _widget_under(child, widget):
                return True
            if item.layout() is not None and _layout_contains_widget(item.layout(), widget):
                return True
        return False

    def _is_patient_name_field(widget) -> bool:
        if not isinstance(widget, QLineEdit):
            return False
        if _prop_true(widget, "hmsPatientName"):
            return True
        obj = (widget.objectName() or "").casefold().replace("-", "_")
        if any(hint in obj for hint in _NAME_OBJECT_HINTS):
            return True
        placeholder = ""
        if hasattr(widget, "placeholderText"):
            placeholder = (widget.placeholderText() or "").casefold().strip()
        if "patient name" in placeholder or placeholder == "name":
            return True
        if "customer" in placeholder and "name" in placeholder:
            return True
        label = _form_row_label_text(widget).casefold().replace("&", "").strip()
        label = " ".join(label.split())
        if label in {"user name", "username", "ledger name", "service name", "doctor name"}:
            return False
        if label in _NAME_LABEL_HINTS or "patient" in label and "name" in label:
            return True
        if "customer" in label and "name" in label:
            return True
        return False

    def _in_expanding_form(widget) -> bool:
        if _prop_true(widget, "hmsAllowWide") or _prop_true(widget, "hmsPatientName"):
            return True
        if _is_patient_name_field(widget):
            return True
        parent = widget.parentWidget()
        while parent is not None:
            if _prop_true(parent, "hmsExpandFormFields"):
                return True
            # Settings / full-page profile forms
            if parent.__class__.__name__ in {"HospitalProfileWidget", "DatabaseMigrationWidget"}:
                return True
            layout = parent.layout()
            if isinstance(layout, QFormLayout) and (
                layout.fieldGrowthPolicy()
                in (
                    QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow,
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow,
                )
            ):
                return True
            parent = parent.parentWidget()
        return False

    def _should_expand_horizontally(widget) -> bool:
        if _prop_true(widget, "hmsSkipFormStyle"):
            return False
        if _is_patient_name_field(widget):
            return True
        if _field_has_explicit_width(widget):
            return False
        return _in_expanding_form(widget)

    for cls in (
        QLineEdit,
        QComboBox,
        QDateEdit,
        QTimeEdit,
        QSpinBox,
        QDoubleSpinBox,
        QTextEdit,
        QPlainTextEdit,
    ):
        for widget in root.findChildren(cls):
            if widget.property("hmsSkipFormStyle"):
                continue
            if cls is QLineEdit and _skip_line_edit(widget):
                continue
            _apply_input_palette(widget)
            if not isinstance(widget, (QTextEdit, QPlainTextEdit)):
                widget.setMinimumHeight(d.field_min_height)
                widget.setMaximumHeight(d.field_min_height)
                if _should_expand_horizontally(widget):
                    widget.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                    )
                    widget.setMaximumWidth(_DEFAULT_MAX_W)
                    if _is_patient_name_field(widget) and widget.minimumWidth() < _NAME_MIN_WIDTH:
                        widget.setMinimumWidth(_NAME_MIN_WIDTH)
                else:
                    if widget.maximumWidth() >= _DEFAULT_MAX_W:
                        widget.setMaximumWidth(_FORM_MAX_WIDTH)
                    widget.setSizePolicy(
                        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                    )
            extra = widget.styleSheet().strip()
            if isinstance(widget, QDateEdit):
                configure_date_edit(widget)
                compact = bool(widget.property("hmsCompactDate"))
                date_css = date_edit_stylesheet(compact=compact)
                base = f"{field_css}\n{date_css}"
            else:
                base = field_css
            widget.setStyleSheet(f"{base}\n{extra}" if extra else base)
            if isinstance(widget, QDateEdit):
                finalize_date_edit(widget)

    apply_responsive_layout(root)
    from app.ui.table_utils import apply_resizable_columns

    apply_resizable_columns(root)


def mark_patient_name_field(field) -> None:
    """Mark a line edit as a long patient/customer name field (global form styling)."""
    from PySide6.QtWidgets import QSizePolicy

    if field is None:
        return
    if not (field.objectName() or "").strip():
        field.setObjectName("patient_name")
    field.setProperty("hmsPatientName", True)
    field.setProperty("hmsAllowWide", True)
    field.setMinimumWidth(480)
    field.setMaximumWidth(16777215)
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

