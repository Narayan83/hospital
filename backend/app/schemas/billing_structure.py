from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.billing_type import BillingTypeRead
from app.schemas.common import ORMModel
from app.schemas.department import DepartmentRead
from app.schemas.procedure_type import ProcedureTypeRead


class BillingStructureCreate(BaseModel):
    billing_type_id: str
    department_id: str
    procedure_type_id: str
    sort_order: int = 0
    is_active: bool = True


class BillingStructureUpdate(BaseModel):
    sort_order: int | None = None
    is_active: bool | None = None


class BillingStructureRead(ORMModel):
    id: str
    billing_type_id: str
    department_id: str
    procedure_type_id: str
    billing_type_code: str | None = None
    billing_type_name: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    procedure_type_code: str | None = None
    procedure_type_name: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BillingStructureDepartmentNode(BaseModel):
    department: DepartmentRead
    procedure_types: list[ProcedureTypeRead]


class BillingStructureTreeNode(BaseModel):
    billing_type: BillingTypeRead
    departments: list[BillingStructureDepartmentNode]
