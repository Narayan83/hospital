from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.number_sequence import NumberSequenceRepository
from app.services.prefix import PrefixService
from app.utils.financial_year import financial_year_start

ENTITY_OPD_BILL = "opd_bill"
ENTITY_IPD_ADMISSION = "ipd_admission"
ENTITY_IPD_BILL = "ipd_bill"
ENTITY_PATHOLOGY_BILL = "pathology_bill"
ENTITY_PHARMACY_SALE = "pharmacy_sale_bill"
ENTITY_PHARMACY_PURCHASE = "pharmacy_purchase_bill"
ENTITY_SHORT_BILL = "short_bill"
ENTITY_SINGLE_SERVICE_OPD = "single_service_opd"
ENTITY_DISCHARGE_SUMMARY = "discharge_summary"
ENTITY_ADVANCE_VOUCHER = "advance_voucher"
ENTITY_PAYMENT_VOUCHER = "payment_voucher"
ENTITY_CONTRA_VOUCHER = "contra_voucher"


class BillNumberService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sequence_repo = NumberSequenceRepository(session)
        self.prefix_svc = PrefixService(session)

    async def generate_opd_bill_no(self, bill_date: date | None = None) -> str:
        """Yearly OPD bill series — e.g. OPD202600001 (resets each financial year from 1 Apr)."""
        prefix = await self.prefix_svc.get_prefix_value("OPD", "OPD")
        target = bill_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(ENTITY_OPD_BILL, scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_ipd_admission_no(self) -> str:
        prefix = await self.prefix_svc.get_prefix_value("IPD", "IPD")
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        scope_key = f"{prefix}{today}"
        seq = await self.sequence_repo.get_next_value(ENTITY_IPD_ADMISSION, scope_key)
        return f"{scope_key}{seq:04d}"

    async def generate_ipd_bill_no(self, bill_date: date | None = None) -> str:
        """Yearly IPD discharge bill series — e.g. IPDB202600001 (resets each financial year from 1 Apr)."""
        prefix = await self.prefix_svc.get_prefix_value("IPDB", "IPDB")
        target = bill_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(ENTITY_IPD_BILL, scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_pathology_bill_no(self) -> str:
        prefix = await self.prefix_svc.get_prefix_value("PATH", "PATH")
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        scope_key = f"{prefix}{today}"
        seq = await self.sequence_repo.get_next_value(ENTITY_PATHOLOGY_BILL, scope_key)
        return f"{scope_key}{seq:04d}"

    async def generate_discharge_summary_no(self, summary_date: date | None = None) -> str:
        """Yearly discharge summary series — e.g. DS202600001 (resets each financial year from 1 Apr)."""
        prefix = await self.prefix_svc.get_prefix_value("DS", "DS")
        target = summary_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(ENTITY_DISCHARGE_SUMMARY, scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_pharmacy_sale_bill_no(self, bill_date: date | None = None) -> str:
        prefix = await self.prefix_svc.get_prefix_value("PHARM", "PHS")
        target = bill_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(ENTITY_PHARMACY_SALE, scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_pharmacy_purchase_bill_no(self, bill_date: date | None = None) -> str:
        prefix = await self.prefix_svc.get_prefix_value("PHARMP", "PHP")
        target = bill_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(ENTITY_PHARMACY_PURCHASE, scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_short_bill_no(
        self,
        bill_prefix: str,
        type_code: str,
        bill_date: date | None = None,
    ) -> str:
        prefix = (bill_prefix or "SB").strip().upper()
        target = bill_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(f"{ENTITY_SHORT_BILL}:{type_code}", scope_key)
        return f"{scope_key}{seq:05d}"

    async def generate_single_service_opd_no(
        self,
        option_id: str,
        bill_prefix: str,
        bill_date: date | None = None,
    ) -> str:
        """Separate yearly series per option — e.g. CON202600001, restarts each financial year."""
        prefix = "".join(ch for ch in (bill_prefix or "SSO").upper() if ch.isalnum())[:10] or "SSO"
        target = bill_date or date.today()
        year = financial_year_start(target)
        scope_key = f"{option_id}:{year}"
        seq = await self.sequence_repo.get_next_value(ENTITY_SINGLE_SERVICE_OPD, scope_key)
        return f"{prefix}{year}{seq:05d}"

    async def generate_accounting_voucher_no(
        self,
        voucher_kind: str,
        voucher_date: date | None = None,
    ) -> str:
        prefixes = {
            "advance": "ADV",
            "payment": "PAY",
            "contra": "CNT",
        }
        entity_keys = {
            "advance": ENTITY_ADVANCE_VOUCHER,
            "payment": ENTITY_PAYMENT_VOUCHER,
            "contra": ENTITY_CONTRA_VOUCHER,
        }
        kind = (voucher_kind or "payment").strip().lower()
        prefix = prefixes.get(kind, "VCH")
        entity = entity_keys.get(kind, ENTITY_PAYMENT_VOUCHER)
        target = voucher_date or date.today()
        scope_key = f"{prefix}{financial_year_start(target)}"
        seq = await self.sequence_repo.get_next_value(entity, scope_key)
        return f"{scope_key}{seq:05d}"
