"""Tests for lab-test helpers: auto code slug + age unit conversion."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pathology_ranges import age_to_days, days_to_age  # noqa: E402


def test_age_to_days_units() -> None:
    assert age_to_days(1, "years") == 365
    assert age_to_days(12, "months") == 360
    assert age_to_days(4, "weeks") == 28
    assert age_to_days(10, "days") == 10
    assert age_to_days(5, "unknown") == 5 * 365


def test_days_to_age_roundtrip() -> None:
    assert days_to_age(365) == (1, "years")
    assert days_to_age(28) == (4, "weeks")
    assert days_to_age(60) == (2, "months")
    assert days_to_age(3) == (3, "days")


def test_slug_auto_code() -> None:
    from app.services.lab_test import _slug

    assert _slug("Hemoglobin") == "HEMOGLOBIN"
    assert _slug("A Very Long Lab Test Name That Exceeds Limits") == "AVERYLONGLABTESTNAMETHAT"
    assert len(_slug("A Very Long Lab Test Name That Exceeds Limits")) == 24
    assert _slug("   ") == "TEST"
    assert _slug("CBC / Panel #1") == "CBCPANEL1"
