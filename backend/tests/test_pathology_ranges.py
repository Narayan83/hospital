"""Tests for legacy pathology age-group range parsing."""
from decimal import Decimal

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pathology_ranges import parse_age_group_range, parse_range_entries_from_row


def test_parse_tsh_age_group_adult() -> None:
    entry = parse_age_group_range("21 - 80 Years                                             0.301-4.2")
    assert entry is not None
    assert entry["age_from_days"] == 21 * 365
    assert entry["age_to_days"] == 80 * 365
    assert entry["min_value"] == Decimal("0.301")
    assert entry["max_value"] == Decimal("4.2")


def test_parse_tsh_age_group_neonate() -> None:
    entry = parse_age_group_range("01 - 04 Days                                              1.6 - 39.0")
    assert entry is not None
    assert entry["age_from_days"] == 1
    assert entry["age_to_days"] == 4


def test_parse_range_entries_skips_header_row() -> None:
    entries = parse_range_entries_from_row(
        {
            "rng1": "",
            "rng2": "AGE GROUP                                         TSH REFERENCE RANGE {m IU/L }",
            "rng3": "01 - 04 Days                                              1.6 - 39.0",
            "rng4": "21 - 80 Years                                             0.301-4.2",
            "min_value": None,
            "max_value": None,
        }
    )
    assert len(entries) == 2
    assert entries[0]["age_to_days"] == 4
    assert entries[1]["age_from_days"] == 21 * 365
