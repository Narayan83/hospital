from app.reports.layout_render import render_document_html
from app.reports.print_layouts import default_document_layout, normalize_layout, sample_context


def test_default_opd_layout_renders_patient_and_lines():
    layout = default_document_layout("OPD_BILL")
    layout["designed"] = True
    html = render_document_html(
        code="OPD_BILL",
        context=sample_context("OPD_BILL"),
        layout_raw=layout,
        bill_format="A5",
    )
    assert "Anita Rao" in html
    assert "Consultation" in html
    assert "OP-1042" in html


def test_hidden_field_is_omitted_and_custom_page_kept():
    layout = default_document_layout("IPD_BILL")
    layout["custom_pages"] = {"CUSTOM_SLIP": {"name": "Slip", "width_mm": 100, "height_mm": 150}}
    layout["formats"]["CUSTOM_SLIP"] = layout["formats"]["A4"]
    for field in layout["formats"]["A4"]["meta"]:
        if field["id"] == "patient_name":
            field["visible"] = False
    normalized = normalize_layout("IPD_BILL", layout)
    assert "CUSTOM_SLIP" in normalized["custom_pages"]
    html = render_document_html(
        code="IPD_BILL",
        context=sample_context("IPD_BILL"),
        layout_raw=normalized,
        bill_format="A4",
    )
    assert "Anita Rao" not in html
    assert "Admission no" in html


def test_static_text_prints():
    layout = default_document_layout("ADVANCE_RECEIPT")
    layout["formats"]["A4"]["footer"].append(
        {"id": "static_note", "band": "footer", "visible": True, "label": "Note", "align": "left", "text": "Pay at counter"}
    )
    html = render_document_html(
        code="ADVANCE_RECEIPT",
        context=sample_context("ADVANCE_RECEIPT"),
        layout_raw=layout,
        bill_format="A4",
    )
    assert "Pay at counter" in html
    assert "ADV-18" in html


def test_dragged_boxes_survive_normalize_and_print_on_half_page():
    layout = default_document_layout("OPD_BILL")
    layout["custom_pages"] = {"CUSTOM_HALF": {"name": "Half page", "width_mm": 74, "height_mm": 105}}
    layout["formats"]["CUSTOM_HALF"] = layout["formats"]["A4"]
    layout["page"]["CUSTOM_HALF"] = {"orientation": "portrait"}
    meta = layout["formats"]["CUSTOM_HALF"]["meta"]
    for field in meta:
        if not field.get("visible"):
            continue
        field["x_mm"] = 2
        field["y_mm"] = 1
        field["width_mm"] = 34
        field["height_mm"] = 5
        field["font_size_pt"] = 8
    normalized = normalize_layout("OPD_BILL", layout)
    saved = next(field for field in normalized["formats"]["CUSTOM_HALF"]["meta"] if field["id"] == "patient_name")
    assert saved["x_mm"] == 2.0
    assert saved["width_mm"] == 34.0
    assert saved["font_size_pt"] == 8.0
    html = render_document_html(
        code="OPD_BILL",
        context=sample_context("OPD_BILL"),
        layout_raw=normalized,
        bill_format="CUSTOM_HALF",
    )
    assert "data-page-w='74.0'" in html
    assert "data-page-h='105.0'" in html
    assert "Anita Rao" in html
    assert "font-size:8pt" in html
