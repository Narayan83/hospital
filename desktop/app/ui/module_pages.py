"""Factory for HMS module screens (shared by main window and modal shortcuts)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.ui.module_registry import MODULE_ALIASES

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from app.api_client.client import ApiClient
    from app.controllers.patient_controller import PatientController


def create_module_widget(
    module_id: str,
    *,
    api: ApiClient,
    controller: PatientController | None = None,
    on_navigate: Callable[[str], None] | None = None,
    logout_callback: Callable[[], None] | None = None,
) -> QWidget | None:
    module_id = MODULE_ALIASES.get(module_id, module_id)
    navigate = on_navigate or (lambda _mid: None)

    if module_id == "patient_master":
        from app.ui.widgets.patient_registration import PatientRegistrationWidget

        if controller is None:
            return None
        return PatientRegistrationWidget(controller)
    if module_id == "patient_list":
        from app.ui.widgets.patient_list import PatientListWidget

        if controller is None:
            return None
        return PatientListWidget(controller)
    if module_id == "patient_service_creation":
        from app.ui.widgets.patient_service_master import PatientServiceMasterWidget

        return PatientServiceMasterWidget(api)
    if module_id == "doctor_master":
        from app.ui.widgets.doctor_master import DoctorMasterWidget

        return DoctorMasterWidget(api)
    if module_id == "department_master":
        from app.ui.widgets.department_master import DepartmentMasterWidget

        return DepartmentMasterWidget(api)
    if module_id == "user_addition_modification":
        from app.ui.widgets.user_registration_admin import UserRegistrationAdminWidget

        return UserRegistrationAdminWidget(api)
    if module_id == "user_type_creation":
        from app.ui.widgets.user_type_master import UserTypeMasterWidget

        return UserTypeMasterWidget(api)
    if module_id == "bill_types_creation":
        from app.ui.widgets.billing_type_master import BillingTypeMasterWidget

        return BillingTypeMasterWidget(api)
    if module_id == "authority_creation_master":
        from app.ui.widgets.authority_master import AuthorityMasterWidget

        return AuthorityMasterWidget(api)
    if module_id == "letter_master":
        from app.ui.widgets.letter_master import LetterMasterWidget

        return LetterMasterWidget(api)
    if module_id == "print_master":
        from app.ui.widgets.print_master import PrintMasterWidget

        return PrintMasterWidget(api, on_navigate=navigate)
    if module_id == "ledger_master":
        from app.ui.widgets.ledger_master import LedgerMasterWidget

        return LedgerMasterWidget(api)
    if module_id == "cashbook":
        from app.ui.widgets.cashbook import CashbookWidget

        return CashbookWidget(api)
    if module_id == "advance_collection":
        from app.ui.widgets.advance_collection import AdvanceCollectionWidget

        return AdvanceCollectionWidget(api)
    if module_id == "advance_reprint":
        from app.ui.widgets.advance_reprint import AdvanceReprintWidget

        return AdvanceReprintWidget(api)
    if module_id == "adjustment_entry":
        from app.ui.widgets.payment_voucher import PaymentVoucherWidget

        return PaymentVoucherWidget(api)
    if module_id == "receipt_voucher_adjustment_entry":
        from app.ui.widgets.contra_entry import ContraEntryWidget

        return ContraEntryWidget(api)
    if module_id == "ledger_details":
        from app.ui.widgets.accounting_reports import LedgerDetailsWidget

        return LedgerDetailsWidget(api)
    if module_id == "cash_book":
        from app.ui.widgets.accounting_reports import AccountingRegisterWidget

        return AccountingRegisterWidget(api, mode="cash_book")
    if module_id == "daybook":
        from app.ui.widgets.accounting_reports import AccountingRegisterWidget

        return AccountingRegisterWidget(api, mode="daybook")
    if module_id == "short_bill_master":
        from app.ui.widgets.short_bill_master import ShortBillMasterWidget

        return ShortBillMasterWidget(api)
    if module_id == "single_service_opd_setup":
        from app.ui.widgets.single_service_opd_setup import SingleServiceOpdSetupWidget

        return SingleServiceOpdSetupWidget(api)
    if module_id.startswith("sso_"):
        from app.ui.widgets.single_service_opd_bill import SingleServiceOpdBillWidget

        return SingleServiceOpdBillWidget(api, menu_code=module_id)
    if module_id.startswith("sbt_") or module_id in (
        "scan_bill",
        "xray_bill",
        "observation_bill",
        "immunization_bill",
    ):
        from app.ui.widgets.short_bill_transaction import ShortBillTransactionWidget

        return ShortBillTransactionWidget(api, menu_code=module_id)
    if module_id == "form_3c_report":
        from app.ui.widgets.form_3c_report import Form3CReportWidget

        return Form3CReportWidget(api)
    if module_id == "cancellation_bill_report":
        from app.ui.widgets.cancellation_bill_report import CancellationBillReportWidget

        return CancellationBillReportWidget(api)
    if module_id == "modification_bill_report":
        from app.ui.widgets.modification_bill_report import ModificationBillReportWidget

        return ModificationBillReportWidget(api)
    if module_id == "user_wise_cash_transaction_report":
        from app.ui.widgets.user_wise_cash_transaction_report import (
            UserWiseCashTransactionReportWidget,
        )

        return UserWiseCashTransactionReportWidget(api)
    if module_id == "doctor_wise_collection_report":
        from app.ui.widgets.doctor_wise_collection_report import (
            DoctorWiseCollectionReportWidget,
        )

        return DoctorWiseCollectionReportWidget(api)
    if module_id == "pathology_doctor_wise_collection_report":
        from app.ui.widgets.pathology_doctor_wise_collection_report import (
            PathologyDoctorWiseCollectionReportWidget,
        )

        return PathologyDoctorWiseCollectionReportWidget(api)
    if module_id == "hospital_profile":
        from app.ui.widgets.hospital_profile import HospitalProfileWidget

        return HospitalProfileWidget(api)
    if module_id == "dashboard_shortcut_setup":
        from app.ui.widgets.dashboard_shortcut_setup import DashboardShortcutSetupWidget

        return DashboardShortcutSetupWidget(api)
    if module_id == "print_template_designer":
        from app.ui.widgets.bill_template_designer import BillTemplateDesignerWidget

        return BillTemplateDesignerWidget(api)
    if module_id == "database_migration":
        from app.ui.widgets.database_migration import DatabaseMigrationWidget

        return DatabaseMigrationWidget(api)
    if module_id == "hospital_sections":
        from app.ui.widgets.hospital_section_master import HospitalSectionMasterWidget

        return HospitalSectionMasterWidget(api)
    if module_id == "prefix_creation":
        from app.ui.widgets.prefix_master import PrefixMasterWidget

        return PrefixMasterWidget(api)
    if module_id == "patient_id_format":
        from app.ui.widgets.patient_no_format_master import PatientNoFormatMasterWidget

        return PatientNoFormatMasterWidget(api)
    if module_id == "payment_mode_creation":
        from app.ui.widgets.payment_mode_master import PaymentModeMasterWidget

        return PaymentModeMasterWidget(api)
    if module_id == "procedure_type_master":
        from app.ui.widgets.procedure_type_master import ProcedureTypeMasterWidget

        return ProcedureTypeMasterWidget(api)
    if module_id == "billing_structure_mapping":
        from app.ui.widgets.billing_structure_mapping import BillingStructureMappingWidget

        return BillingStructureMappingWidget(api)
    if module_id == "billing":
        from app.ui.widgets.billing_hub import BillingHubWidget

        return BillingHubWidget(on_navigate=navigate)
    if module_id == "service_category_master":
        from app.ui.widgets.service_category_master import ServiceCategoryMasterWidget

        return ServiceCategoryMasterWidget(api)
    if module_id == "package_creation_master":
        from app.ui.widgets.package_master import PackageMasterWidget

        return PackageMasterWidget(api)
    if module_id == "assign_services_to_package":
        from app.ui.widgets.package_service_mapping import PackageServiceMappingWidget

        return PackageServiceMappingWidget(api)
    if module_id == "service_sub_category_master":
        from app.ui.widgets.service_sub_category_master import ServiceSubCategoryMasterWidget

        return ServiceSubCategoryMasterWidget(api)
    if module_id == "opd_bill":
        from app.ui.widgets.opd_bill import OpdBillWidget

        return OpdBillWidget(api, on_navigate=navigate)
    if module_id == "opd_bill_reprint":
        from app.ui.widgets.opd_bill_reprint import OpdBillReprintWidget

        return OpdBillReprintWidget(api, on_navigate=navigate)
    if module_id == "ipd_bill_reprint":
        from app.ui.widgets.ipd_bill_reprint import IpdBillReprintWidget

        return IpdBillReprintWidget(api, on_navigate=navigate)
    if module_id == "modify_bill":
        from app.ui.widgets.modify_bill import BillModifyWidget

        return BillModifyWidget(api, on_navigate=navigate)
    if module_id == "cancel_bill":
        from app.ui.widgets.cancel_bill import CancelBillWidget

        return CancelBillWidget(api, on_navigate=navigate)
    if module_id == "change_patient_doctor":
        from app.ui.widgets.change_patient_doctor import ChangePatientDoctorWidget

        return ChangePatientDoctorWidget(api, on_navigate=navigate)
    if module_id == "opd_bill_modification":
        from app.ui.widgets.opd_bill_modify import OpdBillModifyWidget

        return OpdBillModifyWidget(api, on_navigate=navigate)
    if module_id == "ipd_bill_modification":
        from app.ui.widgets.ipd_bill_modify import IpdBillModifyWidget

        return IpdBillModifyWidget(api, on_navigate=navigate)
    if module_id == "in_patient_admission":
        from app.ui.widgets.ipd_admission import IpdAdmissionWidget

        return IpdAdmissionWidget(api, on_navigate=navigate)
    if module_id == "ipd_bill":
        from app.ui.widgets.ipd_bill import IpdBillWidget

        return IpdBillWidget(api, on_navigate=navigate)
    if module_id == "in_patient_discharge":
        from app.ui.widgets.ipd_discharge import IpdDischargeWidget

        return IpdDischargeWidget(api, on_navigate=navigate)
    if module_id == "diagnose_management":
        from app.ui.widgets.discharge_summary import DischargeSummaryWidget

        return DischargeSummaryWidget(api, on_navigate=navigate)
    if module_id == "pathology_bill":
        from app.ui.widgets.pathology_bill import PathologyBillWidget

        return PathologyBillWidget(api, on_navigate=navigate)
    if module_id == "pathology_bill_reprint":
        from app.ui.widgets.pathology_bill_reprint import PathologyBillReprintWidget

        return PathologyBillReprintWidget(api, on_navigate=navigate)
    if module_id == "pathology_bill_cancel":
        from app.ui.widgets.pathology_bill_cancel import PathologyBillCancelWidget

        return PathologyBillCancelWidget(api, on_navigate=navigate)
    if module_id == "pathology_bill_modification":
        from app.ui.widgets.pathology_bill_modify import PathologyBillModifyWidget

        return PathologyBillModifyWidget(api, on_navigate=navigate)
    if module_id == "pathology_work_list":
        from app.ui.widgets.pathology_work_list import PathologyWorkListWidget

        return PathologyWorkListWidget(api, on_navigate=navigate)
    if module_id == "patient_history_opd":
        from app.ui.widgets.patient_history_opd import PatientHistoryOpdWidget

        return PatientHistoryOpdWidget(api)
    if module_id == "scanning_patient_documents":
        from app.ui.widgets.scanning_patient_documents import ScanningPatientDocumentsWidget

        return ScanningPatientDocumentsWidget(api)
    if module_id == "unit_creation":
        from app.ui.widgets.pathology_unit_master import PathologyUnitMasterWidget

        return PathologyUnitMasterWidget(api)
    if module_id == "parameter_mapping":
        from app.ui.widgets.pathology_test_profile import PathologyTestProfileWidget

        return PathologyTestProfileWidget(api)
    if module_id == "normal_range_creation":
        from app.ui.widgets.pathology_normal_range_master import PathologyNormalRangeMasterWidget

        return PathologyNormalRangeMasterWidget(api)
    if module_id == "custom_template_creation":
        from app.ui.widgets.pathology_custom_template import PathologyCustomTemplateWidget

        return PathologyCustomTemplateWidget(api)
    if module_id == "pathology_notes_master":
        from app.ui.widgets.notes_master import NotesMasterWidget

        return NotesMasterWidget(api)
    if module_id == "service_creation_pathology":
        from app.ui.widgets.pathology_service_master import PathologyServiceMasterWidget

        return PathologyServiceMasterWidget(api)
    if module_id == "ward_master":
        from app.ui.widgets.ward_master import WardMasterWidget

        return WardMasterWidget(api)
    if module_id == "role_management":
        from app.ui.widgets.role_management import RoleManagementWidget

        return RoleManagementWidget(api)
    if module_id == "role_menu_permissions":
        from app.ui.widgets.role_menu_permissions import RoleMenuPermissionsWidget

        return RoleMenuPermissionsWidget(api)
    if module_id == "user_role_mapping":
        from app.ui.widgets.user_role_mapping import UserRoleMappingWidget

        return UserRoleMappingWidget(api)
    if module_id == "notification_setup":
        from app.ui.widgets.notification_setup import NotificationSetupWidget

        return NotificationSetupWidget(api)
    if module_id == "medical_shop":
        from app.ui.widgets.medical_shop_hub import MedicalShopHubWidget

        return MedicalShopHubWidget(on_navigate=navigate)
    if module_id == "medicine_master":
        from app.ui.widgets.pharmacy_item_master import PharmacyItemMasterWidget

        return PharmacyItemMasterWidget(api, "MD", "Medicine Master")
    if module_id == "surgicals_master":
        from app.ui.widgets.pharmacy_item_master import PharmacyItemMasterWidget

        return PharmacyItemMasterWidget(api, "SG", "Surgicals Master")
    if module_id == "disposables_master":
        from app.ui.widgets.pharmacy_item_master import PharmacyItemMasterWidget

        return PharmacyItemMasterWidget(api, "DS", "Disposables Master")
    if module_id == "consumables_master":
        from app.ui.widgets.pharmacy_item_master import PharmacyItemMasterWidget

        return PharmacyItemMasterWidget(api, "CS", "Consumables Master")
    if module_id == "implants_master":
        from app.ui.widgets.pharmacy_item_master import PharmacyItemMasterWidget

        return PharmacyItemMasterWidget(api, "IM", "Implants Master")
    if module_id == "manufacturer_master":
        from app.ui.widgets.pharmacy_code_master import PharmacyCodeMasterWidget

        return PharmacyCodeMasterWidget(api, "MF", "Manufacturer Master")
    if module_id == "marketing_agency_master":
        from app.ui.widgets.pharmacy_code_master import PharmacyCodeMasterWidget

        return PharmacyCodeMasterWidget(api, "MK", "Marketing Agency Master")
    if module_id == "distributors_master":
        from app.ui.widgets.pharmacy_code_master import PharmacyCodeMasterWidget

        return PharmacyCodeMasterWidget(api, "DM", "Distributors Master")
    if module_id == "drug_category_master":
        from app.ui.widgets.pharmacy_code_master import PharmacyCodeMasterWidget

        return PharmacyCodeMasterWidget(api, "DC", "Drug Category Master")
    if module_id == "medicine_group_creation":
        from app.ui.widgets.pharmacy_code_master import PharmacyCodeMasterWidget

        return PharmacyCodeMasterWidget(api, "MG", "Medicine Group Creation")
    if module_id == "supplier_master":
        from app.ui.widgets.pharmacy_supplier_master import PharmacySupplierMasterWidget

        return PharmacySupplierMasterWidget(api)
    if module_id == "assign_medicine_to_group":
        from app.ui.widgets.pharmacy_group_mapping import PharmacyGroupMappingWidget

        return PharmacyGroupMappingWidget(api)
    if module_id == "medicine_sale_bill":
        from app.ui.widgets.pharmacy_sale_bill import PharmacySaleBillWidget

        return PharmacySaleBillWidget(api, on_navigate=navigate)
    if module_id in {"medicine_purchase_bill_109", "medicine_purchase_bill"}:
        from app.ui.widgets.pharmacy_purchase_bill import PharmacyPurchaseBillWidget

        return PharmacyPurchaseBillWidget(api, on_navigate=navigate)
    if module_id == "medicine_purchase_return":
        from app.ui.widgets.pharmacy_purchase_return import PharmacyPurchaseReturnWidget

        return PharmacyPurchaseReturnWidget(api, on_navigate=navigate)
    if module_id == "medicine_indent":
        from app.ui.widgets.pharmacy_medicine_indent import PharmacyMedicineIndentWidget

        return PharmacyMedicineIndentWidget(api, on_navigate=navigate)
    if module_id in {
        "sales_register",
        "sales_summary",
        "schedule_h_drug_report",
        "consolidated_stock_report",
    }:
        from app.ui.widgets.pharmacy_reports import PharmacyReportsWidget

        return PharmacyReportsWidget(api, module_id)
    if module_id == "settings":
        from app.ui.widgets.profile_settings import SettingsWidget

        return SettingsWidget()
    if module_id == "profile":
        from app.ui.widgets.profile_settings import ProfileWidget

        widget = ProfileWidget()
        if logout_callback is not None:
            widget.logout_requested.connect(logout_callback)
        return widget
    if module_id == "notifications":
        from app.ui.widgets.profile_settings import NotificationsWidget

        return NotificationsWidget()
    return None
