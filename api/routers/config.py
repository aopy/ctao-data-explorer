from fastapi import APIRouter
from pydantic import BaseModel

from api.config import get_api_settings

router = APIRouter(prefix="/api/config", tags=["config"])


class FrontendConfig(BaseModel):
    default_tap_url: str
    default_obscore_table: str


@router.get("/frontend", response_model=FrontendConfig)
async def get_frontend_config() -> FrontendConfig:
    settings = get_api_settings()
    return FrontendConfig(
        default_tap_url=settings.DEFAULT_TAP_URL,
        default_obscore_table=settings.DEFAULT_OBSCORE_TABLE,
    )
