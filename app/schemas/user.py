"""Request/response schemas for user provisioning & listing.

Accounts are provisioned by a Manager or Admin — see app/api/users.py and
the project blueprint, Section 9 — never created via self-signup.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EMPLOYEE
    home_location_id: uuid.UUID | None = None
    # Convenience: immediately scope the new account to one or more
    # locations (employee_locations for an employee, manager_locations for
    # a manager) in the same request, instead of a separate call.
    location_ids: list[uuid.UUID] = Field(default_factory=list)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    home_location_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
