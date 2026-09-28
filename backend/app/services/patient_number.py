import re
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_no_format import PatientNoFormat
from app.repositories.hospital_section import HospitalSectionRepository
from app.repositories.number_sequence import NumberSequenceRepository
from app.repositories.patient_no_format import PatientNoFormatRepository
from app.schemas.patient import PatientNoPreview
from app.services.prefix import PrefixService

TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
ENTITY_PATIENT = "patient"


@dataclass(frozen=True)
class PatientNumberContext:
    prefix: str
    section_char: str
    now: datetime


class PatientNumberGenerator:
    def __init__(self, default_pad: int = 3):
        self.default_pad = default_pad

    def _render_token(self, token: str, ctx: PatientNumberContext, seq: int | None) -> str:
        upper = token.strip().upper()
        if upper in ("PREFIX", "P"):
            return ctx.prefix
        if upper in ("SECTION", "S"):
            return ctx.section_char
        if upper == "YYYY":
            return ctx.now.strftime("%Y")
        if upper == "YY":
            return ctx.now.strftime("%y")
        if upper == "MM":
            return ctx.now.strftime("%m")
        if upper == "DD":
            return ctx.now.strftime("%d")
        if upper == "YYYYMMDD":
            return ctx.now.strftime("%Y%m%d")
        if upper == "YYMMDD":
            return ctx.now.strftime("%y%m%d")
        if upper.startswith("SEQ"):
            if seq is None:
                return ""
            parts = token.split(":")
            pad = int(parts[1]) if len(parts) > 1 else self.default_pad
            if pad <= 0:
                return str(seq)
            return f"{seq:0{pad}d}"
        raise ValueError(f"Unknown pattern token: {{{token}}}")

    def build_scope_key(self, pattern: str, ctx: PatientNumberContext) -> str:
        def replace(match: re.Match[str]) -> str:
            return self._render_token(match.group(1), ctx, None)

        return TOKEN_PATTERN.sub(replace, pattern)

    def generate(self, pattern: str, ctx: PatientNumberContext, seq: int) -> str:
        def replace(match: re.Match[str]) -> str:
            return self._render_token(match.group(1), ctx, seq)

        return TOKEN_PATTERN.sub(replace, pattern)

    @staticmethod
    def validate_pattern(pattern: str) -> None:
        if not TOKEN_PATTERN.search(pattern):
            raise ValueError("Pattern must include at least one token, e.g. {SEQ} or {PREFIX}{YYYYMMDD}{SEQ:3}")
        for match in TOKEN_PATTERN.finditer(pattern):
            token = match.group(1).strip().upper()
            allowed = (
                "PREFIX",
                "P",
                "SECTION",
                "S",
                "YYYY",
                "YY",
                "MM",
                "DD",
                "YYYYMMDD",
                "YYMMDD",
            )
            if token.startswith("SEQ") or token in allowed:
                continue
            raise ValueError(f"Unknown token: {{{match.group(1)}}}")


def section_char_from_code(code: str | None, fallback: str) -> str:
    if code:
        stripped = code.strip().upper()
        if stripped:
            return stripped[0]
    return fallback[:1].upper() if fallback else "P"


class PatientNumberService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.format_repo = PatientNoFormatRepository(session)
        self.sequence_repo = NumberSequenceRepository(session)
        self.section_repo = HospitalSectionRepository(session)
        self.prefix_svc = PrefixService(session)

    async def get_selected_format(self) -> PatientNoFormat:
        item = await self.format_repo.get_selected()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No patient number format is configured",
            )
        return item

    async def preview(
        self,
        pattern: str,
        *,
        seq_pad_width: int = 3,
        prefix: str = "P",
        section_char: str = "P",
        seq: int = 1,
    ) -> str:
        PatientNumberGenerator.validate_pattern(pattern)
        ctx = PatientNumberContext(
            prefix=prefix,
            section_char=section_char,
            now=datetime.now(timezone.utc),
        )
        return PatientNumberGenerator(seq_pad_width).generate(pattern, ctx, seq)

    async def _build_context(
        self,
        *,
        hospital_section_id: str | None = None,
        hospital_section_code: str | None = None,
    ) -> tuple[PatientNoFormat, PatientNumberContext, PatientNumberGenerator]:
        fmt = await self.get_selected_format()
        prefix = await self.prefix_svc.get_prefix_value("PATIENT", "P")
        section_code = hospital_section_code
        if hospital_section_id and not section_code:
            section = await self.section_repo.get_by_id(hospital_section_id)
            if section:
                section_code = section.code
        section_char = section_char_from_code(section_code, prefix)
        ctx = PatientNumberContext(
            prefix=prefix,
            section_char=section_char,
            now=datetime.now(timezone.utc),
        )
        return fmt, ctx, PatientNumberGenerator(fmt.seq_pad_width)

    async def preview_next(
        self,
        *,
        hospital_section_id: str | None = None,
    ) -> PatientNoPreview:
        fmt, ctx, generator = await self._build_context(hospital_section_id=hospital_section_id)
        scope_key = generator.build_scope_key(fmt.pattern, ctx)
        seq = await self.sequence_repo.peek_value(ENTITY_PATIENT, scope_key) + 1
        return PatientNoPreview(
            patient_no=generator.generate(fmt.pattern, ctx, seq),
            format_code=fmt.code,
            format_name=fmt.name,
            pattern=fmt.pattern,
            sample_output=fmt.sample_output,
        )

    async def generate_next(
        self,
        *,
        hospital_section_id: str | None = None,
        hospital_section_code: str | None = None,
    ) -> str:
        fmt, ctx, generator = await self._build_context(
            hospital_section_id=hospital_section_id,
            hospital_section_code=hospital_section_code,
        )
        scope_key = generator.build_scope_key(fmt.pattern, ctx)
        seq = await self.sequence_repo.get_next_value(ENTITY_PATIENT, scope_key)
        return generator.generate(fmt.pattern, ctx, seq)
