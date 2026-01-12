import os
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OPUS_SERVICE = "https://example.invalid/opus"


def _require_nonempty(val: str | None, name: str) -> None:
    if not (val and val.strip()):
        raise ValueError(f"{name} must be set in PRODUCTION")


def _ensure_https_url(url: str, what: str) -> None:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme and scheme != "https":
        raise ValueError(f"{what} must use https in PRODUCTION")
    if parsed.hostname == "example.invalid":
        raise ValueError(f"{what} must be set in PRODUCTION (not example.invalid)")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            (".env.ci", ".env", ".env.local") if os.getenv("PREFER_DOTENV", "1") == "1" else None
        ),
        case_sensitive=False,
        extra="ignore",
    )

    # App / cookies
    BASE_URL: str | None = None
    FRONTEND_BASE_URL: str | None = None
    COOKIE_SAMESITE: str = "Lax"
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None
    SESSION_DURATION_SECONDS: int = 3600 * 8
    REFRESH_BUFFER_SECONDS: int = 300
    SESSION_SECRET_KEY_OIDC: str = "a_different_strong_secret_for_oidc_state"

    # Data stores / crypto
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@127.0.0.1:5432/mydb"
    REDIS_URL: str = "redis://localhost:6379/0"
    REFRESH_TOKEN_ENCRYPTION_KEY: str = ""

    # External services
    SIMBAD_TAP_SYNC: str = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
    NED_OBJECT_LOOKUP_URL: str = "https://ned.ipac.caltech.edu/srs/ObjectLookup"
    SIMBAD_TAP_BASE: str = "https://simbad.cds.unistra.fr/simbad/sim-tap"
    NED_TAP_SYNC_URL: str = "https://ned.ipac.caltech.edu/tap/sync"

    # TAP defaults
    DEFAULT_TAP_URL: str = "http://voparis-tap-he.obspm.fr/tap"
    DEFAULT_OBSCORE_TABLE: str = "hess_dr.obscore_sdc"
    DEFAULT_SELECT_LIMIT: int = 100

    # OIDC / OAuth
    OIDC_SERVER_METADATA_URL: str = (
        "https://iam-ctao.cloud.cnaf.infn.it/.well-known/openid-configuration"
    )
    CTAO_CLIENT_ID: str | None = None
    CTAO_CLIENT_SECRET: str | None = None
    OIDC_REDIRECT_URI: str | None = None
    OIDC_FAKE_EXPIRES_IN: int | None = None

    JWT_SECRET: str | None = None
    DB_URL: str | None = None
    NODE_OPTIONS: str | None = None

    # Logs
    LOG_LEVEL: str = "INFO"
    LOG_INCLUDE_ACCESS: bool = True
    LOG_JSON: bool = False

    # Docs
    ENABLE_DOCS: bool = False

    # OPUS / UWS  — safe defaults for CI
    OPUS_ROOT: str = "https://voparis-uws-test.obspm.fr"
    OPUS_SERVICE: str = Field(
        default=DEFAULT_OPUS_SERVICE,
        description="Base OPUS service URL. Override via env in all real deployments.",
    )
    OPUS_APP_TOKEN: str = Field(default="", description="OPUS app token")
    OPUS_APP_USER: str = Field(default="ctao", description="OPUS app username")

    # Metrics
    METRICS_ENABLED: bool = False
    METRICS_ROUTE: str = "/metrics"
    METRICS_PROTECT_WITH_BASIC_AUTH: bool = False
    METRICS_BASIC_USER: str | None = None
    METRICS_BASIC_PASS: str | None = None

    PRODUCTION: bool = False

    @property
    def cookie_params(self) -> dict[str, Any]:
        samesite = self.COOKIE_SAMESITE
        if samesite.lower() == "none" and not self.COOKIE_SECURE:
            samesite = "Lax"
        else:
            samesite = samesite.capitalize()
        params: dict[str, Any] = {
            "secure": self.COOKIE_SECURE,
            "httponly": True,
            "samesite": samesite,
            "path": "/",
        }
        if self.COOKIE_DOMAIN:
            params["domain"] = self.COOKIE_DOMAIN
        return params

    @model_validator(mode="after")
    def _require_real_opus_in_prod(self) -> "Settings":
        if not self.PRODUCTION:
            return self

        svc = (self.OPUS_SERVICE or "").strip()
        parsed = urlparse(svc)
        is_full_url = "://" in svc or (parsed.scheme or "").lower() in {"http", "https"}

        if is_full_url:
            _ensure_https_url(svc, "OPUS_SERVICE")
        else:
            _ensure_https_url(self.OPUS_ROOT or "", "OPUS_ROOT")

        _require_nonempty(self.OPUS_APP_TOKEN, "OPUS_APP_TOKEN")
        _require_nonempty(self.OPUS_APP_USER, "OPUS_APP_USER")
        return self

    @model_validator(mode="after")
    def _derive_urls(self) -> "Settings":
        if not self.FRONTEND_BASE_URL and self.BASE_URL:
            self.FRONTEND_BASE_URL = self.BASE_URL.rstrip("/") + "/"

        if not self.OIDC_REDIRECT_URI and self.BASE_URL:
            self.OIDC_REDIRECT_URI = self.BASE_URL.rstrip("/") + "/auth/oidc/callback"

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
