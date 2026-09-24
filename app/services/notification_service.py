"""Notification creation helpers (project blueprint, Section 7 & 10)."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.manager_location import ManagerLocation
from app.models.notification import Notification, NotificationType


def notify(
    db: Session,
    user_id: uuid.UUID,
    notification_type: NotificationType | str,
    shift_id: uuid.UUID | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id, type=NotificationType(notification_type), shift_id=shift_id
        )
    )
    db.flush()


def notify_managers_of_location(
    db: Session,
    location_id: uuid.UUID,
    notification_type: NotificationType | str,
    shift_id: uuid.UUID | None = None,
) -> None:
    manager_ids = db.scalars(
        select(ManagerLocation.manager_id).where(ManagerLocation.location_id == location_id)
    ).all()
    for manager_id in manager_ids:
        notify(db, manager_id, notification_type, shift_id)
