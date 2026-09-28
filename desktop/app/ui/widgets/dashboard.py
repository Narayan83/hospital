from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.api_client.client import ApiClient
from app.session import get_session, hospital_display_name

PAGE_BG = "#eef1f4"
CARD_BG = "#ffffff"
TEXT = "#1a222a"
MUTED = "#6b7280"
BORDER = "#d8dee6"
GREEN = "#22c55e"
GREEN_DARK = "#16a34a"
GREEN_SOFT = "#e8f9ef"
RED = "#ef4444"
RED_SOFT = "#fde8e8"
TEAL = "#0d9488"
TEAL_DARK = "#0f766e"
TEAL_SOFT = "#e6f7f5"
AMBER = "#f59e0b"
AMBER_SOFT = "#fff7e6"
BLUE = "#3b82f6"
BLUE_SOFT = "#eff6ff"
VIOLET = "#8b5cf6"
VIOLET_SOFT = "#f3e8ff"
ROSE = "#f43f5e"
ROSE_SOFT = "#ffe4e6"
WEB_FONT = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

QUICK_ACTIONS = (
    ("opd_bill", "OPD", "Outpatient billing"),
    ("ipd_bill", "IPD", "Inpatient billing"),
    ("pathology_bill", "Pathology", "Pathology billing"),
    ("doctor_wise_collection_report", "Doctor Collection", "Doctor wise collection report"),
)

BOARD_TILES = (
    ("patients", "Patients", "Registered", "green"),
    ("doctors", "Doctors", "Active staff", "white"),
    ("wards", "Wards", "Capacity", "white"),
    ("services", "Services", "Billable", "teal"),
    ("departments", "Departments", "Configured", "white"),
    ("users", "Staff", "System users", "amber"),
)

# Lower colorful statistics: (key, label, hint, color, soft)
COLOR_STATS = (
    ("billing_types", "Billing Types", "Configured bill types", AMBER, AMBER_SOFT),
    ("payment_modes", "Payment Modes", "Accepted modes", BLUE, BLUE_SOFT),
    ("hospital_sections", "Hospital Sections", "Sections / units", VIOLET, VIOLET_SOFT),
    ("departments", "Departments", "Clinical departments", TEAL, TEAL_SOFT),
    ("wards", "Wards", "Bed / ward capacity", GREEN, GREEN_SOFT),
    ("services", "Services", "Patient services", ROSE, ROSE_SOFT),
    ("doctors", "Doctors", "Active doctors", BLUE, BLUE_SOFT),
    ("users", "Staff Users", "System logins", AMBER, AMBER_SOFT),
)


def _soft_shadow(widget: QWidget, *, blur: int = 16, y: int = 3, alpha: int = 24) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(26, 34, 42, alpha))
    widget.setGraphicsEffect(effect)


def _lbl(text: str, style: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"background: transparent; border: none; font-family: {WEB_FONT}; {style}"
    )
    label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return label


def _variant_colors(variant: str) -> tuple[str, str, str, str]:
    if variant == "green":
        return GREEN, GREEN_DARK, "#ffffff", "#ffffff"
    if variant == "red":
        return RED, "#dc2626", "#ffffff", "#ffffff"
    if variant == "teal":
        return TEAL, TEAL_DARK, "#ffffff", "#ffffff"
    if variant == "amber":
        return AMBER, "#d97706", "#ffffff", "#ffffff"
    if variant == "blue":
        return BLUE, "#2563eb", "#ffffff", "#ffffff"
    return CARD_BG, BORDER, TEXT, TEXT


class _PageHeader(QFrame):
    def __init__(self, hospital_name: str, subtitle: str):
        super().__init__()
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(4)
        self._title = _lbl(hospital_name, f"font-size: 24px; font-weight: 700; color: {TEXT};")
        left.addWidget(self._title)
        self._subtitle = _lbl(subtitle, f"font-size: 13px; font-weight: 500; color: {MUTED};")
        left.addWidget(self._subtitle)
        layout.addLayout(left, stretch=1)

        legend = QHBoxLayout()
        legend.setSpacing(8)
        for text, bg, fg, border in (
            ("Active", GREEN, "#ffffff", GREEN),
            ("Masters", CARD_BG, TEXT, BORDER),
            ("Alert", RED, "#ffffff", RED),
        ):
            pill = QLabel(f"  {text}  ")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setMinimumHeight(28)
            pill.setStyleSheet(
                f"""
                QLabel {{
                    background: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 8px;
                    padding: 4px 12px;
                    font-family: {WEB_FONT};
                    font-size: 12px;
                    font-weight: 600;
                }}
                """
            )
            legend.addWidget(pill)
        layout.addLayout(legend)

    def set_brand(self, hospital_name: str) -> None:
        self._title.setText(hospital_name or "Hospital")


class _ShortcutChip(QPushButton):
    def __init__(self, module_id: str, title: str, desc: str = "", *, primary: bool = False):
        super().__init__(title)
        self.module_id = module_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(desc or title)
        self.setMinimumHeight(36)
        self.setFlat(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

        if primary:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {GREEN};
                    color: #ffffff;
                    border: 1px solid {GREEN_DARK};
                    border-radius: 8px;
                    padding: 7px 16px;
                    font-family: {WEB_FONT};
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background-color: {GREEN_DARK}; }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {CARD_BG};
                    color: {TEXT};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    padding: 7px 14px;
                    font-family: {WEB_FONT};
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #f8fafc;
                    border-color: #b6c0cc;
                }}
                """
            )


class _ShortcutsBar(QFrame):
    configure_requested = Signal()
    module_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._chips = QHBoxLayout()
        self._chips.setContentsMargins(0, 0, 0, 0)
        self._chips.setSpacing(8)
        layout.addLayout(self._chips, stretch=1)

        self._configure = QPushButton("+  Shortcuts")
        self._configure.setCursor(Qt.CursorShape.PointingHandCursor)
        self._configure.setFlat(True)
        self._configure.setMinimumHeight(36)
        self._configure.setToolTip("Configure dashboard shortcuts")
        self._configure.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._configure.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {TEAL};
                color: #ffffff;
                border: 1px solid {TEAL_DARK};
                border-radius: 8px;
                padding: 7px 14px;
                font-family: {WEB_FONT};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {TEAL_DARK}; }}
            """
        )
        self._configure.clicked.connect(self.configure_requested.emit)
        layout.addWidget(self._configure)

    def set_configure_visible(self, visible: bool) -> None:
        self._configure.setVisible(visible)

    def set_actions(self, actions: list[tuple]) -> None:
        while self._chips.count():
            item = self._chips.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not actions:
            empty = _lbl("No shortcuts yet", f"font-size: 12px; color: {MUTED};")
            self._chips.addWidget(empty)
            self._chips.addStretch(1)
            return

        for index, action in enumerate(actions):
            module_id, title, desc = action[0], action[1], action[2]
            chip = _ShortcutChip(module_id, title, desc, primary=(index == 0))
            chip.clicked.connect(lambda _c=False, m=module_id: self.module_requested.emit(m))
            self._chips.addWidget(chip)
        self._chips.addStretch(1)


class _BoardTile(QFrame):
    def __init__(self, title: str, subtitle: str, variant: str = "white"):
        super().__init__()
        bg, border, title_c, value_c = _variant_colors(variant)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(100)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            """
        )
        _soft_shadow(self, blur=12, y=2, alpha=18)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._value = _lbl("0", f"font-size: 24px; font-weight: 800; color: {value_c};")
        layout.addWidget(self._value)
        layout.addStretch(1)
        self._title = _lbl(title, f"font-size: 13px; font-weight: 700; color: {title_c};")
        layout.addWidget(self._title)
        muted = MUTED if variant == "white" else "rgba(255,255,255,0.88)"
        self._subtitle = _lbl(subtitle, f"font-size: 11px; font-weight: 500; color: {muted};")
        layout.addWidget(self._subtitle)

    def set_value(self, value: str | int) -> None:
        text = str(value)
        if text.isdigit():
            text = f"{int(text):,}"
        self._value.setText(text)


class _ColorStatCard(QFrame):
    """Colorful statistics card for the lower section."""

    def __init__(self, label: str, hint: str, color: str, soft: str):
        super().__init__()
        self._color = color
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(112)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {soft};
                border: 1px solid {color}33;
                border-left: 5px solid {color};
                border-radius: 12px;
            }}
            """
        )
        _soft_shadow(self, blur=14, y=2, alpha=16)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(_lbl(label, f"font-size: 13px; font-weight: 700; color: {TEXT};"))
        top.addStretch(1)
        self._value = _lbl("0", f"font-size: 28px; font-weight: 800; color: {color};")
        top.addWidget(self._value)
        layout.addLayout(top)

        layout.addWidget(_lbl(hint, f"font-size: 11px; color: {MUTED};"))

        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.75);
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 4px;
            }}
            """
        )
        layout.addWidget(self._bar)
        layout.addStretch(1)

    def set_data(self, value: int, maximum: int) -> None:
        self._value.setText(f"{value:,}")
        pct = int((value / maximum) * 100) if maximum > 0 else 0
        self._bar.setValue(min(100, max(0, pct)))


class DashboardWidget(QWidget):
    module_requested = Signal(str)

    def __init__(self, api: ApiClient | None = None):
        super().__init__()
        self._api = api
        self._board: dict[str, _BoardTile] = {}
        self._color_stat_items: list[tuple[str, _ColorStatCard]] = []
        self._hero: _PageHeader | None = None
        self._shortcuts_bar: _ShortcutsBar | None = None
        self.setObjectName("dashboardRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            #dashboardRoot {{
                background: {PAGE_BG};
                font-family: {WEB_FONT};
            }}
            """
        )
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 14)
        root.setSpacing(12)

        self._hero = _PageHeader(
            hospital_display_name() or "Hospital",
            "Hospital overview · click a shortcut to open · live counts below",
        )
        root.addWidget(self._hero)

        self._shortcuts_bar = _ShortcutsBar()
        self._shortcuts_bar.module_requested.connect(self.module_requested.emit)
        self._shortcuts_bar.configure_requested.connect(
            lambda: self.module_requested.emit("dashboard_shortcut_setup")
        )
        root.addWidget(self._shortcuts_bar)

        # Top metric boxes — full page width, fitted at top
        board_wrap = QWidget()
        board_wrap.setStyleSheet("background: transparent;")
        board_grid = QGridLayout(board_wrap)
        board_grid.setContentsMargins(0, 0, 0, 0)
        board_grid.setHorizontalSpacing(10)
        board_grid.setVerticalSpacing(10)
        for i, (key, title, subtitle, variant) in enumerate(BOARD_TILES):
            tile = _BoardTile(title, subtitle, variant)
            self._board[key] = tile
            board_grid.addWidget(tile, i // 3, i % 3)
        for col in range(3):
            board_grid.setColumnStretch(col, 1)
        root.addWidget(board_wrap)

        # Lower colorful statistics (fills remaining space)
        stats_panel = QFrame()
        stats_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        stats_panel.setStyleSheet(
            f"""
            QFrame {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            """
        )
        _soft_shadow(stats_panel, blur=14, y=2, alpha=16)
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(16, 14, 16, 14)
        stats_layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(
            _lbl("Statistics", f"font-size: 15px; font-weight: 700; color: {TEXT};")
        )
        header.addStretch(1)
        header.addWidget(
            _lbl("Master data snapshot", f"font-size: 12px; color: {MUTED};")
        )
        stats_layout.addLayout(header)

        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(12)
        color_grid.setVerticalSpacing(12)
        self._color_stat_items = []
        for i, (key, label, hint, color, soft) in enumerate(COLOR_STATS):
            card = _ColorStatCard(label, hint, color, soft)
            self._color_stat_items.append((key, card))
            color_grid.addWidget(card, i // 4, i % 4)
        for col in range(4):
            color_grid.setColumnStretch(col, 1)
        for row in range(2):
            color_grid.setRowStretch(row, 1)
        stats_layout.addLayout(color_grid, stretch=1)

        root.addWidget(stats_panel, stretch=1)
        self._render_shortcuts(list(QUICK_ACTIONS))

    def _render_shortcuts(self, actions: list[tuple]) -> None:
        if not self._shortcuts_bar:
            return
        allowed = get_session().allowed_menu_codes()
        can_configure = (
            not allowed
            or "dashboard_shortcut_setup" in allowed
            or get_session().is_super_admin()
        )
        self._shortcuts_bar.set_configure_visible(can_configure)
        self._shortcuts_bar.set_actions(actions)

    def _default_shortcut_actions(self) -> list[tuple]:
        allowed = get_session().allowed_menu_codes()
        actions = []
        for module_id, title, desc in QUICK_ACTIONS:
            if not allowed or module_id in allowed:
                actions.append((module_id, title, desc))
        return actions

    def _shortcut_actions_from_api(self, rows: list[dict]) -> list[tuple]:
        allowed = get_session().allowed_menu_codes()
        actions = []
        for row in rows:
            module_id = (row.get("module_code") or "").strip()
            if not module_id:
                continue
            if allowed and module_id not in allowed:
                continue
            title = (row.get("button_label") or module_id).strip()
            desc = (row.get("description") or "").strip() or title
            actions.append((module_id, title, desc))
        return actions

    def apply_hospital_branding(self) -> None:
        if self._hero:
            self._hero.set_brand(hospital_display_name() or "Hospital")

    def refresh(self) -> None:
        self.apply_hospital_branding()
        if self._api:
            QTimer.singleShot(0, self._load_stats)
            QTimer.singleShot(0, self._load_shortcuts)
        else:
            self._apply_cache_fallback()
            self._render_shortcuts(self._default_shortcut_actions())

    def _load_shortcuts(self) -> None:
        if not self._api:
            self._render_shortcuts(self._default_shortcut_actions())
            return
        try:
            rows = self._api.list_dashboard_shortcuts(active_only=True)
        except Exception:
            self._render_shortcuts(self._default_shortcut_actions())
            return
        actions = self._shortcut_actions_from_api(rows or [])
        self._render_shortcuts(actions or self._default_shortcut_actions())

    def _set_values(self, values: dict[str, int | str]) -> None:
        for key, tile in self._board.items():
            tile.set_value(values.get(key, 0))

        numeric = {}
        for key, _card in self._color_stat_items:
            raw = values.get(key, 0)
            try:
                numeric[key] = int(raw) if str(raw).replace(",", "").isdigit() else 0
            except (TypeError, ValueError):
                numeric[key] = 0
        maximum = max(numeric.values()) if any(numeric.values()) else 1
        for key, card in self._color_stat_items:
            card.set_data(numeric.get(key, 0), maximum)

    def _apply_cache_fallback(self) -> None:
        cache = get_session().cache
        self._set_values(
            {
                "patients": "—",
                "doctors": len(cache.doctors),
                "departments": len(cache.departments),
                "wards": len(cache.wards),
                "services": len(cache.patient_services),
                "users": len(cache.users),
                "billing_types": len(cache.billing_types),
                "payment_modes": len(cache.payment_modes),
                "hospital_sections": len(cache.hospital_sections),
            }
        )

    def _load_stats(self) -> None:
        if not self._api:
            return
        try:
            stats = self._api.get_dashboard_stats()
        except Exception:
            self._apply_cache_fallback()
            return
        self._set_values(
            {
                "patients": stats.get("patients", 0),
                "doctors": stats.get("doctors", 0),
                "departments": stats.get("departments", 0),
                "wards": stats.get("wards", 0),
                "services": stats.get("services", 0),
                "users": stats.get("staff", 0),
                "billing_types": stats.get("billing_types", 0),
                "payment_modes": stats.get("payment_modes", 0),
                "hospital_sections": stats.get("hospital_sections", 0),
            }
        )
