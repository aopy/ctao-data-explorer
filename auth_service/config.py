from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

from pydantic import Field, model_validator
from pydantic.aliases import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            (".env.ci", ".env", ".env.local") if os.getenv("PREFER_DOTENV", "1") == "1" else None
        ),
        case_sensitive=False,
        extra="ignore",
    )

    AUTH_DATABASE_URL: str
    AUTH_REDIS_URL: str

    BASE_URL: str | None = None
    FRONTEND_BASE_URL: str | None = None

    REFRESH_TOKEN_ENCRYPTION_KEY: str = ""
    SESSION_DURATION_SECONDS: int = 3600 * 8
    REFRESH_BUFFER_SECONDS: int = 300

    COOKIE_SAMESITE: str = "Lax"
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None

    SESSION_SECRET_KEY_OIDC: str = "change_me_in_prod"

    # OIDC (auth-service only)
    CTAO_CLIENT_ID: str
    CTAO_CLIENT_SECRET: str
    OIDC_ISSUER: str
    OIDC_REDIRECT_URI: str
    OIDC_FAKE_EXPIRES_IN: int | None = None
    OIDC_SERVER_METADATA_URL: str | None = None

    # misc
    LOG_LEVEL: str = "INFO"
    LOG_INCLUDE_ACCESS: bool = True
    LOG_JSON: bool = False
    ENABLE_DOCS: bool = False
    METRICS_ENABLED: bool = False
    METRICS_ROUTE: str = "/metrics"

    TOKEN_RELAY_TARGETS_JSON: str = Field(
        default="{}",
        validation_alias=AliasChoices(
            "AUTH_TOKEN_RELAY_TARGETS_JSON",
            "TOKEN_RELAY_TARGETS_JSON",
        ),
    )
    TOKEN_RELAY_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "AUTH_TOKEN_RELAY_TIMEOUT_SECONDS",
            "TOKEN_RELAY_TIMEOUT_SECONDS",
        ),
    )

    @property
    def DATABASE_URL(self) -> str:
        return self.AUTH_DATABASE_URL

    @property
    def REDIS_URL(self) -> str:
        return self.AUTH_REDIS_URL

    @property
    def cookie_params(self) -> dict[str, Any]:
        samesite = self.COOKIE_SAMESITE.capitalize()
        if samesite.lower() == "none" and not self.COOKIE_SECURE:
            samesite = "Lax"
        params: dict[str, Any] = {
            "secure": self.COOKIE_SECURE,
            "httponly": True,
            "samesite": samesite,
            "path": "/",
        }
        if self.COOKIE_DOMAIN:
            params["domain"] = self.COOKIE_DOMAIN
        return params

    @property
    def token_relay_targets(self) -> dict[str, str]:
        try:
            obj = json.loads(self.TOKEN_RELAY_TARGETS_JSON or "{}")
            if not isinstance(obj, dict):
                return {}
            return {str(k): str(v).rstrip("/") for k, v in obj.items()}
        except Exception:
            logger.exception("Invalid TOKEN_RELAY_TARGETS_JSON")
            return {}

    @model_validator(mode="after")
    def _validate_secure_cookie_requires_secret(self):
        if self.COOKIE_SECURE and self.SESSION_SECRET_KEY_OIDC in ("", "change_me_in_prod"):
            raise ValueError("SESSION_SECRET_KEY_OIDC must be set when COOKIE_SECURE is true")
        return self


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
