from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.api_client.client import ApiClient, ApiError
from app.ui.widgets.bill_modify_search import PatientBillSearchPanel
from app.ui.widgets.ipd_discharge import IpdDischargeWidget


def _ipd_bill_row(bill: dict) -> list[str]:
    return [
        bill.get("bill_no") or "",
        str(bill.get("discharge_date") or bill.get("bill_date") or ""),
        bill.get("admission_no") or "—",
        bill.get("ward_name") or "—",
        f"{float(bill.get('net_amount') or 0):.2f}",
        str(bill.get("stay_days") or "—"),
        bill.get("payment_mode_name") or "—",
    ]


class IpdBillModifyWidget(QWidget):
    def __init__(self, api: ApiClient, on_navigate: Callable[[str], None] | None = None):
        super().__init__()
        self.api = api
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._search = PatientBillSearchPanel(
            api,
            title="IPD Bill Modification",
            hint="Enter patient id, select a discharge bill, then add/remove services and change payment modes.",
            list_bills=lambda patient_no: api.list_ipd_discharges_by_patient(patient_no=patient_no),
            bill_columns=[
                "Bill No",
                "Discharge Date",
                "Admission No",
                "Ward",
                "Net Amount",
                "Stay Days",
                "Payment",
            ],
            bill_row_values=_ipd_bill_row,
        )
        self._search.bill_selected.connect(self._open_bill_editor)
        self._stack.addWidget(self._search)

        editor_host = QWidget()
        editor_layout = QVBoxLayout(editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(4)
        back_row = QHBoxLayout()
        back_btn = QPushButton("← Back to Bill List")
        back_btn.clicked.connect(self._show_search)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        editor_layout.addLayout(back_row)
        self._editor = IpdDischargeWidget(api, on_navigate, modification_mode=True)
        editor_layout.addWidget(self._editor, stretch=1)
        self._stack.addWidget(editor_host)
        layout.addWidget(self._stack)

    def _show_search(self) -> None:
        self._stack.setCurrentIndex(0)

    def _open_bill_editor(self, summary: dict) -> None:
        bill_id = summary.get("id")
        if not bill_id:
            return
        try:
            bill = self.api.get_ipd_discharge(bill_id)
        except ApiError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Open Bill", str(exc))
            return
        self._editor.load_bill_for_modification(bill)
        self._stack.setCurrentIndex(1)

    def refresh(self) -> None:
        self._editor.refresh()

    def on_module_deactivated(self) -> None:
        self._stack.setCurrentIndex(0)
        self._search.reset_state()
        if hasattr(self._editor, "_clear_form"):
            self._editor._clear_form()
