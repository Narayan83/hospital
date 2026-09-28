from decimal import Decimal

from fastapi import HTTPException, status

from app.models.patient_service_master import PatientServiceMaster


def billing_rate_for_service_master(service: PatientServiceMaster) -> Decimal:
    """Return the patient billing rate for a service master row."""
    if service.is_sharing:
        return Decimal(str(service.rate or 0))
    if service.service_charge and service.service_charge > 0:
        return Decimal(str(service.service_charge))
    return Decimal(str(service.rate or 0))


def default_sharing_split(total: Decimal, doctor_percent: Decimal) -> tuple[Decimal, Decimal]:
    percent = max(Decimal("0"), min(doctor_percent, Decimal("100")))
    doctor_amount = (total * percent / Decimal("100")).quantize(Decimal("0.01"))
    hospital_amount = total - doctor_amount
    return hospital_amount, doctor_amount


def resolve_line_sharing_fields(
    service: PatientServiceMaster,
    *,
    rate: Decimal,
    amount: Decimal,
    hospital_amount: Decimal | None,
    doctor_amount: Decimal | None,
    original_rate: Decimal | None,
    sharing_doctor_id: str | None,
) -> tuple[Decimal | None, Decimal, Decimal, str | None]:
    if not service.is_sharing:
        # Persist the billed amount as hospital collection so doctor-wise /
        # date reports see the line immediately after save (print is not required).
        billed = Decimal(str(amount or 0))
        return None, billed, Decimal("0"), None

    master_original = Decimal(str(service.rate or rate))
    resolved_original = original_rate if original_rate is not None else master_original
    resolved_doctor_id = sharing_doctor_id or service.doctor_id

    if hospital_amount is not None and doctor_amount is not None:
        if hospital_amount < 0 or doctor_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sharing amounts cannot be negative for service {service.name}",
            )
        if hospital_amount + doctor_amount != amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Hospital and doctor amounts must total {amount} for service {service.name}"
                ),
            )
        return resolved_original, hospital_amount, doctor_amount, resolved_doctor_id

    percent = Decimal(str(service.service_charge or 0))
    hospital, doctor = default_sharing_split(amount, percent)
    return resolved_original, hospital, doctor, resolved_doctor_id
