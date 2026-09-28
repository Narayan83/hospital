"""Shared display helpers for pathology master screens."""


def pathology_item_label(item: dict, *, name_key: str = "name", code_key: str = "code") -> str:
    name = (item.get(name_key) or "").strip()
    code = (item.get(code_key) or "").strip()
    if name and code:
        return f"{name} ({code})"
    return name or code or "—"
