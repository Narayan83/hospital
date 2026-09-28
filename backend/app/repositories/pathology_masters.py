import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pathology_normal_range import PathologyNormalRange
from app.models.pathology_parameter import PathologyParameter, PathologyServiceParameter
from app.models.pathology_unit import PathologyUnit
from app.models.patient import Patient
from app.repositories.base import BaseRepository

_SHARED = Path(__file__).resolve().parents[3] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from pathology_ranges import AGE_UNIT_DAYS, days_to_age  # noqa: E402


class PathologyUnitRepository(BaseRepository[PathologyUnit]):
    model = PathologyUnit

    async def list_active(self) -> list[PathologyUnit]:
        result = await self.session.execute(
            select(PathologyUnit)
            .where(PathologyUnit.is_active.is_(True))
            .order_by(PathologyUnit.sort_order, PathologyUnit.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> PathologyUnit | None:
        result = await self.session.execute(
            select(PathologyUnit).where(PathologyUnit.code == code.upper())
        )
        return result.scalar_one_or_none()


class PathologyParameterRepository(BaseRepository[PathologyParameter]):
    model = PathologyParameter

    async def list_active(self) -> list[PathologyParameter]:
        result = await self.session.execute(
            select(PathologyParameter)
            .options(selectinload(PathologyParameter.unit))
            .where(PathologyParameter.is_active.is_(True))
            .order_by(PathologyParameter.sort_order, PathologyParameter.name)
        )
        return list(result.scalars().all())

    async def get_with_unit(self, parameter_id: str) -> PathologyParameter | None:
        result = await self.session.execute(
            select(PathologyParameter)
            .options(selectinload(PathologyParameter.unit))
            .where(PathologyParameter.id == parameter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> PathologyParameter | None:
        result = await self.session.execute(
            select(PathologyParameter).where(PathologyParameter.code == code.upper())
        )
        return result.scalar_one_or_none()


class PathologyServiceParameterRepository(BaseRepository[PathologyServiceParameter]):
    model = PathologyServiceParameter

    async def list_for_service(self, service_id: str) -> list[PathologyServiceParameter]:
        result = await self.session.execute(
            select(PathologyServiceParameter)
            .options(
                selectinload(PathologyServiceParameter.parameter).selectinload(PathologyParameter.unit),
                selectinload(PathologyServiceParameter.service),
            )
            .where(PathologyServiceParameter.service_id == service_id)
            .where(PathologyServiceParameter.is_active.is_(True))
            .order_by(PathologyServiceParameter.sort_order)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[PathologyServiceParameter]:
        result = await self.session.execute(
            select(PathologyServiceParameter)
            .options(
                selectinload(PathologyServiceParameter.parameter),
                selectinload(PathologyServiceParameter.service),
            )
            .where(PathologyServiceParameter.is_active.is_(True))
            .order_by(PathologyServiceParameter.service_id, PathologyServiceParameter.sort_order)
        )
        return list(result.scalars().all())

    async def get_mapping(self, service_id: str, parameter_id: str) -> PathologyServiceParameter | None:
        result = await self.session.execute(
            select(PathologyServiceParameter).where(
                PathologyServiceParameter.service_id == service_id,
                PathologyServiceParameter.parameter_id == parameter_id,
            )
        )
        return result.scalar_one_or_none()


class PathologyNormalRangeRepository(BaseRepository[PathologyNormalRange]):
    model = PathologyNormalRange

    async def list_active(self, parameter_id: str | None = None) -> list[PathologyNormalRange]:
        stmt = (
            select(PathologyNormalRange)
            .options(
                selectinload(PathologyNormalRange.parameter),
                selectinload(PathologyNormalRange.unit),
            )
            .where(PathologyNormalRange.is_active.is_(True))
            .order_by(PathologyNormalRange.parameter_id, PathologyNormalRange.sort_order)
        )
        if parameter_id:
            stmt = stmt.where(PathologyNormalRange.parameter_id == parameter_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_for_patient(
        self, parameter_id: str, patient: Patient
    ) -> PathologyNormalRange | None:
        age_days = _patient_age_days(patient)
        gender = (patient.gender or "A").upper()[:1]
        if gender not in ("M", "F"):
            gender = "A"
        result = await self.session.execute(
            select(PathologyNormalRange)
            .options(selectinload(PathologyNormalRange.unit))
            .where(PathologyNormalRange.parameter_id == parameter_id)
            .where(PathologyNormalRange.is_active.is_(True))
            .where(PathologyNormalRange.age_from_days <= age_days)
            .where(PathologyNormalRange.age_to_days >= age_days)
            .where(PathologyNormalRange.gender.in_([gender, "A"]))
            .order_by(
                PathologyNormalRange.gender.desc(),
                (PathologyNormalRange.age_to_days - PathologyNormalRange.age_from_days),
                PathologyNormalRange.sort_order,
            )
        )
        return result.scalars().first()


def _patient_age_days(patient: Patient) -> int:
    if not patient.date_of_birth:
        return 365 * 30
    return (date.today() - patient.date_of_birth).days


def format_range_text(rng: PathologyNormalRange | None, unit_name: str | None = None) -> str:
    if not rng:
        return "—"
    if rng.text_range:
        text = rng.text_range.strip()
    elif rng.min_value is not None and rng.max_value is not None:
        text = f"{Decimal(str(rng.min_value))} - {Decimal(str(rng.max_value))}"
    elif rng.min_value is not None:
        text = f">= {Decimal(str(rng.min_value))}"
    elif rng.max_value is not None:
        text = f"<= {Decimal(str(rng.max_value))}"
    else:
        return "—"
    if unit_name and unit_name.upper() not in text.upper():
        return f"{text} {unit_name}"
    return text


def is_value_abnormal(value: Decimal, rng: PathologyNormalRange | None) -> bool:
    if not rng:
        return False
    if rng.min_value is not None and value < Decimal(str(rng.min_value)):
        return True
    if rng.max_value is not None and value > Decimal(str(rng.max_value)):
        return True
    return False


# Pathology order workflow: one bill/order is shared by the billing counter and
# the lab/report counter — they're separated by status, not by duplicate data.
#   Billed -> Report Ready (set explicitly once every result is entered).
ORDER_STATUS_BILLED = "billed"
ORDER_STATUS_REPORT_READY = "report_ready"


def can_authorize(pending_count: int) -> bool:
    return pending_count == 0


_GENDER_LABELS = {"M": "Male", "F": "Female", "A": "All"}


def age_group_label(age_from_days: int, age_to_days: int) -> str:
    """Human age-group label like '01 - 04 Days' or '21 - 80 Years'."""
    from_val, from_unit = days_to_age(age_from_days)
    to_val, to_unit = days_to_age(age_to_days)
    if from_unit != to_unit:
        # Express both bounds in the larger bound's unit for a clean label.
        size = AGE_UNIT_DAYS.get(to_unit, 365)
        from_val = int(age_from_days // size)
    return f"{from_val:02d} - {to_val:02d} {to_unit.title()}"


def reference_range_rows(
    ranges: list[PathologyNormalRange],
    *,
    fallback_unit_name: str | None = None,
) -> list[dict]:
    """Build display rows (age group + range text) for all reference ranges of a test.

    Mirrors the legacy 'Additional Ranges' table that lists every age-group/gender
    normal range below the test name on the report.
    """
    rows: list[dict] = []
    for rng in sorted(ranges, key=lambda r: (r.sort_order, r.age_from_days)):
        unit_name = (rng.unit.name if rng.unit else None) or fallback_unit_name
        rows.append(
            {
                "age_group": age_group_label(rng.age_from_days, rng.age_to_days),
                "gender": _GENDER_LABELS.get((rng.gender or "A").upper(), rng.gender),
                "range_text": format_range_text(rng, unit_name),
            }
        )
    return rows
