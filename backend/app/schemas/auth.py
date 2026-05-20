"""Схемы для аутентификации и админских операций."""

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# -------------------- Admin --------------------

class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = ""
    role: str  # 'admin' | 'lead'
    password: str


class UserUpdateRequest(BaseModel):
    """Частичное обновление: только присланные поля."""
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordResetRequest(BaseModel):
    new_password: str


class ConfigTransferRequest(BaseModel):
    """Перепривязать конфиг к другому пользователю."""
    new_owner_user_id: int
