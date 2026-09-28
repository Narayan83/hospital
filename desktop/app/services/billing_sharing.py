from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QWidget

from app.ui.components.doctor_sharing_split_dialog import ask_doctor_sharing_split


def is_sharing_service(service: dict) -> bool:
    value = service.get("is_sharing")
    if isinstance(value, str):
        return value.strip().upper() in {"Y", "YES", "TRUE", "1"}
    return bool(value)


def enrich_service_sharing(service: dict, *, patient_services: list[dict] | None = None) -> dict:
    """Merge latest sharing fields from patient service master cache/API source."""
    merged = dict(service)
    service_id = str(service.get("id") or "")
    if not service_id:
        return merged
    for svc in patient_services or []:
        if str(svc.get("id")) != service_id:
            continue
        merged["is_sharing"] = bool(svc.get("is_sharing"))
        merged["doctor_id"] = svc.get("doctor_id")
        merged["doctor_name"] = svc.get("doctor_name")
        merged["service_charge"] = svc.get("service_charge")
        break
    return merged


def build_bill_line_amounts(
    service: dict,
    *,
    rate: Decimal,
    qty: int,
    parent: QWidget | None = None,
    patient_services: list[dict] | None = None,
) -> dict | None:
    service = enrich_service_sharing(service, patient_services=patient_services)
    total = (rate * qty).quantize(Decimal("0.01"))
    if not is_sharing_service(service):
        return {
            "rate": float(rate),
            "quantity": qty,
            "amount": float(total),
        }

    try:
        doctor_percent = Decimal(str(service.get("service_charge") or 0))
    except Exception:
        doctor_percent = Decimal("0")

    split = ask_doctor_sharing_split(
        service_name=str(service.get("name") or "Service"),
        total_amount=total,
        doctor_percent=doctor_percent,
        doctor_name=service.get("doctor_name"),
        parent=parent,
    )
    if split is None:
        return None

    hospital = split["hospital_amount"]
    doctor = split["doctor_amount"]
    line_total = hospital + doctor
    effective_rate = line_total / qty if qty else line_total
    original_rate = rate.quantize(Decimal("0.01"))
    return {
        "rate": float(effective_rate),
        "quantity": qty,
        "amount": float(line_total),
        "original_rate": float(original_rate),
        "hospital_amount": float(hospital),
        "doctor_amount": float(doctor),
        "sharing_doctor_id": service.get("doctor_id"),
    }


def sharing_fields_for_payload(line: dict) -> dict:
    payload: dict = {}
    if line.get("sharing_doctor_id"):
        payload["sharing_doctor_id"] = line.get("sharing_doctor_id")
    if line.get("original_rate") is not None:
        payload["original_rate"] = str(line.get("original_rate"))
    if line.get("hospital_amount") is not None:
        payload["hospital_amount"] = str(line.get("hospital_amount"))
    if line.get("doctor_amount") is not None:
        payload["doctor_amount"] = str(line.get("doctor_amount"))
    return payload
