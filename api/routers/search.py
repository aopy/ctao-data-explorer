from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.deps_optional import get_optional_identity
from api.auth.jwt_verifier import VerifiedIdentity
from api.config import get_api_settings
from api.db import get_async_session
from api.models import SearchResult
from api.services.search_coords import SearchCoordsParams, search_coords_impl

router = APIRouter()


def get_search_coords_params(request: Request) -> SearchCoordsParams:
    raw: dict[str, Any] = dict(request.query_params)

    tap_url = (raw.get("tap_url") or "").strip()
    obscore = (raw.get("obscore_table") or "").strip()

    settings = get_api_settings()

    if not tap_url:
        raw["tap_url"] = settings.DEFAULT_TAP_URL

    if not obscore:
        raw["obscore_table"] = settings.DEFAULT_OBSCORE_TABLE

    return SearchCoordsParams.model_validate(raw)


@router.get("/api/search_coords", response_model=SearchResult, tags=["search"])
async def search_coords(
    request: Request,
    params: SearchCoordsParams = Depends(get_search_coords_params),
    identity: VerifiedIdentity | None = Depends(get_optional_identity),
    db_session: AsyncSession = Depends(get_async_session),
) -> SearchResult:
    redis_client = getattr(request.app.state, "redis", None)

    return await search_coords_impl(
        params=params,
        identity=identity,
        db_session=db_session,
        redis_client=redis_client,
    )
