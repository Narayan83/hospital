"""Navigation helpers — shortcuts open modules as modals; menu uses full-page navigation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from app.api_client.client import ApiClient


def make_shortcut_navigator(source: QWidget) -> Callable[[str], None]:
    """Return an ``on_navigate`` callback that opens targets as modal dialogs."""
    api = getattr(source, "api", None)
    on_navigate = getattr(source, "_on_navigate", None)
    return lambda module_id: navigate_shortcut(
        module_id,
        parent=source,
        api=api,
        on_navigate=on_navigate,
    )


def navigate_shortcut(
    module_id: str,
    *,
    parent: QWidget,
    api: ApiClient | None = None,
    on_navigate: Callable[[str], None] | None = None,
    before_show: Callable | None = None,
    title: str | None = None,
) -> None:
    """Open *module_id* in a modal when invoked from a screen shortcut."""
    from app.ui.module_modal import open_module_modal

    open_module_modal(
        module_id,
        parent=parent,
        api=api,
        on_navigate=on_navigate,
        before_show=before_show,
        title=title,
    )
