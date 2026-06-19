from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    return {"status": "ok"}
