import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_email_format(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip().lower()

    if not value:
        return None

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    if not re.fullmatch(pattern, value):
        raise ValueError("Enter a valid email address.")

    return value


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Customer name must contain at least 2 characters.")

        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return validate_email_format(value)


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if len(value) < 2:
            raise ValueError("Customer name must contain at least 2 characters.")

        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return validate_email_format(value)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str | None
    phone: str | None
    company: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
