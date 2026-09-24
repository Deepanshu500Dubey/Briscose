"""Request/response schemas for shift assignments."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.shift_assignment import AssignmentStatus


class CreateAssignmentRequest(BaseModel):
    employee_id: uuid.UUID


class WithdrawAssignmentRequest(BaseModel):
    # Required to withdraw an ACCEPTED assignment — see the project
    # blueprint, Section 8: withdrawing an accepted row can drop a shift
    # below min_staff and un-publish it from the roster.
    confirm: bool = False


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shift_id: uuid.UUID
    employee_id: uuid.UUID
    status: AssignmentStatus
    offered_by: uuid.UUID | None
    offered_at: datetime
    responded_at: datetime | None
