"""Unified lab-test / profile management.

A "lab test" the user sees is stored as:
  - a billable PatientServiceMaster (LAB category)   -> the price + name
  - a 1:1 PathologyParameter (same auto code)         -> unit, result type, ranges

A "profile" is a billable PatientServiceMaster whose member tests are linked
through PathologyServiceParameter rows. Codes are auto-generated from the name
and never shown to the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pathology_normal_range import PathologyNormalRange
from app.models.pathology_parameter import PathologyParameter, PathologyServiceParameter
from app.models.pathology_service_member import PathologyServiceMember
from app.models.patient_service_master import PatientServiceMaster
from app.models.service_category import ServiceCategory
from app.schemas.lab_test import (
    LabTestRead,
    LabTestSave,
    ProfileMember,
    ProfileRead,
    ProfileSave,
    ReferenceRangeRead,
)

import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parents[3] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from pathology_ranges import age_to_days, days_to_age  # noqa: E402


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "", name.upper())
    return cleaned[:24] or "TEST"


@dataclass
class _Catalog:
    """In-memory snapshot of the lab catalog used to build list responses
    without per-item database queries."""

    services: list[PatientServiceMaster]
    params_by_code: dict[str, PathologyParameter]
    params_by_id: dict[str, PathologyParameter]
    ranges_by_param: dict[str, list[PathologyNormalRange]]
    mappings_by_service: dict[str, list[PathologyServiceParameter]]
    units_by_id: dict[str, "PathologyUnit"]
    subs_by_id: dict[str, "ServiceSubCategory"]
    services_by_code: dict[str, PatientServiceMaster]
    services_by_id: dict[str, PatientServiceMaster]
    members_by_bundle: dict[str, list[PathologyServiceMember]]


class LabTestService:
    LAB_CATEGORY_CODE = "LAB"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _lab_category_id(self) -> str:
        cat = (
            await self.session.execute(
                select(ServiceCategory).where(ServiceCategory.code == self.LAB_CATEGORY_CODE)
            )
        ).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=500, detail="LAB service category not configured")
        return cat.id

    async def _existing_codes(self) -> set[str]:
        rows = (await self.session.execute(select(PatientServiceMaster.code))).scalars().all()
        return {c for c in rows if c}

    async def _unique_code(self, name: str) -> str:
        base = _slug(name)
        existing = await self._existing_codes()
        if base not in existing:
            return base
        suffix = 2
        while True:
            candidate = f"{base[:24]}{suffix}"[:30]
            if candidate not in existing:
                return candidate
            suffix += 1

    async def _analyte_for(self, service: PatientServiceMaster) -> PathologyParameter | None:
        return (
            await self.session.execute(
                select(PathologyParameter).where(PathologyParameter.code == service.code)
            )
        ).scalar_one_or_none()

    async def _ranges_for(self, analyte_id: str) -> list[PathologyNormalRange]:
        rows = (
            await self.session.execute(
                select(PathologyNormalRange)
                .where(PathologyNormalRange.parameter_id == analyte_id)
                .where(PathologyNormalRange.is_active.is_(True))
                .order_by(PathologyNormalRange.sort_order)
            )
        ).scalars().all()
        return list(rows)

    async def _mappings_for(self, service_id: str) -> list[PathologyServiceParameter]:
        rows = (
            await self.session.execute(
                select(PathologyServiceParameter)
                .where(PathologyServiceParameter.service_id == service_id)
                .where(PathologyServiceParameter.is_active.is_(True))
            )
        ).scalars().all()
        return list(rows)

    async def _members_for(self, bundle_service_id: str) -> list[PathologyServiceMember]:
        rows = (
            await self.session.execute(
                select(PathologyServiceMember)
                .where(PathologyServiceMember.bundle_service_id == bundle_service_id)
                .where(PathologyServiceMember.is_active.is_(True))
                .order_by(PathologyServiceMember.sort_order)
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    def _range_read(rng: PathologyNormalRange) -> ReferenceRangeRead:
        age_from, unit_from = days_to_age(rng.age_from_days)
        age_to, _unit_to = days_to_age(rng.age_to_days)
        return ReferenceRangeRead(
            id=rng.id,
            gender=rng.gender,
            age_from=age_from,
            age_to=age_to,
            age_unit=unit_from,
            low=rng.min_value,
            high=rng.max_value,
            text_range=rng.text_range,
        )

    async def _is_profile(self, service: PatientServiceMaster) -> bool:
        """A service is a bundle/profile when it has service members."""
        return bool(await self._members_for(service.id))

    async def _lab_services(self) -> list[PatientServiceMaster]:
        cat_id = await self._lab_category_id()
        rows = (
            await self.session.execute(
                select(PatientServiceMaster)
                .where(PatientServiceMaster.category_id == cat_id)
                .where(PatientServiceMaster.is_active.is_(True))
                .order_by(PatientServiceMaster.name)
            )
        ).scalars().all()
        return list(rows)

    async def _catalog(self) -> "_Catalog":
        """Bulk-load the whole lab catalog in a few queries (avoids N+1).

        The per-item helpers issue one query each; iterating them over the
        full legacy catalog produced thousands of sequential round-trips and
        made the master screens load very slowly.
        """
        cat_id = await self._lab_category_id()
        services = list(
            (
                await self.session.execute(
                    select(PatientServiceMaster)
                    .where(PatientServiceMaster.category_id == cat_id)
                    .where(PatientServiceMaster.is_active.is_(True))
                    .order_by(PatientServiceMaster.name)
                )
            ).scalars().all()
        )

        params = (await self.session.execute(select(PathologyParameter))).scalars().all()
        params_by_code: dict[str, PathologyParameter] = {}
        params_by_id: dict[str, PathologyParameter] = {}
        for param in params:
            params_by_id[param.id] = param
            if param.code:
                params_by_code[param.code] = param

        ranges_by_param: dict[str, list[PathologyNormalRange]] = {}
        range_rows = (
            await self.session.execute(
                select(PathologyNormalRange)
                .where(PathologyNormalRange.is_active.is_(True))
                .order_by(PathologyNormalRange.sort_order)
            )
        ).scalars().all()
        for rng in range_rows:
            ranges_by_param.setdefault(rng.parameter_id, []).append(rng)

        mappings_by_service: dict[str, list[PathologyServiceParameter]] = {}
        map_rows = (
            await self.session.execute(
                select(PathologyServiceParameter).where(
                    PathologyServiceParameter.is_active.is_(True)
                )
            )
        ).scalars().all()
        for mapping in map_rows:
            mappings_by_service.setdefault(mapping.service_id, []).append(mapping)

        members_by_bundle: dict[str, list[PathologyServiceMember]] = {}
        member_rows = (
            await self.session.execute(
                select(PathologyServiceMember).where(
                    PathologyServiceMember.is_active.is_(True)
                )
            )
        ).scalars().all()
        for member in member_rows:
            members_by_bundle.setdefault(member.bundle_service_id, []).append(member)
        for rows in members_by_bundle.values():
            rows.sort(key=lambda m: m.sort_order)

        units_by_id = {
            u.id: u
            for u in (await self.session.execute(select(PathologyUnit))).scalars().all()
        }
        subs_by_id = {
            s.id: s
            for s in (
                await self.session.execute(select(ServiceSubCategory))
            ).scalars().all()
        }
        services_by_code: dict[str, PatientServiceMaster] = {
            s.code: s for s in services if s.code
        }
        services_by_id: dict[str, PatientServiceMaster] = {s.id: s for s in services}

        return _Catalog(
            services=services,
            params_by_code=params_by_code,
            params_by_id=params_by_id,
            ranges_by_param=ranges_by_param,
            mappings_by_service=mappings_by_service,
            units_by_id=units_by_id,
            subs_by_id=subs_by_id,
            services_by_code=services_by_code,
            services_by_id=services_by_id,
            members_by_bundle=members_by_bundle,
        )

    @staticmethod
    def _is_profile_cached(service: PatientServiceMaster, cat: "_Catalog") -> bool:
        return bool(cat.members_by_bundle.get(service.id))

    async def list_tests(self) -> list[LabTestRead]:
        cat = await self._catalog()
        out: list[LabTestRead] = []
        for service in cat.services:
            if self._is_profile_cached(service, cat):
                continue
            out.append(self._test_read_cached(service, cat))
        return out

    def _test_read_cached(self, service: PatientServiceMaster, cat: "_Catalog") -> LabTestRead:
        analyte = cat.params_by_code.get(service.code)
        unit_name = None
        unit_id = None
        result_type = "numeric"
        method = None
        ranges: list[ReferenceRangeRead] = []
        if analyte:
            unit_id = analyte.unit_id
            result_type = analyte.data_type or "numeric"
            method = analyte.method
            if analyte.unit_id:
                unit = cat.units_by_id.get(analyte.unit_id)
                unit_name = unit.name if unit else None
            ranges = [self._range_read(r) for r in cat.ranges_by_param.get(analyte.id, [])]
        sub_name = None
        if service.sub_category_id:
            sub = cat.subs_by_id.get(service.sub_category_id)
            sub_name = sub.name if sub else None
        return LabTestRead(
            id=service.id,
            code=service.code,
            name=service.name,
            price=Decimal(str(service.rate)),
            unit_id=unit_id,
            unit_name=unit_name,
            result_type=result_type,
            method=method,
            sub_category_id=service.sub_category_id,
            sub_category_name=sub_name,
            is_profile=False,
            ranges=ranges,
        )

    async def _test_read(self, service: PatientServiceMaster) -> LabTestRead:
        analyte = await self._analyte_for(service)
        unit_name = None
        unit_id = None
        result_type = "numeric"
        method = None
        ranges: list[ReferenceRangeRead] = []
        if analyte:
            unit_id = analyte.unit_id
            result_type = analyte.data_type or "numeric"
            method = analyte.method
            if analyte.unit_id:
                unit = (
                    await self.session.execute(
                        select(PathologyUnit).where(PathologyUnit.id == analyte.unit_id)
                    )
                ).scalar_one_or_none()
                unit_name = unit.name if unit else None
            ranges = [self._range_read(r) for r in await self._ranges_for(analyte.id)]
        sub_name = None
        if service.sub_category_id:
            sub = (
                await self.session.execute(
                    select(ServiceSubCategory).where(ServiceSubCategory.id == service.sub_category_id)
                )
            ).scalar_one_or_none()
            sub_name = sub.name if sub else None
        return LabTestRead(
            id=service.id,
            code=service.code,
            name=service.name,
            price=Decimal(str(service.rate)),
            unit_id=unit_id,
            unit_name=unit_name,
            result_type=result_type,
            method=method,
            sub_category_id=service.sub_category_id,
            sub_category_name=sub_name,
            is_profile=False,
            ranges=ranges,
        )

    async def save_test(self, data: LabTestSave, test_id: str | None = None) -> LabTestRead:
        cat_id = await self._lab_category_id()
        name = data.name.strip()

        if test_id:
            service = (
                await self.session.execute(
                    select(PatientServiceMaster).where(PatientServiceMaster.id == test_id)
                )
            ).scalar_one_or_none()
            if not service:
                raise HTTPException(status_code=404, detail="Lab test not found")
            service.name = name
            service.rate = data.price
            service.service_charge = data.price
            service.sub_category_id = data.sub_category_id
            service.is_service_active = True
            service.is_active = True
        else:
            code = await self._unique_code(name)
            service = PatientServiceMaster(
                code=code,
                name=name,
                rate=data.price,
                service_charge=data.price,
                category_id=cat_id,
                sub_category_id=data.sub_category_id,
                is_sharing=False,
                discount_apply=False,
                is_renewal=False,
                is_service_active=True,
                is_active=True,
            )
            self.session.add(service)
        await self.session.flush()

        analyte = await self._analyte_for(service)
        if analyte:
            analyte.name = name
            analyte.unit_id = data.unit_id
            analyte.data_type = data.result_type
            analyte.method = data.method
            analyte.is_active = True
        else:
            analyte = PathologyParameter(
                code=service.code,
                name=name,
                unit_id=data.unit_id,
                data_type=data.result_type,
                method=data.method,
                sort_order=0,
                is_active=True,
            )
            self.session.add(analyte)
        await self.session.flush()

        # Self-mapping so a single test still produces one result line on billing.
        self_map = (
            await self.session.execute(
                select(PathologyServiceParameter)
                .where(PathologyServiceParameter.service_id == service.id)
                .where(PathologyServiceParameter.parameter_id == analyte.id)
            )
        ).scalar_one_or_none()
        if self_map:
            self_map.is_active = True
        else:
            self.session.add(
                PathologyServiceParameter(
                    service_id=service.id,
                    parameter_id=analyte.id,
                    sort_order=0,
                    is_required=True,
                    is_active=True,
                )
            )

        await self._replace_ranges(analyte, data)
        await self.session.flush()
        return await self._test_read(service)

    async def _replace_ranges(self, analyte: PathologyParameter, data: LabTestSave) -> None:
        for old in await self._ranges_for(analyte.id):
            old.is_active = False
        for index, rng in enumerate(data.ranges):
            self.session.add(
                PathologyNormalRange(
                    parameter_id=analyte.id,
                    gender=rng.gender,
                    age_from_days=age_to_days(rng.age_from, rng.age_unit),
                    age_to_days=age_to_days(rng.age_to, rng.age_unit),
                    min_value=rng.low,
                    max_value=rng.high,
                    text_range=(rng.text_range.strip() if rng.text_range else None),
                    unit_id=analyte.unit_id,
                    sort_order=index,
                    is_active=True,
                )
            )

    async def delete_test(self, test_id: str) -> None:
        service = (
            await self.session.execute(
                select(PatientServiceMaster).where(PatientServiceMaster.id == test_id)
            )
        ).scalar_one_or_none()
        if not service:
            raise HTTPException(status_code=404, detail="Lab test not found")
        service.is_active = False
        service.is_service_active = False
        analyte = await self._analyte_for(service)
        if analyte:
            analyte.is_active = False
            for rng in await self._ranges_for(analyte.id):
                rng.is_active = False
        for mapping in await self._mappings_for(service.id):
            mapping.is_active = False
        await self.session.flush()

    # ----- profiles -------------------------------------------------------

    async def list_profiles(self) -> list[ProfileRead]:
        cat = await self._catalog()
        out: list[ProfileRead] = []
        for service in cat.services:
            if not self._is_profile_cached(service, cat):
                continue
            out.append(self._profile_read_cached(service, cat))
        return out

    def _profile_read_cached(self, service: PatientServiceMaster, cat: "_Catalog") -> ProfileRead:
        members: list[ProfileMember] = []
        for member in cat.members_by_bundle.get(service.id, []):
            member_service = cat.services_by_id.get(member.member_service_id)
            if member_service:
                members.append(
                    ProfileMember(
                        id=member_service.id,
                        code=member_service.code,
                        name=member_service.name,
                        is_bundle=bool(cat.members_by_bundle.get(member_service.id)),
                    )
                )
        sub_name = None
        if service.sub_category_id:
            sub = cat.subs_by_id.get(service.sub_category_id)
            sub_name = sub.name if sub else None
        return ProfileRead(
            id=service.id,
            code=service.code,
            name=service.name,
            price=Decimal(str(service.rate)),
            sub_category_id=service.sub_category_id,
            sub_category_name=sub_name,
            members=members,
        )

    async def _profile_read(self, service: PatientServiceMaster) -> ProfileRead:
        members: list[ProfileMember] = []
        for member in await self._members_for(service.id):
            member_service = (
                await self.session.execute(
                    select(PatientServiceMaster).where(
                        PatientServiceMaster.id == member.member_service_id
                    )
                )
            ).scalar_one_or_none()
            if member_service:
                members.append(
                    ProfileMember(
                        id=member_service.id,
                        code=member_service.code,
                        name=member_service.name,
                        is_bundle=bool(await self._members_for(member_service.id)),
                    )
                )
        sub_name = None
        if service.sub_category_id:
            sub = (
                await self.session.execute(
                    select(ServiceSubCategory).where(ServiceSubCategory.id == service.sub_category_id)
                )
            ).scalar_one_or_none()
            sub_name = sub.name if sub else None
        return ProfileRead(
            id=service.id,
            code=service.code,
            name=service.name,
            price=Decimal(str(service.rate)),
            sub_category_id=service.sub_category_id,
            sub_category_name=sub_name,
            members=members,
        )

    async def save_profile(self, data: ProfileSave, profile_id: str | None = None) -> ProfileRead:
        cat_id = await self._lab_category_id()
        name = data.name.strip()
        if profile_id:
            service = (
                await self.session.execute(
                    select(PatientServiceMaster).where(PatientServiceMaster.id == profile_id)
                )
            ).scalar_one_or_none()
            if not service:
                raise HTTPException(status_code=404, detail="Profile not found")
            service.name = name
            service.rate = data.price
            service.service_charge = data.price
            service.sub_category_id = data.sub_category_id
            service.is_service_active = True
            service.is_active = True
        else:
            code = await self._unique_code(name)
            service = PatientServiceMaster(
                code=code,
                name=name,
                rate=data.price,
                service_charge=data.price,
                category_id=cat_id,
                sub_category_id=data.sub_category_id,
                is_sharing=False,
                discount_apply=False,
                is_renewal=False,
                is_service_active=True,
                is_active=True,
            )
            self.session.add(service)
        await self.session.flush()

        await self._set_members(service, data.member_test_ids)
        await self.session.flush()
        return await self._profile_read(service)

    async def _set_members(self, service: PatientServiceMaster, member_test_ids: list[str]) -> None:
        # A bundle owns no analytes of its own — deactivate any stale self/analyte
        # mappings, then store member services in the service->service table.
        for mapping in await self._mappings_for(service.id):
            mapping.is_active = False

        existing_rows = (
            await self.session.execute(
                select(PathologyServiceMember).where(
                    PathologyServiceMember.bundle_service_id == service.id
                )
            )
        ).scalars().all()
        existing_by_member = {row.member_service_id: row for row in existing_rows}
        for row in existing_rows:
            row.is_active = False

        seen: set[str] = set()
        index = 0
        for member_id in member_test_ids:
            if member_id in seen or member_id == service.id:
                continue
            member = (
                await self.session.execute(
                    select(PatientServiceMaster).where(PatientServiceMaster.id == member_id)
                )
            ).scalar_one_or_none()
            if not member or not member.is_active:
                continue
            if await self._would_create_cycle(service.id, member_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{member.name}' cannot be added — it would create a circular bundle.",
                )
            seen.add(member_id)
            row = existing_by_member.get(member_id)
            if row is not None:
                row.is_active = True
                row.sort_order = index
            else:
                self.session.add(
                    PathologyServiceMember(
                        bundle_service_id=service.id,
                        member_service_id=member_id,
                        sort_order=index,
                        is_active=True,
                    )
                )
            index += 1
        await self.session.flush()

    async def _would_create_cycle(self, bundle_id: str, member_id: str) -> bool:
        """True if adding ``member_id`` under ``bundle_id`` would make a cycle."""
        if member_id == bundle_id:
            return True
        # Walk the members of the candidate; if we reach the bundle, it's a cycle.
        stack = [member_id]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            for row in await self._members_for(current):
                if row.member_service_id == bundle_id:
                    return True
                stack.append(row.member_service_id)
        return False

    async def delete_profile(self, profile_id: str) -> None:
        service = (
            await self.session.execute(
                select(PatientServiceMaster).where(PatientServiceMaster.id == profile_id)
            )
        ).scalar_one_or_none()
        if not service:
            raise HTTPException(status_code=404, detail="Profile not found")
        service.is_active = False
        service.is_service_active = False
        for member in await self._members_for(service.id):
            member.is_active = False
        await self.session.flush()


# Imports placed at end to avoid circulars in type checkers; resolved at runtime.
from app.models.pathology_unit import PathologyUnit  # noqa: E402
from app.models.service_sub_category import ServiceSubCategory  # noqa: E402
