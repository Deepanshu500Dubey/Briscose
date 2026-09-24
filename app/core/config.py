"""Centralized, environment-based application configuration."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-me"
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    APP_NAME: str = "briscoes"

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Clock in/out grace window either side of a shift's start/end (Section 10).
    CLOCK_GRACE_MINUTES: int = 15

    # Comma-separated allowed origins for CORS. Empty by default because
    # local dev doesn't need it at all — the Vite dev proxy (vite.config.ts)
    # makes frontend requests same-origin. Only a split-service deployment
    # (frontend and backend on different hosts, e.g. two Cloud Run services)
    # needs this set.
    CORS_ORIGINS: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _refuse_insecure_secret_in_production(self) -> "Settings":
        """The README's own default JWT_SECRET_KEY ("change-me") is fine for
        local dev but must never reach a real deployment. This is a
        deliberately loud, fail-at-startup check rather than a runtime
        warning — a weak signing key is a total auth bypass, not a
        degraded-mode issue."""
        if self.APP_ENV.lower() in ("production", "prod"):
            if self.JWT_SECRET_KEY == _INSECURE_DEFAULT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY is still the insecure default ('change-me') "
                    "with APP_ENV=production. Set a strong, unique secret "
                    "(e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`)."
                )
            if len(self.JWT_SECRET_KEY) < _MIN_SECRET_LENGTH:
                raise ValueError(
                    f"JWT_SECRET_KEY is only {len(self.JWT_SECRET_KEY)} characters with "
                    f"APP_ENV=production — use at least {_MIN_SECRET_LENGTH}."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()


settings = get_settings()
