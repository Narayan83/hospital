from pydantic import BaseModel, EmailStr, Field

from app.schemas.app_data import AppDataResponse
from app.schemas.menu import MenuTreeNode


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None = None
    roles: list[str]
    doctor_id: str | None = None
    maps_to_doctor: bool = False
    user_type_sort_order: int | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    menus: list[MenuTreeNode]
    app_data: AppDataResponse
