from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # App / cookies
    BASE_URL: str | None = None
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
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/oidc/callback"
    OIDC_FAKE_EXPIRES_IN: int | None = None

    JWT_SECRET: str | None = None
    DB_URL: str | None = None
    NODE_OPTIONS: str | None = None

    # Logs
    LOG_LEVEL: str = "INFO"
    LOG_INCLUDE_ACCESS: bool = True
    LOG_JSON: bool = False

    # OPUS / UWS
    OPUS_ROOT: str = "https://voparis-uws-test.obspm.fr"
    OPUS_SERVICE: str
    OPUS_APP_TOKEN: str
    OPUS_APP_USER: str = "ctao"

    # Metrics
    METRICS_ENABLED: bool = False
    METRICS_ROUTE: str = "/metrics"
    METRICS_PROTECT_WITH_BASIC_AUTH: bool = False
    METRICS_BASIC_USER: str | None = None
    METRICS_BASIC_PASS: str | None = None

    @property
    def PRODUCTION(self) -> bool:
        return bool(self.BASE_URL)

    @property
    def cookie_params(self) -> dict:
        samesite = self.COOKIE_SAMESITE
        if samesite.lower() == "none" and not self.COOKIE_SECURE:
            samesite = "Lax"
        else:
            samesite = samesite.capitalize()
        params = {"secure": self.COOKIE_SECURE, "httponly": True, "samesite": samesite, "path": "/"}
        if self.COOKIE_DOMAIN:
            params["domain"] = self.COOKIE_DOMAIN
        return params


@lru_cache
def get_settings() -> Settings:
    return Settings()
