from datetime import datetime, timezone

import pytest

from app.services.patient_number import PatientNumberContext, PatientNumberGenerator, section_char_from_code


@pytest.fixture
def ctx() -> PatientNumberContext:
    return PatientNumberContext(
        prefix="P",
        section_char="P",
        now=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
    )


def test_section_daily_pattern(ctx: PatientNumberContext) -> None:
    gen = PatientNumberGenerator(3)
    pattern = "{SECTION}{YYYYMMDD}{SEQ:3}"
    scope = gen.build_scope_key(pattern, ctx)
    assert scope == "P20260619"
    assert gen.generate(pattern, ctx, 1) == "P20260619001"
    assert gen.generate(pattern, ctx, 12) == "P20260619012"


def test_prefix_short_date_pattern(ctx: PatientNumberContext) -> None:
    gen = PatientNumberGenerator(3)
    pattern = "{PREFIX}{YYMMDD}{SEQ:3}"
    assert gen.generate(pattern, ctx, 2) == "P260619002"


def test_simple_incremental_pattern(ctx: PatientNumberContext) -> None:
    gen = PatientNumberGenerator(0)
    pattern = "{SEQ}"
    assert gen.build_scope_key(pattern, ctx) == ""
    assert gen.generate(pattern, ctx, 3) == "3"


def test_custom_prefix_is_used() -> None:
    ctx = PatientNumberContext(
        prefix="H",
        section_char="O",
        now=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
    )
    gen = PatientNumberGenerator(3)
    assert gen.generate("{PREFIX}{YYYYMMDD}{SEQ:3}", ctx, 1) == "H20260619001"
    assert gen.generate("{P}{YYMMDD}{SEQ:3}", ctx, 2) == "H260619002"
    assert gen.generate("{SECTION}{YYYYMMDD}{SEQ:3}", ctx, 1) == "O20260619001"


def test_custom_prefix_k_is_used() -> None:
    ctx = PatientNumberContext(
        prefix="K",
        section_char="O",
        now=datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc),
    )
    gen = PatientNumberGenerator(3)
    assert gen.generate("{PREFIX}{YYYYMMDD}{SEQ:3}", ctx, 1) == "K20260619001"
    assert gen.generate("{P}{YYMMDD}{SEQ:3}", ctx, 2) == "K260619002"


def test_prefix_update_payload_keeps_prefix_value() -> None:
    from app.schemas.prefix import PrefixUpdate

    data = PrefixUpdate(name="Patient Prefix", prefix_value="k", sort_order=1)
    dumped = data.model_dump(exclude_unset=True, exclude_none=True)
    assert dumped["prefix_value"] == "k"
    assert dumped["name"] == "Patient Prefix"
