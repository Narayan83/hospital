"""Parse legacy pservice RNG / nrng text into structured normal ranges."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_AGE_ROW = re.compile(
    r"(\d+)\s*-\s*(\d+)\s*(day|days|week|weeks|month|months|year|years)\b",
    re.IGNORECASE,
)
_NUMERIC_RANGE = re.compile(r"([\d.]+)\s*-\s*([\d.]+)")

_UNIT_DAYS = {
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}

# Canonical age units used by the Lab Test Master reference-range grid.
AGE_UNIT_DAYS = {"days": 1, "weeks": 7, "months": 30, "years": 365}


def age_to_days(value: int, unit: str) -> int:
    return int(value) * AGE_UNIT_DAYS.get((unit or "years").lower(), 365)


def days_to_age(days: int) -> tuple[int, str]:
    """Convert a day count back to the largest whole age unit for display."""
    days = int(days)
    for unit in ("years", "months", "weeks", "days"):
        size = AGE_UNIT_DAYS[unit]
        if days % size == 0:
            return days // size, unit
    return days, "days"


def _gender_from_range_text(text: str) -> str:
    upper = text.upper()
    if "FEMALE" in upper or "FEMAIL" in upper:
        return "F"
    if "MALE" in upper:
        return "M"
    return "A"


def _is_header_row(text: str) -> bool:
    upper = text.upper()
    return "AGE GROUP" in upper and "REFERENCE" in upper


def parse_age_group_range(text: str, *, sort_order: int = 0) -> dict | None:
    """Parse rows like '01 - 04 Days ... 1.6 - 39.0' or '21 - 80 Years ... 0.301-4.2'."""
    cleaned = " ".join(text.split())
    if not cleaned or _is_header_row(cleaned):
        return None
    age_match = _AGE_ROW.search(cleaned)
    if not age_match:
        return None
    lo = int(age_match.group(1))
    hi = int(age_match.group(2))
    unit = age_match.group(3).lower()
    mult = _UNIT_DAYS.get(unit, 1)
    tail = cleaned[age_match.end() :].strip()
    nums = _NUMERIC_RANGE.search(tail)
    entry: dict = {
        "gender": "A",
        "age_from_days": lo * mult,
        "age_to_days": hi * mult,
        "sort_order": sort_order,
    }
    if nums:
        try:
            entry["min_value"] = Decimal(nums.group(1))
            entry["max_value"] = Decimal(nums.group(2))
            entry["text_range"] = None
        except InvalidOperation:
            entry["min_value"] = None
            entry["max_value"] = None
            entry["text_range"] = cleaned[:200]
    else:
        entry["min_value"] = None
        entry["max_value"] = None
        entry["text_range"] = cleaned[:200]
    return entry


def parse_range_entries_from_row(row: dict) -> list[dict]:
    """Build normal-range dicts from a pservice row (rng1-15, nrng2-5, min/max)."""
    entries: list[dict] = []
    lower = {k.lower(): v for k, v in row.items()}

    sort_idx = 0
    for idx in range(1, 11):
        text = (lower.get(f"rng{idx}") or "").strip()
        if not text or _is_header_row(text):
            continue
        age_entry = parse_age_group_range(text, sort_order=sort_idx)
        if age_entry:
            entries.append(age_entry)
            sort_idx += 1
            continue
        entries.append(
            {
                "gender": _gender_from_range_text(text),
                "age_from_days": 0,
                "age_to_days": 36500,
                "text_range": text[:200],
                "min_value": None,
                "max_value": None,
                "sort_order": sort_idx,
            }
        )
        sort_idx += 1

    for key in ("nrng2", "nrng3", "nrng4", "nrng5"):
        text = (lower.get(key) or "").strip()
        if not text or _is_header_row(text):
            continue
        age_entry = parse_age_group_range(text, sort_order=sort_idx)
        if age_entry:
            entries.append(age_entry)
        else:
            entries.append(
                {
                    "gender": _gender_from_range_text(text),
                    "age_from_days": 0,
                    "age_to_days": 36500,
                    "text_range": text[:200],
                    "min_value": None,
                    "max_value": None,
                    "sort_order": sort_idx,
                }
            )
        sort_idx += 1

    min_val = row.get("min_value")
    max_val = row.get("max_value")
    if min_val is not None or max_val is not None:
        entries.append(
            {
                "gender": "A",
                "age_from_days": 0,
                "age_to_days": 36500,
                "text_range": None,
                "min_value": min_val,
                "max_value": max_val,
                "sort_order": sort_idx,
            }
        )

    seen: set[tuple] = set()
    unique: list[dict] = []
    for entry in entries:
        key = (
            entry["gender"],
            entry.get("age_from_days"),
            entry.get("age_to_days"),
            entry.get("text_range"),
            entry.get("min_value"),
            entry.get("max_value"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique
