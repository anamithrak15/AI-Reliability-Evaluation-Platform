from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _check_length(password: str) -> str:
    minimum = get_settings().password_min_length
    if len(password) < minimum:
        raise ValueError(f"password must be at least {minimum} characters")
    return password


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def _lower(cls, email: str) -> str:
        return _normalise_email(email)


class RegisterIn(Credentials):
    @field_validator("password")
    @classmethod
    def _long_enough(cls, password: str) -> str:
        return _check_length(password)


class LoginIn(Credentials):
    pass


class EmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _lower(cls, email: str) -> str:
        return _normalise_email(email)


class TokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=2000)


class ResetPasswordIn(TokenIn):
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def _long_enough(cls, password: str) -> str:
        return _check_length(password)


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def _long_enough(cls, password: str) -> str:
        return _check_length(password)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
    email_verified_at: datetime | None = None
