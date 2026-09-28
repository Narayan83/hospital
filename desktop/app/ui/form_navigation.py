from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox, QDateEdit, QLineEdit, QWidget


class _EnterKeyNavigationFilter(QObject):
    def __init__(self, skip: set[QWidget]):
        super().__init__()
        self._skip = skip

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        if not isinstance(obj, QWidget) or obj in self._skip:
            return False
        if isinstance(obj, QLineEdit) and obj.isReadOnly():
            return False
        if not obj.isEnabled():
            return False
        if isinstance(obj, QComboBox):
            view = obj.view()
            if view is not None and view.isVisible():
                return False
        if isinstance(obj, QDateEdit) and obj.calendarWidget().isVisible():
            return False

        parent = obj.parentWidget()
        while parent is not None:
            if parent.focusNextPrevChild(True):
                return True
            parent = parent.parentWidget()
        return False


def enable_enter_key_navigation(
    container: QWidget,
    *,
    skip: set[QWidget] | None = None,
) -> _EnterKeyNavigationFilter:
    """Move focus to the next field when Enter is pressed (same order as Tab)."""
    skip = skip or set()
    navigation_filter = _EnterKeyNavigationFilter(skip)

    for widget_type in (QLineEdit, QComboBox, QDateEdit):
        for widget in container.findChildren(widget_type):
            if widget in skip:
                continue
            if isinstance(widget, QLineEdit) and widget.isReadOnly():
                continue
            widget.installEventFilter(navigation_filter)

    return navigation_filter
