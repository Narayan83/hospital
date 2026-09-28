from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.pathology_bill import PathologyBill, PathologyBillLine
from app.models.patient_service_master import PatientServiceMaster
from app.schemas.pathology_collection_report import (
    PathologyCollectionColumnGroup,
    PathologyCollectionColumnReportRead,
    PathologyCollectionColumnRow,
    PathologyCollectionDateGroup,
    PathologyCollectionDetailRow,
    PathologyCollectionGroup,
    PathologyCollectionReportRead,
    PathologyCollectionServiceColumn,
    PathologyCollectionServiceSummaryRow,
)


class PathologyCollectionReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _payment_mode_label(bill: PathologyBill) -> str:
        mode = getattr(bill, "payment_mode", None)
        name = (getattr(mode, "name", None) or "").strip()
        return name or "—"

    @staticmethod
    def _line_amount(line: PathologyBillLine) -> Decimal:
        amount = Decimal(str(getattr(line, "amount", None) or 0))
        if amount > 0:
            return amount
        rate = Decimal(str(getattr(line, "rate", None) or 0))
        qty = Decimal(str(getattr(line, "quantity", None) or 1))
        return rate * qty

    @staticmethod
    def _normalize_referral(value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None

    async def build_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        referral_names: list[str] | None = None,
        report_type: str = "normal",
    ) -> PathologyCollectionReportRead | PathologyCollectionColumnReportRead:
        if report_type == "column_wise":
            return await self.build_column_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
            )
        if report_type == "referral_wise":
            return await self.build_referral_summary_report(
                from_date=from_date,
                to_date=to_date,
                referral_names=referral_names,
            )
        return await self.build_normal_report(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            referral_names=None,
            group_by="pathologist",
        )

    async def build_referral_summary_report(
        self,
        *,
        from_date: date,
        to_date: date,
        referral_names: list[str] | None = None,
    ) -> PathologyCollectionReportRead:
        """One row per bill (bill net amount) grouped by reference/referring doctor."""
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        raw_rows = await self._fetch_referral_bill_rows(
            from_date=from_date,
            to_date=to_date,
            referral_names=referral_names,
        )

        doctor_ids_needed = {row[0] for row in raw_rows if row[0]}
        doctor_name_map = await self._doctor_names(doctor_ids_needed)

        grouped: dict[str, dict[date, list[PathologyCollectionDetailRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        group_labels: dict[str, str] = {}

        for (
            doctor_id,
            patient_name,
            bill_date,
            bill_no,
            patient_no,
            payment_mode,
            referring_doctor,
            amount,
        ) in raw_rows:
            pathologist_name = doctor_name_map.get(doctor_id or "", "—") if doctor_id else "—"
            referral_label = self._normalize_referral(referring_doctor) or "—"
            group_key = referral_label.casefold()
            group_labels[group_key] = referral_label
            grouped[group_key][bill_date].append(
                PathologyCollectionDetailRow(
                    bill_date=bill_date,
                    bill_no=bill_no,
                    patient_no=patient_no,
                    patient_name=patient_name,
                    payment_mode=payment_mode,
                    pathologist_name=pathologist_name,
                    referring_doctor=referral_label,
                    service_name="—",
                    rate=Decimal("0"),
                    amount=amount,
                )
            )

        groups: list[PathologyCollectionGroup] = []
        overall_total = Decimal("0")

        for group_key in sorted(
            grouped.keys(),
            key=lambda value: group_labels.get(value, value).casefold(),
        ):
            date_groups: list[PathologyCollectionDateGroup] = []
            group_total = Decimal("0")

            for bill_date in sorted(grouped[group_key].keys()):
                rows = sorted(
                    grouped[group_key][bill_date],
                    key=lambda row: (row.bill_no, row.patient_no),
                )
                # One bill once — collapse any accidental duplicates by bill_no.
                unique: dict[str, PathologyCollectionDetailRow] = {}
                for row in rows:
                    unique[row.bill_no] = row
                rows = list(unique.values())
                rows.sort(key=lambda row: (row.bill_no, row.patient_no))
                date_total = sum((row.amount for row in rows), Decimal("0"))
                date_groups.append(
                    PathologyCollectionDateGroup(
                        bill_date=bill_date,
                        rows=rows,
                        total_amount=date_total,
                    )
                )
                group_total += date_total

            groups.append(
                PathologyCollectionGroup(
                    group_key=group_key,
                    group_name=group_labels.get(group_key, group_key),
                    date_groups=date_groups,
                    service_summary=[],
                    grand_total_amount=group_total,
                )
            )
            overall_total += group_total

        return PathologyCollectionReportRead(
            report_type="referral_wise",
            from_date=from_date,
            to_date=to_date,
            groups=groups,
            overall_total_amount=overall_total,
        )

    async def build_normal_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        referral_names: list[str] | None = None,
        group_by: str = "pathologist",
    ) -> PathologyCollectionReportRead:
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        raw_rows = await self._fetch_detail_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            referral_names=referral_names,
            require_referral=(group_by == "referral"),
        )

        doctor_ids_needed = {row[0] for row in raw_rows if row[0]}
        doctor_name_map = await self._doctor_names(doctor_ids_needed)

        grouped: dict[str, dict[date, list[PathologyCollectionDetailRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        group_labels: dict[str, str] = {}

        for (
            doctor_id,
            patient_name,
            bill_date,
            bill_no,
            patient_no,
            payment_mode,
            referring_doctor,
            service_name,
            rate,
            amount,
        ) in raw_rows:
            pathologist_name = doctor_name_map.get(doctor_id or "", "—") if doctor_id else "—"
            referral_label = self._normalize_referral(referring_doctor) or "—"

            if group_by == "referral":
                group_key = referral_label.casefold()
                group_name = referral_label
            else:
                if not doctor_id:
                    continue
                group_key = doctor_id
                group_name = pathologist_name if pathologist_name != "—" else doctor_id

            group_labels[group_key] = group_name
            grouped[group_key][bill_date].append(
                PathologyCollectionDetailRow(
                    bill_date=bill_date,
                    bill_no=bill_no,
                    patient_no=patient_no,
                    patient_name=patient_name,
                    payment_mode=payment_mode,
                    pathologist_name=pathologist_name,
                    referring_doctor=referral_label,
                    service_name=service_name,
                    rate=rate,
                    amount=amount,
                )
            )

        groups: list[PathologyCollectionGroup] = []
        overall_total = Decimal("0")

        for group_key in sorted(
            grouped.keys(),
            key=lambda value: group_labels.get(value, value).casefold(),
        ):
            date_groups: list[PathologyCollectionDateGroup] = []
            service_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            group_total = Decimal("0")

            for bill_date in sorted(grouped[group_key].keys()):
                rows = sorted(
                    grouped[group_key][bill_date],
                    key=lambda row: (
                        row.patient_no,
                        row.service_name.casefold(),
                        row.bill_no,
                    ),
                )
                date_total = sum((row.amount for row in rows), Decimal("0"))
                date_groups.append(
                    PathologyCollectionDateGroup(
                        bill_date=bill_date,
                        rows=rows,
                        total_amount=date_total,
                    )
                )
                group_total += date_total
                for row in rows:
                    service_totals[row.service_name] += row.amount

            service_summary = [
                PathologyCollectionServiceSummaryRow(
                    service_name=service_name,
                    total_amount=total,
                )
                for service_name, total in sorted(
                    service_totals.items(),
                    key=lambda item: item[0].casefold(),
                )
            ]

            groups.append(
                PathologyCollectionGroup(
                    group_key=group_key,
                    group_name=group_labels.get(group_key, group_key),
                    date_groups=date_groups,
                    service_summary=service_summary,
                    grand_total_amount=group_total,
                )
            )
            overall_total += group_total

        return PathologyCollectionReportRead(
            report_type="referral_wise" if group_by == "referral" else "normal",
            from_date=from_date,
            to_date=to_date,
            groups=groups,
            overall_total_amount=overall_total,
        )

    async def build_column_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
    ) -> PathologyCollectionColumnReportRead:
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        service_columns = await self._column_services()
        if not service_columns:
            return PathologyCollectionColumnReportRead(
                report_type="column_wise",
                from_date=from_date,
                to_date=to_date,
                service_columns=[],
                groups=[],
                overall_column_totals={},
                overall_total_amount=Decimal("0"),
            )

        service_ids = {str(col.service_id) for col in service_columns}
        raw_rows = await self._fetch_column_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=service_ids,
        )

        doctor_name_map = await self._doctor_names({row[0] for row in raw_rows if row[0]})

        bill_buckets: dict[str, dict[tuple[date, str], dict[str, object]]] = defaultdict(dict)

        for (
            doctor_id,
            patient_name,
            bill_date,
            bill_no,
            patient_no,
            payment_mode,
            service_id,
            amount,
        ) in raw_rows:
            if not doctor_id or not service_id:
                continue
            service_id = str(service_id)
            if service_id not in service_ids:
                continue
            key = (bill_date, bill_no)
            bucket = bill_buckets[doctor_id].get(key)
            if bucket is None:
                bucket = {
                    "bill_date": bill_date,
                    "bill_no": bill_no,
                    "patient_no": patient_no,
                    "patient_name": patient_name,
                    "payment_mode": payment_mode,
                    "amounts": {},
                }
                bill_buckets[doctor_id][key] = bucket
            amounts: dict[str, Decimal] = bucket["amounts"]  # type: ignore[assignment]
            amounts[service_id] = amounts.get(service_id, Decimal("0")) + amount

        groups: list[PathologyCollectionColumnGroup] = []
        overall_column_totals: dict[str, Decimal] = {
            col.service_id: Decimal("0") for col in service_columns
        }
        overall_total = Decimal("0")

        for doctor_id in sorted(
            bill_buckets.keys(),
            key=lambda value: doctor_name_map.get(value, value).casefold(),
        ):
            rows: list[PathologyCollectionColumnRow] = []
            column_totals: dict[str, Decimal] = {
                col.service_id: Decimal("0") for col in service_columns
            }
            group_total = Decimal("0")

            for key in sorted(bill_buckets[doctor_id].keys()):
                bucket = bill_buckets[doctor_id][key]
                amounts_raw: dict[str, Decimal] = bucket["amounts"]  # type: ignore[assignment]
                amounts = {
                    col.service_id: Decimal(str(amounts_raw.get(col.service_id, 0) or 0))
                    for col in service_columns
                }
                row_total = sum(amounts.values(), Decimal("0"))
                if row_total <= 0:
                    continue
                rows.append(
                    PathologyCollectionColumnRow(
                        bill_date=bucket["bill_date"],  # type: ignore[arg-type]
                        bill_no=str(bucket["bill_no"]),
                        patient_no=str(bucket["patient_no"]),
                        patient_name=str(bucket["patient_name"] or "—"),
                        payment_mode=str(bucket.get("payment_mode") or "—"),
                        amounts=amounts,
                        total_amount=row_total,
                    )
                )
                group_total += row_total
                for service_id, value in amounts.items():
                    column_totals[service_id] = column_totals.get(service_id, Decimal("0")) + value

            if not rows:
                continue

            groups.append(
                PathologyCollectionColumnGroup(
                    group_key=doctor_id,
                    group_name=doctor_name_map.get(doctor_id, doctor_id),
                    rows=rows,
                    column_totals=column_totals,
                    grand_total_amount=group_total,
                )
            )
            overall_total += group_total
            for service_id, value in column_totals.items():
                overall_column_totals[service_id] = (
                    overall_column_totals.get(service_id, Decimal("0")) + value
                )

        return PathologyCollectionColumnReportRead(
            report_type="column_wise",
            from_date=from_date,
            to_date=to_date,
            service_columns=service_columns,
            groups=groups,
            overall_column_totals=overall_column_totals,
            overall_total_amount=overall_total,
        )

    async def list_referring_doctors(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[str]:
        stmt = (
            select(PathologyBill.referring_doctor)
            .where(
                PathologyBill.is_active.is_(True),
                PathologyBill.status != "cancelled",
                PathologyBill.referring_doctor.is_not(None),
                PathologyBill.referring_doctor != "",
            )
            .distinct()
            .order_by(PathologyBill.referring_doctor)
        )
        if from_date is not None:
            stmt = stmt.where(PathologyBill.bill_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(PathologyBill.bill_date <= to_date)
        result = await self.session.execute(stmt)
        names: list[str] = []
        seen: set[str] = set()
        for value in result.scalars().all():
            name = self._normalize_referral(value)
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
        return names

    async def _column_services(self) -> list[PathologyCollectionServiceColumn]:
        result = await self.session.execute(
            select(PatientServiceMaster)
            .where(
                PatientServiceMaster.is_active.is_(True),
                PatientServiceMaster.show_in_doctor_collection.is_(True),
            )
            .order_by(PatientServiceMaster.code)
        )
        items = list(result.scalars().all())
        name_counts: dict[str, int] = defaultdict(int)
        for item in items:
            name_counts[item.name.casefold()] += 1
        return [
            PathologyCollectionServiceColumn(
                service_id=str(item.id),
                service_name=(
                    f"{item.name} ({item.code})"
                    if name_counts[item.name.casefold()] > 1
                    else item.name
                ),
            )
            for item in items
        ]

    async def _fetch_referral_bill_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        referral_names: list[str] | None,
    ) -> list[
        tuple[
            str | None,
            str,
            date,
            str,
            str,
            str,
            str | None,
            Decimal,
        ]
    ]:
        """One tuple per bill: doctor_id, patient_name, bill_date, bill_no, patient_no,
        payment_mode, referring_doctor, net_amount."""
        stmt = (
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.payment_mode),
            )
            .where(
                PathologyBill.is_active.is_(True),
                PathologyBill.status != "cancelled",
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
                PathologyBill.referring_doctor.is_not(None),
                PathologyBill.referring_doctor != "",
            )
        )
        result = await self.session.execute(stmt)
        referral_filter = None
        if referral_names:
            referral_filter = {
                name.strip().casefold() for name in referral_names if name and name.strip()
            }

        raw_rows: list[
            tuple[str | None, str, date, str, str, str, str | None, Decimal]
        ] = []
        for bill in result.scalars().all():
            referral = self._normalize_referral(bill.referring_doctor)
            if not referral:
                continue
            if referral_filter is not None and referral.casefold() not in referral_filter:
                continue
            amount = Decimal(str(bill.net_amount or 0))
            if amount < 0:
                amount = Decimal("0")
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    referral,
                    amount,
                )
            )
        return raw_rows

    async def _fetch_detail_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
        referral_names: list[str] | None,
        require_referral: bool,
    ) -> list[
        tuple[
            str | None,
            str,
            date,
            str,
            str,
            str,
            str | None,
            str,
            Decimal,
            Decimal,
        ]
    ]:
        """Tuple: doctor_id, patient_name, bill_date, bill_no, patient_no, payment_mode,
        referring_doctor, service_name, rate, amount."""
        stmt = (
            select(PathologyBillLine, PathologyBill)
            .join(PathologyBill, PathologyBill.id == PathologyBillLine.bill_id)
            .options(
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.payment_mode),
            )
            .where(
                PathologyBillLine.is_active.is_(True),
                PathologyBill.is_active.is_(True),
                PathologyBill.status != "cancelled",
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
            )
        )
        if doctor_ids:
            stmt = stmt.where(PathologyBill.doctor_id.in_(doctor_ids))
        if require_referral:
            stmt = stmt.where(
                PathologyBill.referring_doctor.is_not(None),
                PathologyBill.referring_doctor != "",
            )

        result = await self.session.execute(stmt)
        referral_filter = None
        if referral_names:
            referral_filter = {
                name.strip().casefold() for name in referral_names if name and name.strip()
            }

        raw_rows: list[
            tuple[
                str | None,
                str,
                date,
                str,
                str,
                str,
                str | None,
                str,
                Decimal,
                Decimal,
            ]
        ] = []
        for line, bill in result.all():
            referral = self._normalize_referral(bill.referring_doctor)
            if referral_filter is not None:
                if not referral or referral.casefold() not in referral_filter:
                    continue
            amount = self._line_amount(line)
            if amount <= 0:
                continue
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            rate = Decimal(str(line.rate or 0))
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    referral,
                    line.service_name or "—",
                    rate,
                    amount,
                )
            )
        return raw_rows

    async def _fetch_column_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
        service_ids: set[str],
    ) -> list[tuple[str, str, date, str, str, str, str, Decimal]]:
        """Tuple: doctor_id, patient_name, bill_date, bill_no, patient_no, payment_mode,
        service_id, amount."""
        doctor_filter = set(doctor_ids) if doctor_ids else None
        master_result = await self.session.execute(
            select(
                PatientServiceMaster.id,
                PatientServiceMaster.code,
                PatientServiceMaster.name,
            ).where(PatientServiceMaster.id.in_(list(service_ids)))
        )
        code_to_service_id: dict[str, str] = {}
        name_to_service_id: dict[str, str] = {}
        for service_id, code, name in master_result.all():
            sid = str(service_id)
            if code:
                code_to_service_id[str(code).strip().upper()] = sid
            if name:
                name_to_service_id.setdefault(str(name).casefold().strip(), sid)

        def resolve_service_id(
            line_service_id: object | None,
            line_service_code: str | None,
            line_service_name: str | None,
        ) -> str | None:
            if line_service_id is not None:
                sid = str(line_service_id)
                if sid in service_ids:
                    return sid
                return None
            if line_service_code:
                matched = code_to_service_id.get(str(line_service_code).strip().upper())
                if matched:
                    return matched
            if line_service_name:
                matched = name_to_service_id.get(str(line_service_name).casefold().strip())
                if matched:
                    return matched
            return None

        stmt = (
            select(PathologyBillLine, PathologyBill)
            .join(PathologyBill, PathologyBill.id == PathologyBillLine.bill_id)
            .options(
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.payment_mode),
            )
            .where(
                PathologyBillLine.is_active.is_(True),
                PathologyBill.is_active.is_(True),
                PathologyBill.status != "cancelled",
                PathologyBill.doctor_id.is_not(None),
                PathologyBill.bill_date >= from_date,
                PathologyBill.bill_date <= to_date,
            )
        )
        if doctor_filter is not None:
            stmt = stmt.where(PathologyBill.doctor_id.in_(list(doctor_filter)))

        result = await self.session.execute(stmt)
        raw_rows: list[tuple[str, str, date, str, str, str, str, Decimal]] = []
        for line, bill in result.all():
            if not bill.doctor_id:
                continue
            doctor_id = str(bill.doctor_id)
            if doctor_filter is not None and doctor_id not in doctor_filter:
                continue
            service_id = resolve_service_id(line.service_id, line.service_code, line.service_name)
            if not service_id:
                continue
            amount = self._line_amount(line)
            if amount <= 0:
                continue
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    doctor_id,
                    patient_name,
                    bill.bill_date,
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    service_id,
                    amount,
                )
            )
        return raw_rows

    async def _doctor_names(self, doctor_ids: set[str]) -> dict[str, str]:
        if not doctor_ids:
            return {}
        result = await self.session.execute(
            select(Doctor).where(Doctor.id.in_(list(doctor_ids)), Doctor.is_active.is_(True))
        )
        return {doctor.id: doctor.full_name for doctor in result.scalars().all()}
