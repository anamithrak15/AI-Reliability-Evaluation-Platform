from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings


def _normalise_email(value: str) -> str:
    return value.strip().lower()


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
        minimum = get_settings().password_min_length
        if len(password) < minimum:
            raise ValueError(f"password must be at least {minimum} characters")
        return password


class LoginIn(Credentials):
    pass


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
