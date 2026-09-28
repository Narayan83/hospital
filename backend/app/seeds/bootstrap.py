from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.authority import Authority
from app.models.billing_structure import BillingStructureMapping
from app.models.billing_type import BillingType
from app.models.short_bill import ShortBillType
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.hospital_profile import HospitalProfile
from app.models.menu import Menu
from app.models.payment_mode import PaymentMode
from app.models.patient_no_format import PatientNoFormat
from app.models.prefix import Prefix
from app.models.procedure_type import ProcedureType
from app.models.service_category import ServiceCategory
from app.models.service_sub_category import ServiceSubCategory
from app.models.role import Role
from app.models.role_menu_permission import RoleMenuPermission
from app.models.user import User
from app.models.user_role_mapping import UserRoleMapping
from app.models.user_type import UserType
from app.seeds.menu_definitions import MENU_DEFINITIONS

USER_TYPES = [
    ("admin", "Admin", 1, False),
    ("user", "User", 2, False),
    ("doctor", "Doctor", 3, True),
]

AUTHORITIES = [
    ("MANAGER", "Manager", 1),
]

BILLING_TYPES = [
    ("OPD", "OPD", 1),
    ("IPD", "IPD", 2),
    ("LAB", "Lab", 3),
]

SHORT_BILL_TYPES = [
    ("SCAN", "Scan Bill", "scan_bill", "SCN", 1),
    ("XRAY", "XRay Bill", "xray_bill", "XRY", 2),
    ("OBS", "Observation Bill", "observation_bill", "OBS", 3),
    ("IMM", "Immunization Bill", "immunization_bill", "IMB", 4),
]

PREFIXES = [
    ("PATIENT", "Patient Prefix", "P", 1),
    ("OPD", "OPD Prefix", "OPD", 2),
    ("IPD", "IPD Prefix", "IPD", 3),
    ("IPDB", "IPD Bill Prefix", "IPDB", 4),
    ("PATH", "Pathology Bill Prefix", "PATH", 5),
]

# code, name, pattern, sample_output, seq_pad_width, is_selected, sort_order
PATIENT_NO_FORMATS = [
    (
        "SECTION_DAILY",
        "Section + Full Date + Daily Seq",
        "{SECTION}{YYYYMMDD}{SEQ:3}",
        "P20260619001",
        3,
        False,
        1,
    ),
    (
        "PREFIX_DAILY",
        "Prefix + Full Date + Daily Seq",
        "{PREFIX}{YYYYMMDD}{SEQ:3}",
        "P20260619001",
        3,
        True,
        2,
    ),
    (
        "PREFIX_SHORT_DATE",
        "Prefix + Short Date + Daily Seq",
        "{PREFIX}{YYMMDD}{SEQ:3}",
        "P260619002",
        3,
        False,
        3,
    ),
    (
        "SIMPLE",
        "Simple Incremental",
        "{SEQ}",
        "1",
        0,
        False,
        4,
    ),
]

PAYMENT_MODES = [
    ("CASH", "Cash", True, 1),
    ("CREDIT", "Credit", False, 2),
    ("ONLINE", "Online", False, 3),
    ("SWIPE", "Swipe", False, 4),
]

PROCEDURE_TYPES = [
    ("SURGERY", "Surgery", 1),
    ("CONSULTATION", "Consultation", 2),
    ("ENDOSCOPY", "Endoscopy", 3),
]

SERVICE_CATEGORIES = [
    ("GYN", "Gynecology", 1),
    ("SUR", "Surgery", 2),
    ("LAB", "Laboratory", 3),
    ("RAD", "Radiology", 4),
    ("GEN", "General", 5),
]

# parent_category_code, code, name, sort_order
SERVICE_SUB_CATEGORIES = [
    ("GYN", "CONSULT", "Consultation", 1),
    ("GYN", "PROC", "Procedures", 2),
    ("SUR", "MAJOR", "Major Surgery", 1),
    ("SUR", "MINOR", "Minor Surgery", 2),
    ("LAB", "BLOOD", "Blood Tests", 1),
    ("LAB", "URINE", "Urine Tests", 2),
    ("RAD", "XRAY", "X-Ray", 1),
    ("RAD", "USG", "Ultrasound", 2),
    ("GEN", "MISC", "Miscellaneous", 1),
]

# billing_code, department_code, procedure_code, sort_order
BILLING_STRUCTURE_SEEDS = [
    ("OPD", "GYN", "CONSULTATION", 1),
    ("OPD", "GYN", "SURGERY", 2),
    ("OPD", "CAR", "CONSULTATION", 1),
    ("IPD", "GYN", "SURGERY", 1),
    ("IPD", "CAR", "ENDOSCOPY", 1),
]

DEPARTMENTS = [
    ("GEN", "General Medicine", 1),
    ("SUR", "Surgery", 2),
    ("PED", "Pediatrics", 3),
    ("GYN", "Gynecology", 4),
    ("ORT", "Orthopedics", 5),
    ("CAR", "Cardiology", 6),
    ("PATH", "Pathology", 7),
    ("RAD", "Radiology", 8),
]

ROLES = [
    ("Super Admin", "Full system access"),
    ("Admin", "Hospital administrator"),
    ("Reception", "Front desk staff"),
    ("Billing", "Billing department"),
]


async def seed_initial_data(session: AsyncSession) -> None:
    role_map = await _seed_roles(session)
    user_type_map = await _seed_user_types(session)
    await _seed_departments(session)
    await _seed_hospital_profile(session)
    await _seed_dummy_doctor(session)
    await _seed_billing_types(session)
    await _seed_short_bill_types(session)
    await _seed_authorities(session)
    await _seed_prefixes(session)
    await _seed_patient_no_formats(session)
    await _seed_payment_modes(session)
    await _seed_procedure_types(session)
    await _seed_service_categories(session)
    await _seed_service_sub_categories(session)
    await _seed_billing_structure(session)
    menu_map = await _seed_menus(session)
    await _seed_role_permissions(session, role_map, menu_map)
    await _seed_super_admin(session, role_map["Super Admin"], user_type_map["admin"])


async def _seed_user_types(session: AsyncSession) -> dict[str, str]:
    result: dict[str, str] = {}
    existing = {
        item.code: item
        for item in (await session.execute(select(UserType))).scalars().all()
    }
    for code, name, sort_order, maps_to_doctor in USER_TYPES:
        user_type = existing.get(code)
        if not user_type:
            user_type = UserType(
                code=code,
                name=name,
                sort_order=sort_order,
                maps_to_doctor=maps_to_doctor,
                is_active=True,
            )
            session.add(user_type)
            await session.flush()
        else:
            changed = (
                user_type.name != name
                or user_type.sort_order != sort_order
                or user_type.maps_to_doctor != maps_to_doctor
                or not user_type.is_active
            )
            if changed:
                user_type.name = name
                user_type.sort_order = sort_order
                user_type.maps_to_doctor = maps_to_doctor
                user_type.is_active = True
        result[code] = user_type.id
    return result


async def _seed_billing_types(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(BillingType))).scalars().all()
    }
    for code, name, sort_order in BILLING_TYPES:
        item = existing.get(code)
        if not item:
            session.add(
                BillingType(code=code, name=name, sort_order=sort_order, is_active=True)
            )
        elif item.name != name or item.sort_order != sort_order or not item.is_active:
            item.name = name
            item.sort_order = sort_order
            item.is_active = True


async def _seed_short_bill_types(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(ShortBillType))).scalars().all()
    }
    # Defaults are inserted once. Later edits and deletes must not be overwritten on startup.
    if existing:
        return
    for code, name, menu_code, prefix, sort_order in SHORT_BILL_TYPES:
        session.add(
            ShortBillType(
                code=code,
                name=name,
                menu_code=menu_code,
                bill_prefix=prefix,
                sort_order=sort_order,
                is_active=True,
            )
        )


async def _seed_prefixes(session: AsyncSession) -> None:
    existing = {
        (item.code or "").upper(): item
        for item in (await session.execute(select(Prefix))).scalars().all()
    }
    for code, name, prefix_value, sort_order in PREFIXES:
        item = existing.get(code.upper())
        if item:
            # Keep hospital-customized prefix_value/name/sort_order. Overwriting
            # on every startup reset the patient letter back to "P".
            continue
        session.add(
            Prefix(
                code=code,
                name=name,
                prefix_value=prefix_value,
                sort_order=sort_order,
                is_active=True,
            )
        )


async def _seed_patient_no_formats(session: AsyncSession) -> None:
    existing = {
        (item.code or "").upper(): item
        for item in (await session.execute(select(PatientNoFormat))).scalars().all()
    }
    has_selected = any(item.is_selected and item.is_active for item in existing.values())
    for code, name, pattern, sample_output, seq_pad_width, is_selected, sort_order in PATIENT_NO_FORMATS:
        item = existing.get(code.upper())
        if item:
            # Keep hospital-customized formats. Overwriting reset sample_output
            # to examples like "P20260619001" on every backend start.
            if not has_selected and is_selected:
                for other in existing.values():
                    other.is_selected = False
                item.is_selected = True
                item.is_active = True
                has_selected = True
            continue
        should_select = is_selected and not has_selected
        item = PatientNoFormat(
            code=code,
            name=name,
            pattern=pattern,
            sample_output=sample_output,
            seq_pad_width=seq_pad_width,
            is_selected=should_select,
            sort_order=sort_order,
            is_active=True,
        )
        session.add(item)
        existing[code.upper()] = item
        if should_select:
            has_selected = True


async def _seed_procedure_types(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(ProcedureType))).scalars().all()
    }
    for code, name, sort_order in PROCEDURE_TYPES:
        item = existing.get(code)
        if not item:
            session.add(
                ProcedureType(code=code, name=name, sort_order=sort_order, is_active=True)
            )
        elif item.name != name or item.sort_order != sort_order or not item.is_active:
            item.name = name
            item.sort_order = sort_order
            item.is_active = True


async def _seed_service_categories(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(ServiceCategory))).scalars().all()
    }
    for code, name, sort_order in SERVICE_CATEGORIES:
        item = existing.get(code)
        if not item:
            session.add(
                ServiceCategory(code=code, name=name, sort_order=sort_order, is_active=True)
            )
        elif item.name != name or item.sort_order != sort_order or not item.is_active:
            item.name = name
            item.sort_order = sort_order
            item.is_active = True


async def _seed_service_sub_categories(session: AsyncSession) -> None:
    cat_map = {
        item.code: item
        for item in (await session.execute(select(ServiceCategory))).scalars().all()
    }
    existing = {
        (item.category_id, item.code): item
        for item in (await session.execute(select(ServiceSubCategory))).scalars().all()
    }
    for parent_code, code, name, sort_order in SERVICE_SUB_CATEGORIES:
        parent = cat_map.get(parent_code)
        if not parent:
            continue
        key = (parent.id, code)
        item = existing.get(key)
        if not item:
            session.add(
                ServiceSubCategory(
                    category_id=parent.id,
                    code=code,
                    name=name,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
        elif item.name != name or item.sort_order != sort_order or not item.is_active:
            item.name = name
            item.sort_order = sort_order
            item.is_active = True


async def _seed_billing_structure(session: AsyncSession) -> None:
    bt_map = {
        item.code: item
        for item in (await session.execute(select(BillingType))).scalars().all()
    }
    dept_map = {
        item.code: item
        for item in (await session.execute(select(Department))).scalars().all()
    }
    proc_map = {
        item.code: item
        for item in (await session.execute(select(ProcedureType))).scalars().all()
    }
    existing = {
        (m.billing_type_id, m.department_id, m.procedure_type_id): m
        for m in (await session.execute(select(BillingStructureMapping))).scalars().all()
    }
    for bt_code, dept_code, proc_code, sort_order in BILLING_STRUCTURE_SEEDS:
        bt = bt_map.get(bt_code)
        dept = dept_map.get(dept_code)
        proc = proc_map.get(proc_code)
        if not bt or not dept or not proc:
            continue
        key = (bt.id, dept.id, proc.id)
        mapping = existing.get(key)
        if not mapping:
            session.add(
                BillingStructureMapping(
                    billing_type_id=bt.id,
                    department_id=dept.id,
                    procedure_type_id=proc.id,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
        elif mapping.sort_order != sort_order or not mapping.is_active:
            mapping.sort_order = sort_order
            mapping.is_active = True


async def _seed_payment_modes(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(PaymentMode))).scalars().all()
    }
    for code, name, is_cash, sort_order in PAYMENT_MODES:
        item = existing.get(code)
        if not item:
            session.add(
                PaymentMode(
                    code=code,
                    name=name,
                    is_cash=is_cash,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
        elif (
            item.name != name
            or item.is_cash != is_cash
            or item.sort_order != sort_order
            or not item.is_active
        ):
            item.name = name
            item.is_cash = is_cash
            item.sort_order = sort_order
            item.is_active = True


async def _seed_authorities(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(Authority))).scalars().all()
    }
    for code, name, sort_order in AUTHORITIES:
        item = existing.get(code)
        if not item:
            session.add(
                Authority(code=code, name=name, sort_order=sort_order, is_active=True)
            )
        elif item.name != name or item.sort_order != sort_order or not item.is_active:
            item.name = name
            item.sort_order = sort_order
            item.is_active = True


async def _seed_departments(session: AsyncSession) -> None:
    existing = {
        item.code: item
        for item in (await session.execute(select(Department))).scalars().all()
    }
    for code, name, sort_order in DEPARTMENTS:
        dept = existing.get(code)
        if not dept:
            session.add(
                Department(code=code, name=name, sort_order=sort_order, is_active=True)
            )
        elif dept.name != name or dept.sort_order != sort_order or not dept.is_active:
            dept.name = name
            dept.sort_order = sort_order
            dept.is_active = True


async def _seed_hospital_profile(session: AsyncSession) -> None:
    existing = await session.execute(select(HospitalProfile).where(HospitalProfile.code == "MAIN"))
    if existing.scalar_one_or_none():
        return
    from app.repositories.hospital_profile import DEFAULT_SETTINGS

    session.add(HospitalProfile(code="MAIN", **DEFAULT_SETTINGS))


async def _seed_dummy_doctor(session: AsyncSession) -> None:
    dept_result = await session.execute(select(Department).where(Department.code == "GEN"))
    department = dept_result.scalar_one_or_none()
    existing = await session.execute(select(Doctor).where(Doctor.doctor_code == "SAMPLE"))
    doctor = existing.scalar_one_or_none()
    if doctor:
        doctor.title = "Dr."
        doctor.first_name = "Sample"
        doctor.second_name = "Doctor"
        doctor.qualification = "MBBS"
        doctor.mobile = "9999999999"
        doctor.department_id = department.id if department else doctor.department_id
        doctor.is_active = True
        return
    session.add(
        Doctor(
            doctor_code="SAMPLE",
            title="Dr.",
            first_name="Sample",
            second_name="Doctor",
            qualification="MBBS",
            mobile="9999999999",
            department_id=department.id if department else None,
            is_active=True,
        )
    )


async def _seed_roles(session: AsyncSession) -> dict[str, str]:
    result: dict[str, str] = {}
    existing = {
        role.role_name: role
        for role in (await session.execute(select(Role))).scalars().all()
    }
    for role_name, description in ROLES:
        role = existing.get(role_name)
        if not role:
            role = Role(role_name=role_name, description=description, is_active=True)
            session.add(role)
            await session.flush()
        result[role_name] = role.id
    return result


async def _seed_menus(session: AsyncSession) -> dict[str, str]:
    result: dict[str, str] = {}
    defined_codes: set[str] = set()
    existing = {
        menu.code: menu
        for menu in (await session.execute(select(Menu))).scalars().all()
    }

    # Pass 1 — ensure every menu row exists so parent codes can resolve reliably.
    for (
        code,
        label,
        _parent_code,
        sort_order,
        legacy_mcode,
        legacy_form,
        parameters,
    ) in MENU_DEFINITIONS:
        defined_codes.add(code)
        menu = existing.get(code)
        if not menu:
            menu = Menu(
                code=code,
                label=label,
                parent_id=None,
                sort_order=sort_order,
                legacy_mcode=legacy_mcode,
                legacy_form=legacy_form,
                parameters=parameters,
                is_active=True,
            )
            session.add(menu)
            await session.flush()
            existing[code] = menu
        result[code] = menu.id

    # Pass 2 — sync labels, parents, and ordering from definitions.
    for (
        code,
        label,
        parent_code,
        sort_order,
        legacy_mcode,
        legacy_form,
        parameters,
    ) in MENU_DEFINITIONS:
        parent_id = result.get(parent_code) if parent_code else None
        menu = existing[code]
        menu.label = label
        menu.parent_id = parent_id
        menu.sort_order = sort_order
        menu.legacy_mcode = legacy_mcode
        menu.legacy_form = legacy_form
        menu.parameters = parameters
        menu.is_active = True

    for menu in existing.values():
        # sso_* menus are created from Single Service OPD Setup and must survive reseeding.
        if menu.code.startswith(("sso_", "sbt_")):
            continue
        if menu.code not in defined_codes and menu.is_active:
            menu.is_active = False

    return result


async def _seed_role_permissions(
    session: AsyncSession,
    role_map: dict[str, str],
    menu_map: dict[str, str],
) -> None:
    super_admin_id = role_map["Super Admin"]
    existing_menu_ids = set(
        (
            await session.execute(
                select(RoleMenuPermission.menu_id).where(
                    RoleMenuPermission.role_id == super_admin_id
                )
            )
        ).scalars().all()
    )
    for menu_id in menu_map.values():
        if menu_id in existing_menu_ids:
            continue
        session.add(
            RoleMenuPermission(
                role_id=super_admin_id,
                menu_id=menu_id,
                can_view=True,
                can_create=True,
                can_update=True,
                can_delete=True,
            )
        )


async def _seed_super_admin(
    session: AsyncSession,
    super_admin_role_id: str,
    admin_user_type_id: str,
) -> None:
    email = "admin@admin.com"
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("admin123"),
            full_name="Super Admin",
            phone="0000000000",
            user_type_id=admin_user_type_id,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    else:
        if user.user_type_id != admin_user_type_id:
            user.user_type_id = admin_user_type_id

    mapping_result = await session.execute(
        select(UserRoleMapping).where(
            UserRoleMapping.user_id == user.id,
            UserRoleMapping.role_id == super_admin_role_id,
        )
    )
    if not mapping_result.scalar_one_or_none():
        session.add(
            UserRoleMapping(user_id=user.id, role_id=super_admin_role_id, priority=1)
        )
