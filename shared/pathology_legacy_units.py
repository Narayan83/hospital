"""Legacy pathology unit codes (uncd) from pservice.uncd field."""

from __future__ import annotations

# CD -> unit display name (CNAME in legacy unit master)
LEGACY_UNIT_NAMES: dict[int, str] = {
    1: "POSITIVE",
    2: "grms",
    3: "g%",
    4: "mg/dl",
    5: "NON - REACTIVE",
    6: "NEGATIVE",
    7: "mIU/ml",
    8: "nmol/ml",
    9: "%",
    10: "g/dl",
    11: "million/ cumm",
    12: "fl",
    13: "pg",
    14: "NEUTROPHILS",
    15: "LYMPHOCYTES",
    16: "MONOCYTES",
    17: "EOSINOPHILS",
    18: "cells/cumm",
    19: "lakhs/cumm",
    20: "pg",
    21: "U/L",
    22: "mu/ml",
    23: "g/dl",
    24: "nmol / L",
    25: "ng/mL",
    26: "min",
    27: "mg/L",
    28: "TSH",  # legacy CD 64 remapped to 28
}

# Legacy pservice rows may still reference uncd=64 for TSH.
UNCd_REMAP: dict[int, int] = {64: 28}


def normalize_uncd(uncd: int) -> int:
    return UNCd_REMAP.get(uncd, uncd)


def unit_code_for_legacy_cd(cd: int) -> str:
    return f"U{cd:02d}"


def legacy_units_for_import() -> dict[int, tuple[str, str]]:
    """uncd -> (HMS unit code, display name)."""
    items: dict[int, tuple[str, str]] = {}
    for cd, name in LEGACY_UNIT_NAMES.items():
        items[cd] = (unit_code_for_legacy_cd(cd), name)
    return items


def service_code_for_legacy_cd(cd: int) -> str:
    """Industry mapping: pservice.CD is the stable service / parameter code."""
    return f"P{cd}"[:30]
