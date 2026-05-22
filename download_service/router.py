from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from download_service.config import DownloadSettings, get_download_settings
from download_service.models import (
    HealthResponse,
    SignedUrlPartialResponse,
    SignedUrlRequest,
    SignedUrlRequestStatus,
    SignedUrlResponse,
)
from download_service.security import require_bearer_token
from download_service.service import RequestStatusStore, create_signed_urls

router = APIRouter(prefix="/api/v1", tags=["download"])


def get_status_store(request: Request) -> RequestStatusStore:
    return request.app.state.download_status_store


BearerTokenDep = Annotated[str, Depends(require_bearer_token)]
SettingsDep = Annotated[DownloadSettings, Depends(get_download_settings)]
StatusStoreDep = Annotated[RequestStatusStore, Depends(get_status_store)]


@router.post("/signed-urls")
async def signed_urls(
    payload: SignedUrlRequest,
    user_access_token: BearerTokenDep,
    settings: SettingsDep,
    status_store: StatusStoreDep,
) -> JSONResponse:
    request_id, signed, errors, count, final_status = await create_signed_urls(
        request=payload,
        user_access_token=user_access_token,
        settings=settings,
        status_store=status_store,
    )

    if final_status == "failed":
        first_error = errors[0] if errors else None

        raise HTTPException(
            status_code=first_error.status_code if first_error else status.HTTP_400_BAD_REQUEST,
            detail={
                "error": first_error.code if first_error else "INVALID_REQUEST",
                "message": first_error.message if first_error else "No files could be prepared",
                "errors": [error.model_dump(exclude={"status_code"}) for error in errors],
            },
        )

    if errors:
        partial_body = SignedUrlPartialResponse(
            request_id=request_id,
            signed_urls=signed,
            errors=errors,
            token_exchange_count=count,
        )
        body = partial_body.model_dump(mode="json")
        for error in body.get("errors", []):
            error.pop("status_code", None)

        return JSONResponse(
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            content=body,
        )

    success_body = SignedUrlResponse(
        request_id=request_id,
        signed_urls=signed,
        token_exchange_count=count,
        warnings=[],
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=success_body.model_dump(mode="json"),
    )


@router.get("/signed-urls/{request_id}", response_model=SignedUrlRequestStatus)
async def signed_url_status(
    request_id: str,
    _user_access_token: BearerTokenDep,
    status_store: StatusStoreDep,
) -> SignedUrlRequestStatus:
    item = status_store.get(request_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": "No request found for the given request_id",
            },
        )
    return item


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep) -> HealthResponse:
    iam_reachable = False
    rucio_reachable: bool | None = None

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            # A GET on token endpoint may be 405, but reachable.
            response = await client.get(settings.IAM_TOKEN_ENDPOINT)
            iam_reachable = response.status_code < 500
        except httpx.RequestError:
            iam_reachable = False

        if settings.RUCIO_BASE_URL:
            try:
                response = await client.get(settings.RUCIO_BASE_URL)
                rucio_reachable = response.status_code < 500
            except httpx.RequestError:
                rucio_reachable = False

    return HealthResponse(
        status="ok" if iam_reachable and rucio_reachable is not False else "degraded",
        iam_reachable=iam_reachable,
        rucio_reachable=rucio_reachable,
        version=settings.DOWNLOAD_SERVICE_VERSION,
    )
