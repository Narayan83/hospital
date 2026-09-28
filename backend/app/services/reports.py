from pathlib import Path

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.reports.page_layout import prepare_report_html


class ReportService:
    def __init__(self):
        settings = get_settings()
        self.templates_dir = Path(__file__).resolve().parent.parent / "reports" / "templates"
        self.output_dir = settings.reports_output_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return prepare_report_html(template.render(**context))

    @staticmethod
    def _write_pdf_xhtml2pdf(html_content: str, output_path: Path) -> None:
        from xhtml2pdf import pisa

        with output_path.open("wb") as pdf_file:
            status = pisa.CreatePDF(html_content, dest=pdf_file, encoding="utf-8")
        if status.err:
            raise RuntimeError("xhtml2pdf failed to render the bill template")

    def write_pdf(self, html_content: str, output_filename: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / output_filename

        try:
            self._write_pdf_xhtml2pdf(html_content, output_path)
            return output_path
        except ImportError:
            detail = "PDF generation unavailable — xhtml2pdf is not installed."
        except Exception as exc:
            detail = f"PDF generation failed: {exc}"

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    def generate_pdf(self, template_name: str, context: dict, output_filename: str) -> Path:
        return self.write_pdf(self.render_html(template_name, context), output_filename)

    def generate_excel(self, context: dict) -> bytes:
        from app.reports.bill_excel import build_bill_excel

        return build_bill_excel(context)

    def generate_excel_from_html(
        self, html: str, *, title: str = "Report", data_only: bool = False
    ) -> bytes:
        from app.reports.html_excel import html_tables_to_excel

        return html_tables_to_excel(html, title=title, data_only=data_only)
