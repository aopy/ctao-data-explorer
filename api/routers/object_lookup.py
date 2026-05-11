from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Body, HTTPException, Query, Request

from api.services.cache import redis_get_json_dict, redis_set_json_dict
from api.services.object_lookup import (
    SuggestResult,
    object_resolve_impl,
    object_suggest_impl,
)

router = APIRouter()


@router.get("/api/object_suggest", tags=["object_resolve"])
async def object_suggest(
    request: Request,
    q: str = Query(..., min_length=2, max_length=50),
    use_simbad: bool = True,
    use_ned: bool = False,
    limit: int = 15,
) -> SuggestResult:
    q = q.strip()

    cache_key = f"suggest:{q.lower()}:{use_simbad}:{use_ned}:{limit}"
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client:
        cached = await redis_get_json_dict(
            redis_client,
            cache_key,
            metric_name="suggest",
        )
        if cached is not None:
            return cast(SuggestResult, cached)

    result = await object_suggest_impl(
        q=q,
        use_simbad=use_simbad,
        use_ned=use_ned,
        limit=limit,
    )

    if redis_client:
        await redis_set_json_dict(redis_client, cache_key, dict(result), ttl=86400)

    return result


@router.post("/api/object_resolve", tags=["object_resolve"])
async def object_resolve(data: dict[str, Any] = Body(...)) -> dict[str, list[dict[str, Any]]]:
    object_name = str(data.get("object_name", "")).strip()
    use_simbad = bool(data.get("use_simbad", False))
    use_ned = bool(data.get("use_ned", False))

    if not object_name:
        raise HTTPException(status_code=400, detail="No object_name provided.")

    return await object_resolve_impl(
        object_name=object_name,
        use_simbad=use_simbad,
        use_ned=use_ned,
    )
