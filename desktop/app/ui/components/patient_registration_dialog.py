from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from app.api_client.client import ApiClient
from app.controllers.patient_controller import PatientController
from app.ui.responsive_layout import fit_dialog_size
from app.ui.styles import apply_form_field_style
from app.ui.widgets.patient_registration import PatientRegistrationWidget


class PatientRegistrationDialog(QDialog):
    """Modal patient form for billing/list screens — does not change the main page.

    Pass ``patient`` to open in edit mode pre-filled with that record; otherwise
    the dialog opens a blank new-patient form.
    """

    def __init__(
        self,
        controller: PatientController,
        parent: QWidget | None = None,
        patient: dict | None = None,
    ):
        super().__init__(parent)
        self._saved_patient: dict | None = None
        is_edit = patient is not None
        self.setWindowTitle("Edit Patient" if is_edit else "New Patient Registration")
        self.resize(*fit_dialog_size(1020, 720))
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.form = PatientRegistrationWidget(controller)
        self.form.patient_saved.connect(self._on_patient_saved)
        if is_edit:
            self.form.refresh()
            self.form.load_for_edit(patient)
        else:
            self.form.prepare_for_new()
        layout.addWidget(self.form, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_form_field_style(self)

    def _on_patient_saved(self, patient: dict) -> None:
        self._saved_patient = patient
        self.accept()

    def saved_patient(self) -> dict | None:
        return self._saved_patient


def register_patient_dialog(api: ApiClient, parent: QWidget | None = None) -> dict | None:
    """Open patient registration as a modal. Returns saved patient dict, or None if cancelled."""
    dialog = PatientRegistrationDialog(PatientController(api), parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.saved_patient()
    return None


def edit_patient_dialog(
    api: ApiClient, patient: dict, parent: QWidget | None = None
) -> dict | None:
    """Open the patient form pre-filled for editing. Returns the updated patient, or None."""
    dialog = PatientRegistrationDialog(PatientController(api), parent, patient=patient)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.saved_patient()
    return None
