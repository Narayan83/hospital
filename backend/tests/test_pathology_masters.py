"""Tests for pathology master helpers and range logic."""
from decimal import Decimal
from types import SimpleNamespace

from app.repositories.pathology_masters import format_range_text, is_value_abnormal


def _range(
    *,
    text_range: str | None = None,
    min_value: str | None = None,
    max_value: str | None = None,
):
    return SimpleNamespace(
        text_range=text_range,
        min_value=Decimal(min_value) if min_value is not None else None,
        max_value=Decimal(max_value) if max_value is not None else None,
    )


def test_format_range_text_from_text() -> None:
    assert format_range_text(_range(text_range="NON - REACTIVE")) == "NON - REACTIVE"


def test_format_range_text_from_min_max() -> None:
    assert format_range_text(_range(min_value="11.5", max_value="16.0")) == "11.5 - 16.0"


def test_format_range_text_empty() -> None:
    assert format_range_text(None) == "—"
    assert format_range_text(_range()) == "—"


def test_is_value_abnormal_below_min() -> None:
    rng = _range(min_value="11.5", max_value="16.0")
    assert is_value_abnormal(Decimal("10.0"), rng) is True


def test_is_value_abnormal_above_max() -> None:
    rng = _range(min_value="11.5", max_value="16.0")
    assert is_value_abnormal(Decimal("17.0"), rng) is True


def test_is_value_abnormal_in_range() -> None:
    rng = _range(min_value="11.5", max_value="16.0")
    assert is_value_abnormal(Decimal("14.0"), rng) is False


def test_is_value_abnormal_no_range() -> None:
    assert is_value_abnormal(Decimal("99"), None) is False
