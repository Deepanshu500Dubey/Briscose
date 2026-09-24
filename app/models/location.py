"""Location model — a single Briscoes store/site.

Locations are multi-tenant from day one (see the project blueprint's
Section 0 decision log): managers and employees are scoped to one or more
locations via the ManagerLocation / EmployeeLocation join tables.
"""
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    # IANA timezone name (e.g. "Australia/Sydney"). All timestamps are
    # persisted in UTC; this is what renders them in the store's local time.
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
