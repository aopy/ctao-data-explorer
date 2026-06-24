from functools import lru_cache

from fastapi import APIRouter
from pydantic import BaseModel

from api.config import ApiSettings, get_api_settings

router = APIRouter(prefix="/api/config", tags=["config"])


@lru_cache
def _settings() -> ApiSettings:
    return get_api_settings()


class FrontendConfig(BaseModel):
    default_tap_url: str
    default_obscore_table: str


@router.get("/frontend", response_model=FrontendConfig)
async def get_frontend_config() -> FrontendConfig:
    settings = _settings()
    return FrontendConfig(
        default_tap_url=settings.DEFAULT_TAP_URL,
        default_obscore_table=settings.DEFAULT_OBSCORE_TABLE,
    )
