from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DownloadSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DOWNLOAD_SERVICE_VERSION: str = "0.1.0"

    # IAM / token exchange
    IAM_TOKEN_ENDPOINT: str
    DOWNLOAD_SERVICE_CLIENT_ID: str
    DOWNLOAD_SERVICE_CLIENT_SECRET: str
    DOWNLOAD_TOKEN_EXCHANGE_AUDIENCE: str | None = None
    DOWNLOAD_TOKEN_EXCHANGE_SCOPE: str | None = None

    # Request limits
    DOWNLOAD_MAX_FILES: int = 100
    DOWNLOAD_DEFAULT_VALIDITY: str = "PT1H"
    DOWNLOAD_MAX_VALIDITY_SECONDS: int = 24 * 3600
    DOWNLOAD_TOKEN_EXCHANGE_CONCURRENCY: int = 10

    # Storage validation
    # DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON='["globe-door.ifh.de:2880", "dcache-door.pic.es"]'
    DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON: str = "[]"

    # LFN prefix map for development/testing:
    # DOWNLOAD_LFN_PREFIX_MAP_JSON='{"lfn:/data/":"https://webdav-cta.pic.es:8454/CTAO/Open-SDC/data/"}'
    DOWNLOAD_LFN_PREFIX_MAP_JSON: str = "{}"

    # Health checks
    RUCIO_BASE_URL: str | None = None

    @field_validator("DOWNLOAD_MAX_FILES")
    @classmethod
    def _positive_max_files(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DOWNLOAD_MAX_FILES must be positive")
        return value

    @property
    def allowed_storage_hosts(self) -> set[str]:
        try:
            raw = json.loads(self.DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError("DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON must be valid JSON") from exc
        if not isinstance(raw, list):
            raise ValueError("DOWNLOAD_ALLOWED_STORAGE_HOSTS_JSON must be a JSON list")
        return {str(item).strip() for item in raw if str(item).strip()}

    @property
    def lfn_prefix_map(self) -> dict[str, str]:
        try:
            raw: Any = json.loads(self.DOWNLOAD_LFN_PREFIX_MAP_JSON or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("DOWNLOAD_LFN_PREFIX_MAP_JSON must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError("DOWNLOAD_LFN_PREFIX_MAP_JSON must be a JSON object")
        return {str(k): str(v) for k, v in raw.items()}


@lru_cache
def get_download_settings() -> DownloadSettings:
    return DownloadSettings()
