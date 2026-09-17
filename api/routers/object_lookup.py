from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.services.cache import redis_get_json_dict, redis_set_json_dict
from api.services.object_lookup import (
    Suggestion,
    object_resolve_impl,
    object_suggest_impl,
)

router = APIRouter()


class ObjectResolveRequest(BaseModel):
    object_name: str = Field(min_length=1, max_length=200)
    resolve_name: str | None = Field(
        default=None,
        max_length=200,
    )
    use_simbad: bool = False
    use_ned: bool = False


@router.get("/api/object_suggest", tags=["object_resolve"])
async def object_suggest(
    request: Request,
    q: str = Query(..., min_length=2, max_length=50),
    use_simbad: bool = True,
    use_ned: bool = False,
    limit: int = Query(15, ge=1, le=50),
) -> dict[str, list[Suggestion]]:
    q = q.strip()

    if len(q) < 2:
        raise HTTPException(
            status_code=422,
            detail="Query must contain at least two non-whitespace characters.",
        )

    cache_key = f"suggest:v5:{q.casefold()}:{use_simbad}:{use_ned}:{limit}"
    redis_client = getattr(
        request.app.state,
        "redis",
        None,
    )

    if redis_client is not None:
        cached = await redis_get_json_dict(
            redis_client,
            cache_key,
            metric_name="suggest",
        )

        if cached is not None:
            return cast(
                dict[str, list[Suggestion]],
                cached,
            )

    result = await object_suggest_impl(
        q=q,
        use_simbad=use_simbad,
        use_ned=use_ned,
        limit=limit,
    )

    response: dict[str, list[Suggestion]] = {
        "results": result["results"],
    }

    # Cache only if all enabled external services completed successfully
    if redis_client is not None and result["complete"]:
        await redis_set_json_dict(
            redis_client,
            cache_key,
            response,
            ttl=86400,
        )

    return response


@router.post("/api/object_resolve", tags=["object_resolve"])
async def object_resolve(
    data: ObjectResolveRequest,
) -> dict[str, list[dict[str, Any]]]:
    object_name = data.object_name.strip()
    resolve_name = data.resolve_name.strip() if data.resolve_name else object_name

    if not object_name:
        raise HTTPException(
            status_code=400,
            detail="No object_name provided.",
        )

    if not resolve_name:
        raise HTTPException(
            status_code=400,
            detail="No resolvable object identifier provided.",
        )

    return await object_resolve_impl(
        resolve_name=resolve_name,
        use_simbad=data.use_simbad,
        use_ned=data.use_ned,
    )
