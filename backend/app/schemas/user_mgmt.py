from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=20)
    user_type_id: str
    doctor_id: str | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=20)
    user_type_id: str | None = None
    doctor_id: str | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6)


class UserRead(ORMModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    user_type_id: str | None
    user_type_code: str | None = None
    user_type_name: str | None = None
    doctor_id: str | None
    doctor_name: str | None = None
    is_active: bool
    roles: list[str] = []
    created_at: datetime
    updated_at: datetime


class UserRoleAssign(BaseModel):
    user_id: str
    role_id: str
    priority: int = 1


class UserRoleMappingRead(ORMModel):
    id: str
    user_id: str
    role_id: str
    role_name: str
    priority: int
    created_at: datetime


class NotificationSetupItem(BaseModel):
    user_id: str
    is_enabled: bool = True


class NotificationSetupBulk(BaseModel):
    event_code: str = Field(..., min_length=2, max_length=80)
    recipients: list[NotificationSetupItem]
