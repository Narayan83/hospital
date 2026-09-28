from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.ipd_bill import IpdBill, IpdBillLine, IpdBillPayment
from app.models.opd_bill import OpdBill, OpdBillLine, OpdBillPayment
from app.models.patient_service_master import PatientServiceMaster
from app.models.single_service_opd import SingleServiceOpdBill
from app.schemas.doctor_collection_report import (
    DoctorCollectionColumnDoctorGroup,
    DoctorCollectionColumnReportRead,
    DoctorCollectionColumnRow,
    DoctorCollectionDateGroup,
    DoctorCollectionDateServiceGroup,
    DoctorCollectionDateServiceReportRead,
    DoctorCollectionDateServiceRow,
    DoctorCollectionDetailRow,
    DoctorCollectionDoctorGroup,
    DoctorCollectionPaymentModeDoctorRow,
    DoctorCollectionPaymentModeGroup,
    DoctorCollectionPaymentModeReportRead,
    DoctorCollectionReportRead,
    DoctorCollectionServiceColumn,
    DoctorCollectionServiceSummaryRow,
)


class DoctorCollectionReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _payment_mode_label(bill: OpdBill | IpdBill) -> str:
        """Unique payment mode names for a bill, comma-separated when split."""
        names: list[str] = []
        seen: set[str] = set()
        payments = [
            payment
            for payment in (getattr(bill, "payments", None) or [])
            if getattr(payment, "is_active", True)
        ]
        payments.sort(key=lambda payment: getattr(payment, "sort_order", 0) or 0)
        for payment in payments:
            mode = getattr(payment, "payment_mode", None)
            name = (getattr(mode, "name", None) or "").strip()
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                names.append(name)
        if names:
            return ", ".join(names)
        mode = getattr(bill, "payment_mode", None)
        name = (getattr(mode, "name", None) or "").strip()
        return name or "—"

    async def build_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        report_type: str = "sharing",
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
    ) -> (
        DoctorCollectionReportRead
        | DoctorCollectionColumnReportRead
        | DoctorCollectionPaymentModeReportRead
        | DoctorCollectionDateServiceReportRead
    ):
        normalized = (report_type or "sharing").strip().lower()
        if normalized == "normal":
            normalized = "sharing"
        if normalized == "column_wise":
            return await self.build_column_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                payment_modes=payment_modes,
            )
        if normalized == "payment_mode_summary":
            return await self.build_payment_mode_summary(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                payment_modes=payment_modes,
            )
        if normalized == "day_wise_summary":
            return await self.build_day_wise_summary(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                payment_modes=payment_modes,
            )
        if normalized == "date_service_summary":
            return await self.build_date_service_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                payment_modes=payment_modes,
                include_detail_rows=False,
            )
        if normalized == "date_service_details":
            return await self.build_date_service_report(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                payment_modes=payment_modes,
                include_detail_rows=True,
            )
        return await self.build_normal_report(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=service_ids,
            payment_modes=payment_modes,
            report_type_label="sharing",
        )

    @staticmethod
    def _payment_mode_filter_set(payment_modes: list[str] | None) -> set[str] | None:
        if not payment_modes:
            return None
        cleaned = {str(mode).strip().casefold() for mode in payment_modes if str(mode).strip()}
        return cleaned or None

    @classmethod
    def _payment_mode_matches(cls, label: str, allowed: set[str] | None) -> bool:
        if allowed is None:
            return True
        parts = [part.strip().casefold() for part in (label or "").split(",") if part.strip()]
        if not parts:
            return "—" in allowed or "-" in allowed
        return any(part in allowed for part in parts)

    @staticmethod
    def _split_line_amounts(line) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Hospital/doctor split for a bill line.

        Saved OPD/IPD lines without a sharing split store hospital/doctor as 0.
        Treat the billed line amount (or rate × qty) as hospital collection so
        the bill appears in reports immediately after save, not only after print.
        """
        original = Decimal(
            str(line.original_rate if line.original_rate is not None else getattr(line, "rate", 0) or 0)
        )
        hospital = Decimal(str(getattr(line, "hospital_amount", None) or 0))
        doctor = Decimal(str(getattr(line, "doctor_amount", None) or 0))
        amount = Decimal(str(getattr(line, "amount", None) or 0))
        if hospital + doctor <= 0:
            if amount > 0:
                hospital = amount
                doctor = Decimal("0")
            else:
                qty = Decimal(str(getattr(line, "quantity", None) or 1))
                rate = Decimal(str(getattr(line, "rate", None) or 0))
                hospital = rate * qty
                doctor = Decimal("0")
        return original, hospital, doctor, hospital + doctor

    @staticmethod
    def _bill_doctor_clause(bill_doctor_col, doctor_ids: list[str] | None):
        clause = bill_doctor_col.is_not(None)
        if doctor_ids:
            clause = clause & bill_doctor_col.in_(list(doctor_ids))
        return clause

    async def _resolve_service_name_matches(
        self, service_ids: list[str] | None
    ) -> tuple[set[str] | None, set[str] | None]:
        if not service_ids:
            return None, None
        id_set = {str(sid) for sid in service_ids if sid}
        if not id_set:
            return None, None
        result = await self.session.execute(
            select(PatientServiceMaster.name).where(PatientServiceMaster.id.in_(list(id_set)))
        )
        names = {str(name).strip() for (name,) in result.all() if name and str(name).strip()}
        return id_set, names or None

    async def build_normal_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
        report_type_label: str = "sharing",
        include_detail_rows: bool = True,
        include_service_summary: bool = True,
    ) -> DoctorCollectionReportRead:
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        id_set, name_set = await self._resolve_service_name_matches(service_ids)
        mode_filter = self._payment_mode_filter_set(payment_modes)
        raw_rows = await self._fetch_sharing_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=id_set,
            match_service_names=name_set,
        )
        if mode_filter is not None:
            raw_rows = [
                row for row in raw_rows if self._payment_mode_matches(row[6], mode_filter)
            ]

        doctor_name_map = await self._doctor_names({row[0] for row in raw_rows if row[0]})

        grouped: dict[str, dict[date, list[DoctorCollectionDetailRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for (
            doctor_id,
            _patient_name,
            bill_date,
            bill_type,
            bill_no,
            patient_no,
            payment_mode,
            _service_id,
            service_name,
            original_rate,
            hospital_amount,
            doctor_amount,
            total_amount,
        ) in raw_rows:
            grouped[doctor_id][bill_date].append(
                DoctorCollectionDetailRow(
                    bill_date=bill_date,
                    bill_type=bill_type,
                    bill_no=bill_no,
                    patient_no=patient_no,
                    payment_mode=payment_mode,
                    service_name=service_name,
                    original_rate=original_rate,
                    hospital_amount=hospital_amount,
                    doctor_amount=doctor_amount,
                    total_amount=total_amount,
                )
            )

        doctor_groups: list[DoctorCollectionDoctorGroup] = []
        overall_total = Decimal("0")
        overall_hospital = Decimal("0")
        overall_doctor = Decimal("0")

        for doctor_id in sorted(
            grouped.keys(),
            key=lambda value: doctor_name_map.get(value, value).casefold(),
        ):
            date_groups: list[DoctorCollectionDateGroup] = []
            service_totals: dict[str, tuple[Decimal, Decimal, Decimal]] = defaultdict(
                lambda: (Decimal("0"), Decimal("0"), Decimal("0"))
            )
            doctor_total = Decimal("0")
            doctor_hospital = Decimal("0")
            doctor_doctor = Decimal("0")

            for bill_date in sorted(grouped[doctor_id].keys()):
                rows = sorted(
                    grouped[doctor_id][bill_date],
                    key=lambda row: (row.patient_no, row.service_name.casefold(), row.bill_no),
                )
                date_total = sum((row.total_amount for row in rows), Decimal("0"))
                date_hospital = sum((row.hospital_amount for row in rows), Decimal("0"))
                date_doctor = sum((row.doctor_amount for row in rows), Decimal("0"))
                date_groups.append(
                    DoctorCollectionDateGroup(
                        bill_date=bill_date,
                        rows=rows if include_detail_rows else [],
                        total_amount=date_total,
                        hospital_amount=date_hospital,
                        doctor_amount=date_doctor,
                    )
                )
                doctor_total += date_total
                doctor_hospital += date_hospital
                doctor_doctor += date_doctor
                if include_service_summary:
                    for row in rows:
                        prev = service_totals[row.service_name]
                        service_totals[row.service_name] = (
                            prev[0] + row.total_amount,
                            prev[1] + row.hospital_amount,
                            prev[2] + row.doctor_amount,
                        )

            service_summary = [
                DoctorCollectionServiceSummaryRow(
                    service_name=service_name,
                    total_amount=values[0],
                    hospital_amount=values[1],
                    doctor_amount=values[2],
                )
                for service_name, values in sorted(
                    service_totals.items(),
                    key=lambda item: item[0].casefold(),
                )
            ]

            doctor_groups.append(
                DoctorCollectionDoctorGroup(
                    doctor_id=doctor_id,
                    doctor_name=doctor_name_map.get(doctor_id, doctor_id),
                    date_groups=date_groups,
                    service_summary=service_summary,
                    grand_total_amount=doctor_total,
                    grand_hospital_amount=doctor_hospital,
                    grand_doctor_amount=doctor_doctor,
                )
            )
            overall_total += doctor_total
            overall_hospital += doctor_hospital
            overall_doctor += doctor_doctor

        return DoctorCollectionReportRead(
            report_type=report_type_label,  # type: ignore[arg-type]
            from_date=from_date,
            to_date=to_date,
            doctors=doctor_groups,
            overall_total_amount=overall_total,
            overall_hospital_amount=overall_hospital,
            overall_doctor_amount=overall_doctor,
        )

    async def build_day_wise_summary(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
    ) -> DoctorCollectionReportRead:
        return await self.build_normal_report(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=service_ids,
            payment_modes=payment_modes,
            report_type_label="day_wise_summary",
            include_detail_rows=False,
            include_service_summary=False,
        )

    async def build_date_service_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
        include_detail_rows: bool = False,
    ) -> DoctorCollectionDateServiceReportRead:
        """Group bill lines by date, then by selected service (summary or bill detail).

        Unlike sharing reports, this includes every bill line for the selected
        services — not only lines with doctor-sharing configured.
        """
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        id_set, name_set = await self._resolve_service_name_matches(service_ids)
        mode_filter = self._payment_mode_filter_set(payment_modes)
        raw_rows = await self._fetch_bill_service_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=id_set,
            match_service_names=name_set,
        )
        if mode_filter is not None:
            raw_rows = [
                row for row in raw_rows if self._payment_mode_matches(row[6], mode_filter)
            ]

        # date -> service_name -> detail rows
        grouped: dict[date, dict[str, list[DoctorCollectionDetailRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for (
            _doctor_id,
            _patient_name,
            bill_date,
            bill_type,
            bill_no,
            patient_no,
            payment_mode,
            _service_id,
            service_name,
            original_rate,
            hospital_amount,
            doctor_amount,
            total_amount,
        ) in raw_rows:
            name = (service_name or "").strip() or "—"
            grouped[bill_date][name].append(
                DoctorCollectionDetailRow(
                    bill_date=bill_date,
                    bill_type=bill_type,
                    bill_no=bill_no,
                    patient_no=patient_no,
                    payment_mode=payment_mode,
                    service_name=name,
                    original_rate=original_rate,
                    hospital_amount=hospital_amount,
                    doctor_amount=doctor_amount,
                    total_amount=total_amount,
                )
            )

        date_groups: list[DoctorCollectionDateServiceGroup] = []
        overall_total = Decimal("0")
        overall_hospital = Decimal("0")
        overall_doctor = Decimal("0")

        for bill_date in sorted(grouped.keys()):
            services: list[DoctorCollectionDateServiceRow] = []
            date_total = Decimal("0")
            date_hospital = Decimal("0")
            date_doctor = Decimal("0")
            for service_name in sorted(grouped[bill_date].keys(), key=str.casefold):
                rows = sorted(
                    grouped[bill_date][service_name],
                    key=lambda row: (row.patient_no, row.bill_no),
                )
                svc_total = sum((row.total_amount for row in rows), Decimal("0"))
                svc_hospital = sum((row.hospital_amount for row in rows), Decimal("0"))
                svc_doctor = sum((row.doctor_amount for row in rows), Decimal("0"))
                services.append(
                    DoctorCollectionDateServiceRow(
                        service_name=service_name,
                        rows=rows if include_detail_rows else [],
                        hospital_amount=svc_hospital,
                        doctor_amount=svc_doctor,
                        total_amount=svc_total,
                    )
                )
                date_total += svc_total
                date_hospital += svc_hospital
                date_doctor += svc_doctor
            date_groups.append(
                DoctorCollectionDateServiceGroup(
                    bill_date=bill_date,
                    services=services,
                    hospital_amount=date_hospital,
                    doctor_amount=date_doctor,
                    total_amount=date_total,
                )
            )
            overall_total += date_total
            overall_hospital += date_hospital
            overall_doctor += date_doctor

        return DoctorCollectionDateServiceReportRead(
            report_type=(
                "date_service_details" if include_detail_rows else "date_service_summary"
            ),
            from_date=from_date,
            to_date=to_date,
            date_groups=date_groups,
            overall_total_amount=overall_total,
            overall_hospital_amount=overall_hospital,
            overall_doctor_amount=overall_doctor,
        )

    async def build_payment_mode_summary(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
    ) -> DoctorCollectionPaymentModeReportRead:
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        id_set, name_set = await self._resolve_service_name_matches(service_ids)
        mode_filter = self._payment_mode_filter_set(payment_modes)
        raw_rows = await self._fetch_sharing_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=id_set,
            match_service_names=name_set,
        )
        if mode_filter is not None:
            raw_rows = [
                row for row in raw_rows if self._payment_mode_matches(row[6], mode_filter)
            ]

        doctor_name_map = await self._doctor_names({row[0] for row in raw_rows if row[0]})
        # payment_mode -> doctor_id -> totals
        buckets: dict[str, dict[str, list[Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: [Decimal("0"), Decimal("0"), Decimal("0")])
        )
        for (
            doctor_id,
            _patient_name,
            _bill_date,
            _bill_type,
            _bill_no,
            _patient_no,
            payment_mode,
            _service_id,
            _service_name,
            _original_rate,
            hospital_amount,
            doctor_amount,
            total_amount,
        ) in raw_rows:
            mode_key = (payment_mode or "—").strip() or "—"
            totals = buckets[mode_key][doctor_id]
            totals[0] += hospital_amount
            totals[1] += doctor_amount
            totals[2] += total_amount

        mode_groups: list[DoctorCollectionPaymentModeGroup] = []
        overall_total = Decimal("0")
        overall_hospital = Decimal("0")
        overall_doctor = Decimal("0")

        for mode_name in sorted(buckets.keys(), key=lambda value: value.casefold()):
            doctor_rows: list[DoctorCollectionPaymentModeDoctorRow] = []
            mode_hospital = Decimal("0")
            mode_doctor = Decimal("0")
            mode_total = Decimal("0")
            for doctor_id in sorted(
                buckets[mode_name].keys(),
                key=lambda value: doctor_name_map.get(value, value).casefold(),
            ):
                hospital_amount, doctor_amount, total_amount = buckets[mode_name][doctor_id]
                doctor_rows.append(
                    DoctorCollectionPaymentModeDoctorRow(
                        doctor_id=doctor_id,
                        doctor_name=doctor_name_map.get(doctor_id, doctor_id),
                        hospital_amount=hospital_amount,
                        doctor_amount=doctor_amount,
                        total_amount=total_amount,
                    )
                )
                mode_hospital += hospital_amount
                mode_doctor += doctor_amount
                mode_total += total_amount
            mode_groups.append(
                DoctorCollectionPaymentModeGroup(
                    payment_mode=mode_name,
                    doctors=doctor_rows,
                    hospital_amount=mode_hospital,
                    doctor_amount=mode_doctor,
                    total_amount=mode_total,
                )
            )
            overall_hospital += mode_hospital
            overall_doctor += mode_doctor
            overall_total += mode_total

        return DoctorCollectionPaymentModeReportRead(
            report_type="payment_mode_summary",
            from_date=from_date,
            to_date=to_date,
            payment_modes=mode_groups,
            overall_total_amount=overall_total,
            overall_hospital_amount=overall_hospital,
            overall_doctor_amount=overall_doctor,
        )

    async def build_column_report(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        payment_modes: list[str] | None = None,
    ) -> DoctorCollectionColumnReportRead:
        """Ledger: Name + each mapped service as its own amount column.

        Services appear side-by-side (Consultation | Suture | OT | …).
        Each bill is one row; amounts sit only in the matching service column.
        Same bill with multiple mapped services fills multiple columns on that row.
        """
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        service_columns = await self._column_services()
        if not service_columns:
            return DoctorCollectionColumnReportRead(
                report_type="column_wise",
                from_date=from_date,
                to_date=to_date,
                service_columns=[],
                doctors=[],
                overall_column_totals={},
                overall_total_amount=Decimal("0"),
            )

        service_ids = {str(col.service_id) for col in service_columns}
        mode_filter = self._payment_mode_filter_set(payment_modes)
        raw_rows = await self._fetch_column_rows(
            from_date=from_date,
            to_date=to_date,
            doctor_ids=doctor_ids,
            service_ids=service_ids,
        )
        if mode_filter is not None:
            raw_rows = [
                row for row in raw_rows if self._payment_mode_matches(row[6], mode_filter)
            ]

        doctor_name_map = await self._doctor_names({row[0] for row in raw_rows if row[0]})

        # doctor_id -> (bill_date, bill_type, bill_no) -> pivot row
        bill_buckets: dict[str, dict[tuple[date, str, str], dict[str, object]]] = defaultdict(
            dict
        )

        for (
            doctor_id,
            patient_name,
            bill_date,
            bill_type,
            bill_no,
            patient_no,
            payment_mode,
            service_id,
            total_amount,
        ) in raw_rows:
            if not service_id:
                continue
            service_id = str(service_id)
            if service_id not in service_ids:
                continue
            key = (bill_date, bill_type, bill_no)
            bucket = bill_buckets[doctor_id].get(key)
            if bucket is None:
                bucket = {
                    "bill_date": bill_date,
                    "bill_type": bill_type,
                    "bill_no": bill_no,
                    "patient_no": patient_no,
                    "patient_name": patient_name,
                    "payment_mode": payment_mode,
                    "amounts": {},
                }
                bill_buckets[doctor_id][key] = bucket
            amounts: dict[str, Decimal] = bucket["amounts"]  # type: ignore[assignment]
            amounts[service_id] = amounts.get(service_id, Decimal("0")) + total_amount

        doctor_groups: list[DoctorCollectionColumnDoctorGroup] = []
        overall_column_totals: dict[str, Decimal] = {
            col.service_id: Decimal("0") for col in service_columns
        }
        overall_total = Decimal("0")

        for doctor_id in sorted(
            bill_buckets.keys(),
            key=lambda value: doctor_name_map.get(value, value).casefold(),
        ):
            rows: list[DoctorCollectionColumnRow] = []
            column_totals: dict[str, Decimal] = {
                col.service_id: Decimal("0") for col in service_columns
            }
            doctor_total = Decimal("0")

            for key in sorted(bill_buckets[doctor_id].keys()):
                bucket = bill_buckets[doctor_id][key]
                amounts_raw: dict[str, Decimal] = bucket["amounts"]  # type: ignore[assignment]
                # Only fill columns that have an amount; others stay blank (0 → UI hides).
                amounts = {
                    col.service_id: Decimal(str(amounts_raw.get(col.service_id, 0) or 0))
                    for col in service_columns
                }
                row_total = sum(amounts.values(), Decimal("0"))
                if row_total <= 0:
                    continue
                rows.append(
                    DoctorCollectionColumnRow(
                        bill_date=bucket["bill_date"],  # type: ignore[arg-type]
                        bill_type=str(bucket["bill_type"]),
                        bill_no=str(bucket["bill_no"]),
                        patient_no=str(bucket["patient_no"]),
                        patient_name=str(bucket["patient_name"] or "—"),
                        payment_mode=str(bucket.get("payment_mode") or "—"),
                        amounts=amounts,
                        total_amount=row_total,
                    )
                )
                doctor_total += row_total
                for service_id, value in amounts.items():
                    column_totals[service_id] = column_totals.get(service_id, Decimal("0")) + value

            if not rows:
                continue

            doctor_groups.append(
                DoctorCollectionColumnDoctorGroup(
                    doctor_id=doctor_id,
                    doctor_name=doctor_name_map.get(doctor_id, doctor_id),
                    rows=rows,
                    column_totals=column_totals,
                    grand_total_amount=doctor_total,
                )
            )
            overall_total += doctor_total
            for service_id, value in column_totals.items():
                overall_column_totals[service_id] = (
                    overall_column_totals.get(service_id, Decimal("0")) + value
                )

        return DoctorCollectionColumnReportRead(
            report_type="column_wise",
            from_date=from_date,
            to_date=to_date,
            service_columns=service_columns,
            doctors=doctor_groups,
            overall_column_totals=overall_column_totals,
            overall_total_amount=overall_total,
        )

    async def _column_services(self) -> list[DoctorCollectionServiceColumn]:
        result = await self.session.execute(
            select(PatientServiceMaster)
            .where(
                PatientServiceMaster.is_active.is_(True),
                PatientServiceMaster.show_in_doctor_collection.is_(True),
            )
            .order_by(PatientServiceMaster.code)
        )
        items = list(result.scalars().all())
        # Disambiguate duplicate names (e.g. two CONSULTATION masters).
        name_counts: dict[str, int] = defaultdict(int)
        for item in items:
            name_counts[item.name.casefold()] += 1
        return [
            DoctorCollectionServiceColumn(
                service_id=str(item.id),
                service_name=(
                    f"{item.name} ({item.code})"
                    if name_counts[item.name.casefold()] > 1
                    else item.name
                ),
            )
            for item in items
        ]

    async def _fetch_column_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
        service_ids: set[str],
    ) -> list[tuple[str, str, date, str, str, str, str, str, Decimal]]:
        """Rows for column-wise ledger report.

        Tuple: doctor_id, patient_name, bill_date, bill_type, bill_no, patient_no,
        payment_mode, service_id, collection_amount

        Fetches all bill lines for doctor bills in range, then maps each line to a
        Doctor-Collection-Column service by id / code / name in Python (avoids
        missing services when SQL id filters don't match stored line values).
        """
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

        raw_rows: list[tuple[str, str, date, str, str, str, str, str, Decimal]] = []

        def resolve_service_id(
            line_service_id: object | None,
            line_service_code: str | None,
            line_service_name: str | None,
        ) -> str | None:
            # Prefer exact mapped id. If the line points at a *different* master
            # (e.g. PS255 CONSULTATION while only PS252 is mapped), do NOT fall
            # back to name — that wrongly dumps amounts into another column.
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

        def line_amount(line) -> Decimal:
            amount = Decimal(str(getattr(line, "amount", None) or 0))
            if amount > 0:
                return amount
            # Fallback if amount was left 0 but split/rate exists
            hospital = Decimal(str(getattr(line, "hospital_amount", None) or 0))
            doctor = Decimal(str(getattr(line, "doctor_amount", None) or 0))
            split = hospital + doctor
            if split > 0:
                return split
            rate = Decimal(str(getattr(line, "rate", None) or 0))
            qty = Decimal(str(getattr(line, "quantity", None) or 1))
            return rate * qty

        def resolve_doctor(*, bill_doctor_id: object | None) -> str | None:
            if not bill_doctor_id:
                return None
            doctor_id = str(bill_doctor_id)
            if doctor_filter is not None and doctor_id not in doctor_filter:
                return None
            return doctor_id

        # No service filter in SQL — classify in Python so every mapped service can match.
        opd_stmt = (
            select(OpdBillLine, OpdBill)
            .join(OpdBill, OpdBill.id == OpdBillLine.bill_id)
            .options(
                selectinload(OpdBill.patient),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments).selectinload(OpdBillPayment.payment_mode),
            )
            .where(
                OpdBillLine.is_active.is_(True),
                OpdBill.is_active.is_(True),
                self._bill_doctor_clause(OpdBill.doctor_id, doctor_ids),
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
        )
        opd_result = await self.session.execute(opd_stmt)
        for line, bill in opd_result.all():
            service_id = resolve_service_id(line.service_id, line.service_code, line.service_name)
            if not service_id:
                continue
            doctor_id = resolve_doctor(bill_doctor_id=bill.doctor_id)
            if not doctor_id:
                continue
            amount = line_amount(line)
            if amount <= 0:
                continue
            patient_no = bill.patient_no or (bill.patient.patient_no if bill.patient else "—")
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    doctor_id,
                    patient_name,
                    bill.bill_date,
                    "OPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    service_id,
                    amount,
                )
            )

        ipd_stmt = (
            select(IpdBillLine, IpdBill)
            .join(IpdBill, IpdBill.id == IpdBillLine.bill_id)
            .options(
                selectinload(IpdBill.patient),
                selectinload(IpdBill.payment_mode),
                selectinload(IpdBill.payments).selectinload(IpdBillPayment.payment_mode),
            )
            .where(
                IpdBillLine.is_active.is_(True),
                IpdBill.is_active.is_(True),
                self._bill_doctor_clause(IpdBill.doctor_id, doctor_ids),
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
        )
        ipd_result = await self.session.execute(ipd_stmt)
        for line, bill in ipd_result.all():
            service_id = resolve_service_id(line.service_id, line.service_code, line.service_name)
            if not service_id:
                continue
            doctor_id = resolve_doctor(bill_doctor_id=bill.doctor_id)
            if not doctor_id:
                continue
            amount = line_amount(line)
            if amount <= 0:
                continue
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    doctor_id,
                    patient_name,
                    bill.bill_date,
                    "IPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    service_id,
                    amount,
                )
            )

        raw_rows.extend(
            await self._single_service_column_rows(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
            )
        )
        return raw_rows

    async def _fetch_sharing_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: set[str] | None = None,
        match_service_names: set[str] | None = None,
    ) -> list[
        tuple[
            str,
            str,
            date,
            str,
            str,
            str,
            str,
            str | None,
            str,
            Decimal,
            Decimal,
            Decimal,
            Decimal,
        ]
    ]:
        """Return OPD/IPD bill lines for doctor collection reports.

        Tuple layout:
        doctor_id, patient_name, bill_date, bill_type, bill_no, patient_no, payment_mode,
        service_id, service_name, original_rate, hospital_amount, doctor_amount, total_amount

        Includes every saved active bill line for the bill doctor (not only
        doctor-sharing splits), so collection is visible immediately after save.
        """
        raw_rows: list[
            tuple[
                str,
                str,
                date,
                str,
                str,
                str,
                str,
                str | None,
                str,
                Decimal,
                Decimal,
                Decimal,
                Decimal,
            ]
        ] = []

        opd_stmt = (
            select(OpdBillLine, OpdBill)
            .join(OpdBill, OpdBill.id == OpdBillLine.bill_id)
            .options(
                selectinload(OpdBill.patient),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments).selectinload(OpdBillPayment.payment_mode),
            )
            .where(
                OpdBillLine.is_active.is_(True),
                OpdBill.is_active.is_(True),
                self._bill_doctor_clause(OpdBill.doctor_id, doctor_ids),
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
        )
        if service_ids:
            # Include by id, or by name when line has no service_id.
            conditions = [OpdBillLine.service_id.in_(list(service_ids))]
            if match_service_names:
                conditions.append(
                    OpdBillLine.service_id.is_(None)
                    & OpdBillLine.service_name.in_(list(match_service_names))
                )
            opd_stmt = opd_stmt.where(or_(*conditions))

        opd_result = await self.session.execute(opd_stmt)
        for line, bill in opd_result.all():
            if not bill.doctor_id:
                continue
            original, hospital, doctor, total = self._split_line_amounts(line)
            if total <= 0:
                continue
            patient_no = bill.patient_no or (bill.patient.patient_no if bill.patient else "—")
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    "OPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    line.service_id,
                    line.service_name,
                    original,
                    hospital,
                    doctor,
                    total,
                )
            )

        ipd_stmt = (
            select(IpdBillLine, IpdBill)
            .join(IpdBill, IpdBill.id == IpdBillLine.bill_id)
            .options(
                selectinload(IpdBill.patient),
                selectinload(IpdBill.payment_mode),
                selectinload(IpdBill.payments).selectinload(IpdBillPayment.payment_mode),
            )
            .where(
                IpdBillLine.is_active.is_(True),
                IpdBill.is_active.is_(True),
                self._bill_doctor_clause(IpdBill.doctor_id, doctor_ids),
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
        )
        if service_ids:
            conditions = [IpdBillLine.service_id.in_(list(service_ids))]
            if match_service_names:
                conditions.append(
                    IpdBillLine.service_id.is_(None)
                    & IpdBillLine.service_name.in_(list(match_service_names))
                )
            ipd_stmt = ipd_stmt.where(or_(*conditions))

        ipd_result = await self.session.execute(ipd_stmt)
        for line, bill in ipd_result.all():
            if not bill.doctor_id:
                continue
            original, hospital, doctor, total = self._split_line_amounts(line)
            if total <= 0:
                continue
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    "IPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    line.service_id,
                    line.service_name,
                    original,
                    hospital,
                    doctor,
                    total,
                )
            )

        raw_rows.extend(
            await self._single_service_sharing_rows(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                match_service_names=match_service_names,
            )
        )
        return raw_rows

    async def _fetch_bill_service_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None = None,
        service_ids: set[str] | None = None,
        match_service_names: set[str] | None = None,
    ) -> list[
        tuple[
            str,
            str,
            date,
            str,
            str,
            str,
            str,
            str | None,
            str,
            Decimal,
            Decimal,
            Decimal,
            Decimal,
        ]
    ]:
        """All bill lines for date/service reports (not limited to doctor-sharing).

        Same tuple layout as `_fetch_sharing_rows`.
        When a line has no hospital/doctor split, the line amount is treated as hospital.
        """
        raw_rows: list[
            tuple[
                str,
                str,
                date,
                str,
                str,
                str,
                str,
                str | None,
                str,
                Decimal,
                Decimal,
                Decimal,
                Decimal,
            ]
        ] = []

        # Resolve selected masters so lines can also match by code / name.
        code_set: set[str] = set()
        name_set = {n.casefold().strip() for n in (match_service_names or set()) if n}
        if service_ids:
            master_result = await self.session.execute(
                select(
                    PatientServiceMaster.id,
                    PatientServiceMaster.code,
                    PatientServiceMaster.name,
                ).where(PatientServiceMaster.id.in_(list(service_ids)))
            )
            for _sid, code, name in master_result.all():
                if code:
                    code_set.add(str(code).strip().upper())
                if name:
                    name_set.add(str(name).casefold().strip())

        def line_matches(line) -> bool:
            if service_ids is None:
                return True
            if line.service_id and str(line.service_id) in service_ids:
                return True
            code = (getattr(line, "service_code", None) or "").strip().upper()
            if code and code in code_set:
                return True
            name = (getattr(line, "service_name", None) or "").casefold().strip()
            if name and name in name_set:
                return True
            return False

        opd_stmt = (
            select(OpdBillLine, OpdBill)
            .join(OpdBill, OpdBill.id == OpdBillLine.bill_id)
            .options(
                selectinload(OpdBill.patient),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments).selectinload(OpdBillPayment.payment_mode),
            )
            .where(
                OpdBillLine.is_active.is_(True),
                OpdBill.is_active.is_(True),
                self._bill_doctor_clause(OpdBill.doctor_id, doctor_ids),
                OpdBill.bill_date >= from_date,
                OpdBill.bill_date <= to_date,
            )
        )

        opd_result = await self.session.execute(opd_stmt)
        for line, bill in opd_result.all():
            if not bill.doctor_id or not line_matches(line):
                continue
            original, hospital, doctor, total = self._split_line_amounts(line)
            if total <= 0:
                continue
            patient_no = bill.patient_no or (bill.patient.patient_no if bill.patient else "—")
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    "OPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    line.service_id,
                    line.service_name,
                    original,
                    hospital,
                    doctor,
                    total,
                )
            )

        ipd_stmt = (
            select(IpdBillLine, IpdBill)
            .join(IpdBill, IpdBill.id == IpdBillLine.bill_id)
            .options(
                selectinload(IpdBill.patient),
                selectinload(IpdBill.payment_mode),
                selectinload(IpdBill.payments).selectinload(IpdBillPayment.payment_mode),
            )
            .where(
                IpdBillLine.is_active.is_(True),
                IpdBill.is_active.is_(True),
                self._bill_doctor_clause(IpdBill.doctor_id, doctor_ids),
                IpdBill.bill_date >= from_date,
                IpdBill.bill_date <= to_date,
            )
        )

        ipd_result = await self.session.execute(ipd_stmt)
        for line, bill in ipd_result.all():
            if not bill.doctor_id or not line_matches(line):
                continue
            original, hospital, doctor, total = self._split_line_amounts(line)
            if total <= 0:
                continue
            patient_no = bill.patient.patient_no if bill.patient else "—"
            patient_name = bill.patient.full_name if bill.patient else "—"
            raw_rows.append(
                (
                    bill.doctor_id,
                    patient_name,
                    bill.bill_date,
                    "IPD",
                    bill.bill_no,
                    patient_no,
                    self._payment_mode_label(bill),
                    line.service_id,
                    line.service_name,
                    original,
                    hospital,
                    doctor,
                    total,
                )
            )

        raw_rows.extend(
            await self._single_service_sharing_rows(
                from_date=from_date,
                to_date=to_date,
                doctor_ids=doctor_ids,
                service_ids=service_ids,
                match_service_names=match_service_names,
            )
        )
        return raw_rows

    async def _load_single_service_bills(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
    ) -> list[SingleServiceOpdBill]:
        stmt = (
            select(SingleServiceOpdBill)
            .options(
                selectinload(SingleServiceOpdBill.option),
                selectinload(SingleServiceOpdBill.patient),
            )
            .where(
                SingleServiceOpdBill.is_active.is_(True),
                SingleServiceOpdBill.bill_date >= from_date,
                SingleServiceOpdBill.bill_date <= to_date,
                self._bill_doctor_clause(SingleServiceOpdBill.doctor_id, doctor_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _single_service_service_matches(
        bill: SingleServiceOpdBill,
        service_ids: set[str] | None,
        match_service_names: set[str] | None,
    ) -> bool:
        if service_ids is None:
            return True
        if bill.service_id and str(bill.service_id) in service_ids:
            return True
        if bill.service_id:
            return False
        if not match_service_names:
            return False
        name = (bill.service_name or "").casefold().strip()
        return name in {item.casefold().strip() for item in match_service_names if item}

    async def _single_service_column_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
        service_ids: set[str],
    ) -> list[tuple[str, str, date, str, str, str, str, str, Decimal]]:
        rows: list[tuple[str, str, date, str, str, str, str, str, Decimal]] = []
        for bill in await self._load_single_service_bills(
            from_date=from_date, to_date=to_date, doctor_ids=doctor_ids
        ):
            if not bill.service_id or str(bill.service_id) not in service_ids:
                continue
            amount = Decimal(str(bill.rate or 0))
            if amount <= 0 or not bill.doctor_id:
                continue
            patient_no = bill.patient_no or (bill.patient.patient_no if bill.patient else None) or "—"
            rows.append(
                (
                    bill.doctor_id,
                    bill.patient_name or "—",
                    bill.bill_date,
                    bill.option.name if bill.option else "OPD",
                    bill.bill_no,
                    patient_no,
                    bill.payment_mode_name or "Cash",
                    str(bill.service_id),
                    amount,
                )
            )
        return rows

    async def _single_service_sharing_rows(
        self,
        *,
        from_date: date,
        to_date: date,
        doctor_ids: list[str] | None,
        service_ids: set[str] | None,
        match_service_names: set[str] | None,
    ) -> list[
        tuple[
            str,
            str,
            date,
            str,
            str,
            str,
            str,
            str | None,
            str,
            Decimal,
            Decimal,
            Decimal,
            Decimal,
        ]
    ]:
        rows: list[
            tuple[
                str,
                str,
                date,
                str,
                str,
                str,
                str,
                str | None,
                str,
                Decimal,
                Decimal,
                Decimal,
                Decimal,
            ]
        ] = []
        for bill in await self._load_single_service_bills(
            from_date=from_date, to_date=to_date, doctor_ids=doctor_ids
        ):
            if not self._single_service_service_matches(bill, service_ids, match_service_names):
                continue
            amount = Decimal(str(bill.rate or 0))
            if amount <= 0 or not bill.doctor_id:
                continue
            patient_no = bill.patient_no or (bill.patient.patient_no if bill.patient else None) or "—"
            rows.append(
                (
                    bill.doctor_id,
                    bill.patient_name or "—",
                    bill.bill_date,
                    bill.option.name if bill.option else "OPD",
                    bill.bill_no,
                    patient_no,
                    bill.payment_mode_name or "Cash",
                    bill.service_id,
                    bill.service_name,
                    amount,
                    amount,
                    Decimal("0"),
                    amount,
                )
            )
        return rows

    async def _doctor_names(self, doctor_ids: set[str]) -> dict[str, str]:
        if not doctor_ids:
            return {}
        result = await self.session.execute(
            select(Doctor).where(Doctor.id.in_(doctor_ids))
        )
        return {doctor.id: doctor.full_name for doctor in result.scalars().all()}

    async def list_sharing_doctors(self) -> list[tuple[str, str]]:
        result = await self.session.execute(
            select(Doctor).where(Doctor.is_active.is_(True)).order_by(Doctor.doctor_code)
        )
        return [(doctor.id, doctor.full_name) for doctor in result.scalars().all()]
