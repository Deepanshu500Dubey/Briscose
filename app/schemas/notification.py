"""Request/response schemas for notifications."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    shift_id: uuid.UUID | None
    is_read: bool
    created_at: datetime
