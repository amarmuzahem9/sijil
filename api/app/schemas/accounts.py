"""Account management bodies (specs/002 contracts/api.md).

Types only: length rules live in account_service so each failure returns its own code
(`invalid_name`, `weak_password`, `invalid_phone`) instead of the generic validation_error.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: str
    permissions: list[str]
    is_active: bool
    must_change_password: bool
    created_at: datetime


class AccountList(BaseModel):
    items: list[AccountOut]


class MarketerCreate(_Body):
    name: str
    phone: str
    temporary_password: str


class AdminCreate(MarketerCreate):
    permissions: list[str] = []


class MarketerUpdate(_Body):
    name: str | None = None
    phone: str | None = None


class AdminUpdate(MarketerUpdate):
    permissions: list[str] | None = None


class ResetPasswordBody(_Body):
    temporary_password: str


class NameUpdate(_Body):
    name: str


class PersonOut(BaseModel):
    id: int
    name: str
    role: str


class ArchivedAccountOut(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    permissions: list[str]
    archived_at: datetime
    archived_by: PersonOut | None


class ArchivedList(BaseModel):
    items: list[ArchivedAccountOut]
