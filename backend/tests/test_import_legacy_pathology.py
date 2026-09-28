"""Tests for legacy pathology SQL import (pservice + pprmtr)."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SHARED = ROOT / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pathology_legacy_units import LEGACY_UNIT_NAMES, normalize_uncd, service_code_for_legacy_cd
from pathology_ranges import parse_age_group_range, parse_range_entries_from_row
from scripts.import_legacy_pathology import parse_pprmtr_sql, parse_pservice_sql

REAL_SQL = Path(r"c:\Users\tss\OneDrive\Desktop\path.sql")


def test_legacy_units_count_and_tsh() -> None:
    assert len(LEGACY_UNIT_NAMES) == 28
    assert LEGACY_UNIT_NAMES[28] == "TSH"
    assert normalize_uncd(64) == 28
    assert normalize_uncd(4) == 4


def test_service_code_format() -> None:
    assert service_code_for_legacy_cd(13) == "P13"
    assert service_code_for_legacy_cd(115) == "P115"


def test_gender_from_range_text() -> None:
    entries = parse_range_entries_from_row(
        {"rng1": "MALE  60-165", "rng2": "FEMAIL  40-140", "min_value": None, "max_value": None}
    )
    assert entries[0]["gender"] == "M"
    assert entries[1]["gender"] == "F"


def test_parse_range_entries_gender_split() -> None:
    entries = parse_range_entries_from_row(
        {
            "rng1": "MALE  60-165",
            "rng2": "FEMAIL  40-140",
            "min_value": None,
            "max_value": None,
        }
    )
    assert len(entries) == 2
    assert entries[0]["gender"] == "M"
    assert entries[1]["gender"] == "F"


@pytest.fixture
def sample_sql(tmp_path: Path) -> Path:
    row = (
        "(126,NULL,13,150,'SERUM PROTEIN','',10,'Y','RMY','2023-05-07 13:15:19','LAB',"
        "'5.5-8.2','','','','','','','','','','','','','','',0.00,0.00,'','','','')"
    )
    row2 = (
        "(133,NULL,20,120,'TRIGLYCERIDES','',4,'Y','RMY','2023-05-07 13:25:05','LAB',"
        "'MALE  60-165','FEMAIL  40-140','','','','','','','','','','','','','',0.00,0.00,'','','','')"
    )
    row3 = (
        "(200,NULL,50,80,'HB','',3,'Y','RMY','2023-05-07 13:25:05','LAB',"
        "'11.5-16.0','','','','','','','','','','','','','','',11.50,16.00,'','','','')"
    )
    row4 = (
        "(201,NULL,51,80,'WBC','',18,'Y','RMY','2023-05-07 13:25:05','LAB',"
        "'','','','','','','','','','','','','','','',0.00,0.00,'','','','')"
    )
    row5 = (
        "(202,NULL,18,500,'CBC PANEL','',0,'Y','RMY','2023-05-10 12:46:12','LAB',"
        "'','','','','','','','','','','','','','','',0.00,0.00,'','','','')"
    )
    cols = (
        "`MKEY`,`MRK`,`CD`,`RATE`,`CNAME`,`REMARKS`,`uncd`,`STATUS`,`USER1`,`DATETIME1`,`SYSNM`,"
        "`RNG1`,`rng2`,`rng3`,`rng4`,`rng5`,`rng6`,`rng7`,`rng8`,`rng9`,`rng10`,"
        "`rng11`,`rng12`,`rng13`,`rng14`,`rng15`,`minrng1`,`maxrng1`,`nrng2`,`nrng3`,`nrng4`,`nrng5`"
    )
    content = f"""
insert into `pservice`({cols}) values
{row},{row2},{row3},{row4},{row5};

insert into `pprmtr`(`mkey`,`mrk`,`maincd`,`subcd`,`datetime`,`user1`) values
(20,NULL,18,50,'2023-05-10 12:46:12','RMY'),
(21,NULL,18,51,'2023-05-10 12:46:12','RMY');
"""
    path = tmp_path / "path_sample.sql"
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_pservice_sql(sample_sql: Path) -> None:
    rows = parse_pservice_sql(sample_sql)
    assert len(rows) == 5
    protein = next(r for r in rows if r["legacy_cd"] == 13)
    assert protein["code"] == "P13"
    assert protein["uncd"] == 10
    assert len(protein["range_entries"]) == 1
    tg = next(r for r in rows if r["legacy_cd"] == 20)
    assert len(tg["range_entries"]) == 2


def test_parse_pprmtr_sql(sample_sql: Path) -> None:
    mappings = parse_pprmtr_sql(sample_sql)
    assert mappings == [{"maincd": 18, "subcd": 50}, {"maincd": 18, "subcd": 51}]


@pytest.mark.skipif(not REAL_SQL.exists(), reason="Legacy path.sql not on this machine")
def test_parse_real_path_sql() -> None:
    rows = parse_pservice_sql(REAL_SQL)
    assert len(rows) >= 100
    protein = next(r for r in rows if r["legacy_cd"] == 13)
    assert protein["code"] == "P13"
    assert protein["uncd"] == 10
    mappings = parse_pprmtr_sql(REAL_SQL)
    assert len(mappings) >= 90


def test_import_pathology_dry_run(sample_sql: Path) -> None:
    import asyncio

    from scripts.import_legacy_pathology import import_pathology

    stats = asyncio.run(import_pathology(sample_sql, dry_run=True))
    assert stats["units_created"] == 28
    assert stats["services_created"] + stats["services_updated"] == 5
    assert stats["parameters_created"] + stats["parameters_updated"] == 5
    assert stats["bundle_members_created"] == 2
    # Panel P18 has children — no self mapping; P50/P51 are subs — no self mapping
    assert stats["self_mappings_created"] == 2  # P13, P20 standalone
