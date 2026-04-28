from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        extra="ignore",
        validate_default=True,
    )

    # Prefix everything so API can be deployed independently
    API_DATABASE_URL: str
    API_REDIS_URL: str | None = None

    # Resource-server JWT verification
    OIDC_ISSUER: str | None = None
    OIDC_AUDIENCE: str | None = None
    OIDC_CLOCK_SKEW_SECONDS: int = 60

    DEFAULT_TAP_URL: str = "http://voparis-tap-he.obspm.fr/tap"  # no HTTPS available (for now)
    ALLOW_INSECURE_TAP_URL: bool = True
    DEFAULT_OBSCORE_TABLE: str = "hess_dr.obscore_sdc"

    # External services (API-only needs)
    SIMBAD_TAP_SYNC: str = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
    SIMBAD_TAP_BASE: str = "https://simbad.cds.unistra.fr/simbad/sim-tap"
    NED_OBJECT_LOOKUP_URL: str = "https://ned.ipac.caltech.edu/srs/ObjectLookup"
    NED_TAP_SYNC_URL: str = "https://ned.ipac.caltech.edu/tap/sync"

    # OPUS
    OPUS_ROOT: str = "https://voparis-uws-test.obspm.fr"
    OPUS_SERVICE: str = "https://example.invalid/opus"
    OPUS_APP_TOKEN: str = ""
    OPUS_APP_USER: str = "ctao"

    # Logs/metrics
    LOG_LEVEL: str = "INFO"
    LOG_INCLUDE_ACCESS: bool = True
    LOG_JSON: bool = False
    ENABLE_DOCS: bool = False
    METRICS_ENABLED: bool = False
    METRICS_ROUTE: str = "/metrics"
    METRICS_PROTECT_WITH_BASIC_AUTH: bool = False
    METRICS_BASIC_USER: str | None = None
    METRICS_BASIC_PASS: str | None = None

    @property
    def DATABASE_URL(self) -> str:
        return self.API_DATABASE_URL

    @model_validator(mode="after")
    def _validate_urls(self) -> ApiSettings:
        if self.DEFAULT_TAP_URL.startswith("http://") and not self.ALLOW_INSECURE_TAP_URL:
            raise ValueError("DEFAULT_TAP_URL uses http:// but ALLOW_INSECURE_TAP_URL is false")
        return self


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()
