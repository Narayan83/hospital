from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_patient_service, get_report_service, get_session
from app.models.user import User
from app.reports.advance_receipt_context import build_advance_receipt_context
from app.reports.bill_context import (
    _fmt_date,
    build_discharge_summary_context,
    build_ipd_bill_context,
    build_opd_bill_context,
    build_opd_casesheet_context,
    build_pathology_bill_context,
    build_pathology_report_context,
    build_pharmacy_sale_bill_context,
    build_patient_card_context,
    hospital_header_context,
)
from app.reports.cancellation_bill_report_context import build_cancellation_bill_report_context
from app.reports.modification_bill_report_context import build_modification_bill_report_context
from app.reports.doctor_collection_context import build_doctor_collection_report_context
from app.reports.form_3c_report_context import build_form_3c_report_context
from app.reports.pathology_collection_context import build_pathology_collection_report_context
from app.reports.short_bill_report_context import (
    build_short_bill_receipt_context,
    build_short_bill_report_context,
)
from app.reports.user_cash_transaction_context import build_user_cash_transaction_report_context
from app.services.accounting_voucher import AccountingVoucherService
from app.services.cancellation_bill_report import CancellationBillReportService
from app.services.modification_bill_report import ModificationBillReportService
from app.services.doctor import DoctorService
from app.services.hospital_profile import HospitalProfileService
from app.services.ipd_discharge import IpdDischargeService
from app.services.ipd_discharge_summary import IpdDischargeSummaryService
from app.services.opd_bill import OpdBillService
from app.services.pathology_bill import PathologyBillService
from app.services.pathology_collection_report import PathologyCollectionReportService
from app.services.pathology_masters import PathologyOrderService
from app.services.pharmacy_bills import PharmacyBillService
from app.services.print_config import PrintConfigService
from app.services.patient import PatientService
from app.services.reports import ReportService
from app.services.doctor_collection_report import DoctorCollectionReportService
from app.services.form_3c_report import Form3CReportService
from app.services.short_bill import ShortBillService
from app.services.user_cash_transaction_report import UserCashTransactionReportService
from app.schemas.cancellation_bill_report import CancellationBillReportRead
from app.schemas.modification_bill_report import ModificationBillReportRead
from app.schemas.doctor_collection_report import (
    DoctorCollectionColumnReportRead,
    DoctorCollectionDateServiceReportRead,
    DoctorCollectionPaymentModeReportRead,
    DoctorCollectionReportRead,
)
from app.schemas.form_3c_report import Form3CReportRead
from app.schemas.pathology_collection_report import (
    PathologyCollectionColumnReportRead,
    PathologyCollectionReportRead,
)
from app.schemas.user_cash_transaction_report import UserCashTransactionReportRead

router = APIRouter()


async def _report_context(
    session: AsyncSession,
    base: dict,
    *,
    report_code: str | None = None,
    header_name_field: str = "name",
) -> dict:
    profile = await HospitalProfileService(session).get_profile()
    ctx = {**base, **hospital_header_context(profile, name_field=header_name_field)}
    if report_code == "PATHOLOGY_REPORT":
        try:
            cfg = await PrintConfigService(session).get_config_by_code("PATHOLOGY_REPORT")
            if isinstance(cfg.layout_options, dict):
                from app.reports.bill_context import merge_pathology_report_layout

                ctx["report_layout"] = merge_pathology_report_layout(
                    ctx.get("report_layout"),
                    cfg.layout_options,
                )
        except HTTPException:
            pass
    return ctx


def _pdf_response(output_path, download_name: str) -> FileResponse:
    if not output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )
    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=download_name,
    )


async def _saved_bill_layout(session: AsyncSession, code: str):
    """Return (layout, paper) when a designer layout has been saved."""
    try:
        cfg = await PrintConfigService(session).get_config_by_code(code)
    except HTTPException:
        return None, "A4"
    layout = cfg.layout_options if isinstance(cfg.layout_options, dict) else None
    if not layout or not layout.get("designed"):
        return None, cfg.paper_size or "A4"
    paper = (cfg.paper_size or "A4").upper()
    if paper == "CUSTOM":
        from app.reports.print_layouts import custom_pages_of

        pages = custom_pages_of(layout)
        match = None
        for page_code, page in pages.items():
            if (
                cfg.custom_width_mm
                and abs(float(page["width_mm"]) - float(cfg.custom_width_mm)) < 0.6
                and cfg.custom_height_mm
                and abs(float(page["height_mm"]) - float(cfg.custom_height_mm)) < 0.6
            ):
                match = page_code
                break
        paper = match or (next(iter(pages)) if len(pages) == 1 else "A4")
    return layout, paper


async def _render_designed_bill(
    session: AsyncSession,
    report_service: ReportService,
    code: str,
    base: dict,
    *,
    template_name: str,
    header_name_field: str = "name",
) -> str:
    ctx = await _report_context(session, base, header_name_field=header_name_field)
    layout, paper = await _saved_bill_layout(session, code)
    if layout:
        from app.reports.layout_render import render_document_html

        from app.reports.page_layout import prepare_report_html

        return prepare_report_html(
            render_document_html(code=code, context=ctx, layout_raw=layout, bill_format=paper)
        )
    return report_service.render_html(template_name, ctx)


async def _pdf_designed_bill(
    session: AsyncSession,
    report_service: ReportService,
    code: str,
    base: dict,
    output_filename: str,
    *,
    template_name: str,
    header_name_field: str = "name",
):
    html = await _render_designed_bill(
        session,
        report_service,
        code,
        base,
        template_name=template_name,
        header_name_field=header_name_field,
    )
    return report_service.write_pdf(html, output_filename)


def _html_response(html: str) -> HTMLResponse:
    return HTMLResponse(content=html)


def _excel_response(content: bytes, download_name: str) -> Response:
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.get("/opd-bill/{bill_id}/html")
async def opd_bill_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill(bill_id)
    html = await _render_designed_bill(
        session, report_service, "OPD_BILL", build_opd_bill_context(bill), template_name="bill_receipt.html"
    )
    return _html_response(html)


@router.get("/opd-bill/by-no/{bill_no}/html")
async def opd_bill_html_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill_by_no(bill_no)
    html = await _render_designed_bill(
        session, report_service, "OPD_BILL", build_opd_bill_context(bill), template_name="bill_receipt.html"
    )
    return _html_response(html)


@router.get("/opd-bill/{bill_id}/excel")
async def opd_bill_excel(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill(bill_id)
    content = report_service.generate_excel(await _report_context(session, build_opd_bill_context(bill)))
    return _excel_response(content, f"OPD_Bill_{bill.bill_no}.xlsx")


@router.get("/opd-bill/by-no/{bill_no}/excel")
async def opd_bill_excel_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill_by_no(bill_no)
    content = report_service.generate_excel(await _report_context(session, build_opd_bill_context(bill)))
    return _excel_response(content, f"OPD_Bill_{bill.bill_no}.xlsx")


@router.get("/patient-registration/{patient_id}")
async def patient_registration_pdf(
    patient_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    patient_service = get_patient_service(session)
    patient = await patient_service.get_patient(patient_id)

    output_path = report_service.generate_pdf(
        template_name="patient_registration.html",
        context=await _report_context(session, {"patient": patient.model_dump()}),
        output_filename=f"patient_{patient.patient_no}.pdf",
    )
    return _pdf_response(output_path, output_path.name)


@router.get("/patient-card/{patient_id}/html")
async def patient_card_html(
    patient_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    patient = await get_patient_service(session).get_patient(patient_id)
    html = report_service.render_html(
        "patient_card.html",
        await _report_context(session, build_patient_card_context(patient)),
    )
    return _html_response(html)


@router.get("/patient-card/{patient_id}")
async def patient_card_pdf(
    patient_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    patient = await get_patient_service(session).get_patient(patient_id)
    output_path = report_service.generate_pdf(
        template_name="patient_card.html",
        context=await _report_context(session, build_patient_card_context(patient)),
        output_filename=f"patient_card_{patient.patient_no}.pdf",
    )
    return _pdf_response(output_path, f"Patient_Card_{patient.patient_no}.pdf")


@router.get("/opd-casesheet/{patient_id}/html")
async def opd_casesheet_html(
    patient_id: str,
    doctor_id: str = Query(..., min_length=1),
    case_date: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    patient = await get_patient_service(session).get_patient(patient_id)
    doctor = await DoctorService(session).get_doctor(doctor_id)
    target_date = case_date or date.today()
    html = report_service.render_html(
        "opd_casesheet.html",
        await _report_context(
            session,
            build_opd_casesheet_context(
                patient,
                case_date=_fmt_date(target_date),
                doctor_name=doctor.full_name,
            ),
        ),
    )
    return _html_response(html)


@router.get("/opd-bill/{bill_id}")
async def opd_bill_pdf(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill(bill_id)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "OPD_BILL",
        build_opd_bill_context(bill),
        f"opd_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
    )
    return _pdf_response(output_path, f"OPD_Bill_{bill.bill_no}.pdf")


@router.get("/opd-bill/by-no/{bill_no}")
async def opd_bill_pdf_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await OpdBillService(session).get_bill_by_no(bill_no)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "OPD_BILL",
        build_opd_bill_context(bill),
        f"opd_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
    )
    return _pdf_response(output_path, f"OPD_Bill_{bill.bill_no}.pdf")


@router.get("/ipd-bill/{bill_id}/html")
async def ipd_bill_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge(bill_id)
    html = await _render_designed_bill(
        session, report_service, "IPD_BILL", build_ipd_bill_context(bill), template_name="bill_receipt.html"
    )
    return _html_response(html)


@router.get("/ipd-bill/by-no/{bill_no}/html")
async def ipd_bill_html_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge_by_no(bill_no)
    html = await _render_designed_bill(
        session, report_service, "IPD_BILL", build_ipd_bill_context(bill), template_name="bill_receipt.html"
    )
    return _html_response(html)


@router.get("/ipd-bill/{bill_id}/excel")
async def ipd_bill_excel(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge(bill_id)
    content = report_service.generate_excel(await _report_context(session, build_ipd_bill_context(bill)))
    return _excel_response(content, f"IPD_Bill_{bill.bill_no}.xlsx")


@router.get("/ipd-bill/by-no/{bill_no}/excel")
async def ipd_bill_excel_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge_by_no(bill_no)
    content = report_service.generate_excel(await _report_context(session, build_ipd_bill_context(bill)))
    return _excel_response(content, f"IPD_Bill_{bill.bill_no}.xlsx")


@router.get("/ipd-bill/{bill_id}")
async def ipd_bill_pdf(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge(bill_id)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "IPD_BILL",
        build_ipd_bill_context(bill),
        f"ipd_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
    )
    return _pdf_response(output_path, f"IPD_Bill_{bill.bill_no}.pdf")


@router.get("/ipd-bill/by-no/{bill_no}")
async def ipd_bill_pdf_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await IpdDischargeService(session).get_discharge_by_no(bill_no)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "IPD_BILL",
        build_ipd_bill_context(bill),
        f"ipd_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
    )
    return _pdf_response(output_path, f"IPD_Bill_{bill.bill_no}.pdf")


@router.get("/pathology-bill/{bill_id}/html")
async def pathology_bill_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill(bill_id)
    html = await _render_designed_bill(
        session,
        report_service,
        "PATHOLOGY_BILL",
        build_pathology_bill_context(bill),
        template_name="bill_receipt.html",
        header_name_field="pathology_name",
    )
    return _html_response(html)


@router.get("/pathology-bill/by-no/{bill_no}/html")
async def pathology_bill_html_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill_by_no(bill_no)
    html = await _render_designed_bill(
        session,
        report_service,
        "PATHOLOGY_BILL",
        build_pathology_bill_context(bill),
        template_name="bill_receipt.html",
        header_name_field="pathology_name",
    )
    return _html_response(html)


@router.get("/pathology-bill/{bill_id}/excel")
async def pathology_bill_excel(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill(bill_id)
    content = report_service.generate_excel(
        await _report_context(
            session,
            build_pathology_bill_context(bill),
            header_name_field="pathology_name",
        )
    )
    return _excel_response(content, f"Pathology_Bill_{bill.bill_no}.xlsx")


@router.get("/pathology-bill/by-no/{bill_no}/excel")
async def pathology_bill_excel_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill_by_no(bill_no)
    content = report_service.generate_excel(
        await _report_context(
            session,
            build_pathology_bill_context(bill),
            header_name_field="pathology_name",
        )
    )
    return _excel_response(content, f"Pathology_Bill_{bill.bill_no}.xlsx")


@router.get("/pathology-bill/{bill_id}")
async def pathology_bill_pdf(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill(bill_id)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "PATHOLOGY_BILL",
        build_pathology_bill_context(bill),
        f"pathology_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
        header_name_field="pathology_name",
    )
    return _pdf_response(output_path, f"Pathology_Bill_{bill.bill_no}.pdf")


@router.get("/pathology-bill/by-no/{bill_no}")
async def pathology_bill_pdf_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill_by_no(bill_no)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "PATHOLOGY_BILL",
        build_pathology_bill_context(bill),
        f"pathology_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
        header_name_field="pathology_name",
    )
    return _pdf_response(output_path, f"Pathology_Bill_{bill.bill_no}.pdf")


@router.get("/pharmacy-sale-bill/{bill_id}/html")
async def pharmacy_sale_bill_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PharmacyBillService(session).get_sale_bill(bill_id)
    html = await _render_designed_bill(
        session,
        report_service,
        "PHARMACY_SALE_BILL",
        build_pharmacy_sale_bill_context(bill),
        template_name="bill_receipt.html",
        header_name_field="medical_shop_name",
    )
    return _html_response(html)


@router.get("/pharmacy-sale-bill/{bill_id}")
async def pharmacy_sale_bill_pdf(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PharmacyBillService(session).get_sale_bill(bill_id)
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "PHARMACY_SALE_BILL",
        build_pharmacy_sale_bill_context(bill),
        f"pharmacy_sale_bill_{bill.bill_no}.pdf",
        template_name="bill_receipt.html",
        header_name_field="medical_shop_name",
    )
    return _pdf_response(output_path, f"Medical_Bill_{bill.bill_no}.pdf")


@router.get("/pathology-report/{bill_id}/html")
async def pathology_report_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill(bill_id)
    try:
        order = await PathologyOrderService(session).get_order_by_bill(bill_id)
    except HTTPException:
        order = None
    html = report_service.render_html(
        "pathology_report.html",
        await _report_context(
            session,
            build_pathology_report_context(bill, order),
            report_code="PATHOLOGY_REPORT",
            header_name_field="pathology_name",
        ),
    )
    return _html_response(html)


@router.get("/pathology-report/by-no/{bill_no}/html")
async def pathology_report_html_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill_by_no(bill_no)
    try:
        order = await PathologyOrderService(session).get_order_by_bill(bill.id)
    except HTTPException:
        order = None
    html = report_service.render_html(
        "pathology_report.html",
        await _report_context(
            session,
            build_pathology_report_context(bill, order),
            report_code="PATHOLOGY_REPORT",
            header_name_field="pathology_name",
        ),
    )
    return _html_response(html)


@router.get("/pathology-report/{bill_id}")
async def pathology_report_pdf(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill(bill_id)
    try:
        order = await PathologyOrderService(session).get_order_by_bill(bill_id)
    except HTTPException:
        order = None
    output_path = report_service.generate_pdf(
        template_name="pathology_report.html",
        context=await _report_context(
            session,
            build_pathology_report_context(bill, order),
            report_code="PATHOLOGY_REPORT",
            header_name_field="pathology_name",
        ),
        output_filename=f"pathology_report_{bill.bill_no}.pdf",
    )
    return _pdf_response(output_path, f"Pathology_Report_{bill.bill_no}.pdf")


@router.get("/pathology-report/by-no/{bill_no}")
async def pathology_report_pdf_by_no(
    bill_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await PathologyBillService(session).get_bill_by_no(bill_no)
    try:
        order = await PathologyOrderService(session).get_order_by_bill(bill.id)
    except HTTPException:
        order = None
    output_path = report_service.generate_pdf(
        template_name="pathology_report.html",
        context=await _report_context(
            session,
            build_pathology_report_context(bill, order),
            report_code="PATHOLOGY_REPORT",
            header_name_field="pathology_name",
        ),
        output_filename=f"pathology_report_{bill.bill_no}.pdf",
    )
    return _pdf_response(output_path, f"Pathology_Report_{bill.bill_no}.pdf")


@router.get("/discharge-summary/{summary_id}/html")
async def discharge_summary_html(
    summary_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    summary = await IpdDischargeSummaryService(session).get_summary(summary_id)
    html = report_service.render_html(
        "discharge_summary.html",
        await _report_context(session, build_discharge_summary_context(summary)),
    )
    return _html_response(html)


@router.get("/discharge-summary/by-no/{summary_no}/html")
async def discharge_summary_html_by_no(
    summary_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    summary = await IpdDischargeSummaryService(session).get_summary_by_no(summary_no)
    html = report_service.render_html(
        "discharge_summary.html",
        await _report_context(session, build_discharge_summary_context(summary)),
    )
    return _html_response(html)


@router.get("/discharge-summary/{summary_id}")
async def discharge_summary_pdf(
    summary_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    summary = await IpdDischargeSummaryService(session).get_summary(summary_id)
    output_path = report_service.generate_pdf(
        template_name="discharge_summary.html",
        context=await _report_context(session, build_discharge_summary_context(summary)),
        output_filename=f"discharge_summary_{summary.summary_no}.pdf",
    )
    return _pdf_response(output_path, f"Discharge_Summary_{summary.summary_no}.pdf")


@router.get("/discharge-summary/by-no/{summary_no}")
async def discharge_summary_pdf_by_no(
    summary_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    summary = await IpdDischargeSummaryService(session).get_summary_by_no(summary_no)
    output_path = report_service.generate_pdf(
        template_name="discharge_summary.html",
        context=await _report_context(session, build_discharge_summary_context(summary)),
        output_filename=f"discharge_summary_{summary.summary_no}.pdf",
    )
    return _pdf_response(output_path, f"Discharge_Summary_{summary.summary_no}.pdf")


@router.get("/form-3c", response_model=Form3CReportRead)
async def form_3c_report(
    billing_type_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await Form3CReportService(session).build_report(
        billing_type_id=billing_type_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/form-3c/html")
async def form_3c_report_html(
    billing_type_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await Form3CReportService(session).build_report(
        billing_type_id=billing_type_id,
        from_date=from_date,
        to_date=to_date,
    )
    html = report_service.render_html(
        "form_3c_report.html",
        await _report_context(session, build_form_3c_report_context(report)),
    )
    return _html_response(html)


@router.get("/cancellation-bills", response_model=CancellationBillReportRead)
async def cancellation_bill_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    bill_type: str = Query("all", pattern="^(all|opd|ipd|pathology)$"),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await CancellationBillReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        bill_type=bill_type,
    )


@router.get("/cancellation-bills/html")
async def cancellation_bill_report_html(
    from_date: date = Query(...),
    to_date: date = Query(...),
    bill_type: str = Query("all", pattern="^(all|opd|ipd|pathology)$"),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await CancellationBillReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        bill_type=bill_type,
    )
    html = report_service.render_html(
        "cancellation_bill_report.html",
        await _report_context(session, build_cancellation_bill_report_context(report)),
    )
    return _html_response(html)


@router.get("/modification-bills", response_model=ModificationBillReportRead)
async def modification_bill_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    bill_type: str = Query("all", pattern="^(all|opd|ipd|pathology)$"),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await ModificationBillReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        bill_type=bill_type,
    )


@router.get("/modification-bills/html")
async def modification_bill_report_html(
    from_date: date = Query(...),
    to_date: date = Query(...),
    bill_type: str = Query("all", pattern="^(all|opd|ipd|pathology)$"),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await ModificationBillReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        bill_type=bill_type,
    )
    html = report_service.render_html(
        "modification_bill_report.html",
        await _report_context(session, build_modification_bill_report_context(report)),
    )
    return _html_response(html)


@router.get("/short-bill/html")
async def short_bill_report_html(
    short_bill_type_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await ShortBillService(session).build_report(
        short_bill_type_id=short_bill_type_id,
        from_date=from_date,
        to_date=to_date,
    )
    html = report_service.render_html(
        "short_bill_report.html",
        await _report_context(session, build_short_bill_report_context(report)),
    )
    return _html_response(html)


@router.get("/short-bill/{bill_id}/html")
async def short_bill_receipt_html(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    bill = await ShortBillService(session).get_bill(bill_id)
    html = await _render_designed_bill(
        session,
        report_service,
        "SHORT_BILL",
        build_short_bill_receipt_context(bill),
        template_name="bill_receipt.html",
    )
    return _html_response(html)


@router.get("/user-cash-transaction", response_model=UserCashTransactionReportRead)
async def user_cash_transaction_report(
    user_id: str | None = Query(None, description="User id, or 'all'"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    report_type: str = Query("detail", pattern="^(detail|day_wise)$"),
    payment_mode_id: str | None = Query(None, description="Payment mode id, or 'all'"),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await UserCashTransactionReportService(session).build_report(
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        report_type=report_type,
        payment_mode_id=payment_mode_id,
    )


@router.get("/user-cash-transaction/html")
async def user_cash_transaction_report_html(
    user_id: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    report_type: str = Query("detail", pattern="^(detail|day_wise)$"),
    payment_mode_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await UserCashTransactionReportService(session).build_report(
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        report_type=report_type,
        payment_mode_id=payment_mode_id,
    )
    html = report_service.render_html(
        "user_cash_transaction_report.html",
        await _report_context(session, build_user_cash_transaction_report_context(report)),
    )
    return _html_response(html)


@router.get("/user-cash-transaction/excel")
async def user_cash_transaction_report_excel(
    user_id: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    report_type: str = Query("detail", pattern="^(detail|day_wise)$"),
    payment_mode_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await UserCashTransactionReportService(session).build_report(
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        report_type=report_type,
        payment_mode_id=payment_mode_id,
    )
    html = report_service.render_html(
        "user_cash_transaction_report.html",
        await _report_context(session, build_user_cash_transaction_report_context(report)),
    )
    content = report_service.generate_excel_from_html(
        html, title="User wise Cash Transaction Report"
    )
    return _excel_response(content, "User_Cash_Transaction_Report.xlsx")


@router.post("/excel-from-html")
async def excel_from_html(
    payload: dict,
    _: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    html = str(payload.get("html") or "")
    title = str(payload.get("title") or "Report")
    data_only = bool(payload.get("data_only", True))
    if not html.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HTML content required")
    content = report_service.generate_excel_from_html(html, title=title, data_only=data_only)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)[:60] or "Report"
    return _excel_response(content, f"{safe}.xlsx")


@router.get(
    "/doctor-collection",
    response_model=(
        DoctorCollectionReportRead
        | DoctorCollectionColumnReportRead
        | DoctorCollectionPaymentModeReportRead
        | DoctorCollectionDateServiceReportRead
    ),
)
async def doctor_collection_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    doctor_ids: list[str] | None = Query(None),
    service_ids: list[str] | None = Query(None),
    payment_modes: list[str] | None = Query(None),
    report_type: str = Query(
        "sharing",
        pattern=(
            "^(normal|sharing|day_wise_summary|payment_mode_summary|column_wise|"
            "date_service_summary|date_service_details)$"
        ),
    ),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await DoctorCollectionReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        doctor_ids=doctor_ids or None,
        service_ids=service_ids or None,
        payment_modes=payment_modes or None,
        report_type=report_type,
    )


@router.get("/doctor-collection/html")
async def doctor_collection_report_html(
    from_date: date = Query(...),
    to_date: date = Query(...),
    doctor_ids: list[str] | None = Query(None),
    service_ids: list[str] | None = Query(None),
    payment_modes: list[str] | None = Query(None),
    report_type: str = Query(
        "sharing",
        pattern=(
            "^(normal|sharing|day_wise_summary|payment_mode_summary|column_wise|"
            "date_service_summary|date_service_details)$"
        ),
    ),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await DoctorCollectionReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        doctor_ids=doctor_ids or None,
        service_ids=service_ids or None,
        payment_modes=payment_modes or None,
        report_type=report_type,
    )
    html = report_service.render_html(
        "doctor_collection_report.html",
        await _report_context(session, build_doctor_collection_report_context(report)),
    )
    return _html_response(html)


@router.get("/doctor-collection/excel")
async def doctor_collection_report_excel(
    from_date: date = Query(...),
    to_date: date = Query(...),
    doctor_ids: list[str] | None = Query(None),
    service_ids: list[str] | None = Query(None),
    payment_modes: list[str] | None = Query(None),
    report_type: str = Query(
        "sharing",
        pattern=(
            "^(normal|sharing|day_wise_summary|payment_mode_summary|column_wise|"
            "date_service_summary|date_service_details)$"
        ),
    ),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from app.reports.doctor_collection_excel import build_doctor_collection_excel

    report = await DoctorCollectionReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        doctor_ids=doctor_ids or None,
        service_ids=service_ids or None,
        payment_modes=payment_modes or None,
        report_type=report_type,
    )
    content = build_doctor_collection_excel(report)
    return _excel_response(content, "Doctor_Collection_Report.xlsx")


@router.get(
    "/pathology-collection",
    response_model=PathologyCollectionReportRead | PathologyCollectionColumnReportRead,
)
async def pathology_collection_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    doctor_ids: list[str] | None = Query(None),
    referral_names: list[str] | None = Query(None),
    report_type: str = Query("normal", pattern="^(normal|column_wise|referral_wise)$"),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await PathologyCollectionReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        doctor_ids=doctor_ids or None,
        referral_names=referral_names or None,
        report_type=report_type,
    )


@router.get("/pathology-collection/referring-doctors")
async def pathology_collection_referring_doctors(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    names = await PathologyCollectionReportService(session).list_referring_doctors(
        from_date=from_date,
        to_date=to_date,
    )
    return {"items": names}


@router.get("/pathology-collection/html")
async def pathology_collection_report_html(
    from_date: date = Query(...),
    to_date: date = Query(...),
    doctor_ids: list[str] | None = Query(None),
    referral_names: list[str] | None = Query(None),
    report_type: str = Query("normal", pattern="^(normal|column_wise|referral_wise)$"),
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    report = await PathologyCollectionReportService(session).build_report(
        from_date=from_date,
        to_date=to_date,
        doctor_ids=doctor_ids or None,
        referral_names=referral_names or None,
        report_type=report_type,
    )
    html = report_service.render_html(
        "pathology_collection_report.html",
        await _report_context(session, build_pathology_collection_report_context(report)),
    )
    return _html_response(html)


@router.get("/advance/by-no/{voucher_no}/html")
async def advance_receipt_html_by_no(
    voucher_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    svc = AccountingVoucherService(session)
    advance = await svc.get_advance_by_no(voucher_no)
    balance = None
    if advance.patient_id:
        bal = await svc.patient_deposit_balance(patient_id=advance.patient_id)
        balance = bal.balance
    html = await _render_designed_bill(
        session,
        report_service,
        "ADVANCE_RECEIPT",
        build_advance_receipt_context(advance, balance_after=balance),
        template_name="advance_receipt.html",
    )
    return _html_response(html)


@router.get("/advance/by-no/{voucher_no}")
async def advance_receipt_pdf_by_no(
    voucher_no: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    svc = AccountingVoucherService(session)
    advance = await svc.get_advance_by_no(voucher_no)
    balance = None
    if advance.patient_id:
        bal = await svc.patient_deposit_balance(patient_id=advance.patient_id)
        balance = bal.balance
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "ADVANCE_RECEIPT",
        build_advance_receipt_context(advance, balance_after=balance),
        f"advance_{advance.voucher_no}.pdf",
        template_name="advance_receipt.html",
    )
    return _pdf_response(output_path, f"Advance_{advance.voucher_no}.pdf")


@router.get("/advance/{voucher_id}/html")
async def advance_receipt_html(
    voucher_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    svc = AccountingVoucherService(session)
    advance = await svc.get_advance(voucher_id)
    balance = None
    if advance.patient_id:
        bal = await svc.patient_deposit_balance(patient_id=advance.patient_id)
        balance = bal.balance
    html = await _render_designed_bill(
        session,
        report_service,
        "ADVANCE_RECEIPT",
        build_advance_receipt_context(advance, balance_after=balance),
        template_name="advance_receipt.html",
    )
    return _html_response(html)


@router.get("/advance/{voucher_id}")
async def advance_receipt_pdf(
    voucher_id: str,
    session: AsyncSession = Depends(get_session),
    report_service: ReportService = Depends(get_report_service),
):
    svc = AccountingVoucherService(session)
    advance = await svc.get_advance(voucher_id)
    balance = None
    if advance.patient_id:
        bal = await svc.patient_deposit_balance(patient_id=advance.patient_id)
        balance = bal.balance
    output_path = await _pdf_designed_bill(
        session,
        report_service,
        "ADVANCE_RECEIPT",
        build_advance_receipt_context(advance, balance_after=balance),
        f"advance_{advance.voucher_no}.pdf",
        template_name="advance_receipt.html",
    )
    return _pdf_response(output_path, f"Advance_{advance.voucher_no}.pdf")
