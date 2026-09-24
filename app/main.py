"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.assignments import router as assignments_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.availability import router as availability_router
from app.api.locations import router as locations_router
from app.api.notifications import router as notifications_router
from app.api.shifts import router as shifts_router
from app.api.time_entries import router as time_entries_router
from app.api.timesheets import router as timesheets_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.rate_limit import limiter

app = FastAPI(title=f"{settings.APP_NAME} API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Only added when CORS_ORIGINS is actually set (see app/core/config.py) — a
# same-origin deployment behind the dev proxy or a single reverse proxy
# needs none of this.
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(availability_router)
app.include_router(locations_router)
app.include_router(users_router)
app.include_router(shifts_router)
app.include_router(assignments_router)
app.include_router(notifications_router)
app.include_router(time_entries_router)
app.include_router(timesheets_router)
app.include_router(dashboard_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
