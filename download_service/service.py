from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from download_service.config import DownloadSettings
from download_service.models import (
    FileError,
    FileErrorCode,
    RequestStatus,
    SignedUrlEntry,
    SignedUrlRequest,
    SignedUrlRequestStatus,
)
from download_service.token_exchange import (
    TokenExchangeDenied,
    TokenExchangeUpstreamError,
    exchange_file_token,
)
from download_service.url_utils import (
    is_lfn,
    parse_iso_duration,
    storage_audience_from_url,
    storage_element_from_url,
    storage_scope_from_url,
    validate_storage_url,
)


class RequestStatusStore:
    """
    Minimal in-memory status store.

    In production we can replace this with Redis/Postgres later. Tokens are intentionally
    not stored, only audit metadata.
    """

    def __init__(self) -> None:
        self._items: dict[str, SignedUrlRequestStatus] = {}

    def put(self, item: SignedUrlRequestStatus) -> None:
        self._items[item.request_id] = item

    def get(self, request_id: str) -> SignedUrlRequestStatus | None:
        return self._items.get(request_id)


class LfnResolver:
    def __init__(self, settings: DownloadSettings) -> None:
        self.settings = settings

    async def resolve(self, lfn: str, rse_preference: list[str] | None = None) -> str:
        """
        Early implementation: resolve LFNs through a configured prefix map.

        Later this should call Rucio and apply rse_preference.
        """
        _ = rse_preference

        for prefix, target_prefix in self.settings.lfn_prefix_map.items():
            if lfn.startswith(prefix):
                suffix = lfn.removeprefix(prefix).lstrip("/")
                return target_prefix.rstrip("/") + "/" + suffix

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "LFN resolution is not configured for this prefix",
            },
        )


def _file_error_code_from_http_detail(detail: object) -> FileErrorCode:
    if isinstance(detail, dict):
        raw = detail.get("error")
        if raw in {
            "INVALID_REQUEST",
            "HOST_NOT_ALLOWED",
            "NOT_FOUND",
            "AUTHORIZATION_DENIED",
            "RESOLUTION_FAILED",
            "UPSTREAM_ERROR",
        }:
            return raw
    return "INVALID_REQUEST"


async def _resolve_input_file(
    *,
    original: str,
    request: SignedUrlRequest,
    settings: DownloadSettings,
    resolver: LfnResolver,
) -> str:
    if is_lfn(original):
        resolved = await resolver.resolve(original, request.rse_preference)
        return validate_storage_url(resolved, settings)

    return validate_storage_url(original, settings)


async def _tokenise_one(
    *,
    original: str,
    request: SignedUrlRequest,
    user_access_token: str,
    validity_seconds: int,
    settings: DownloadSettings,
    resolver: LfnResolver,
) -> tuple[SignedUrlEntry | None, FileError | None]:
    try:
        storage_url = await _resolve_input_file(
            original=original,
            request=request,
            settings=settings,
            resolver=resolver,
        )

        scope = storage_scope_from_url(storage_url)
        audience = storage_audience_from_url(storage_url)

        access_token, expires_at = await exchange_file_token(
            subject_token=user_access_token,
            scope=scope,
            audience=audience,
            validity_seconds=validity_seconds,
            settings=settings,
        )

        return (
            SignedUrlEntry(
                original=original,
                storage_url=storage_url,
                access_token=access_token,
                expires_at=expires_at,
            ),
            None,
        )

    except TokenExchangeDenied:
        return (
            None,
            FileError(
                file=original,
                code="AUTHORIZATION_DENIED",
                message="IAM scope policy denied storage.read for this path",
                status_code=status.HTTP_403_FORBIDDEN,
            ),
        )

    except TokenExchangeUpstreamError:
        return (
            None,
            FileError(
                file=original,
                code="UPSTREAM_ERROR",
                message="IAM token exchange endpoint returned an unexpected response",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ),
        )

    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            code = _file_error_code_from_http_detail(detail)
            message = str(detail.get("message") or "Invalid download request")
        else:
            code = "INVALID_REQUEST"
            message = str(detail)
        return (
            None,
            FileError(
                file=original,
                code=code,
                message=message,
                status_code=exc.status_code,
            ),
        )


async def create_signed_urls(
    *,
    request: SignedUrlRequest,
    user_access_token: str,
    settings: DownloadSettings,
    status_store: RequestStatusStore,
) -> tuple[str, list[SignedUrlEntry], list[FileError], int, RequestStatus]:
    if len(request.files) > settings.DOWNLOAD_MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "files array exceeds the configured maximum",
            },
        )

    validity_seconds = parse_iso_duration(
        request.validity or settings.DOWNLOAD_DEFAULT_VALIDITY,
        max_seconds=settings.DOWNLOAD_MAX_VALIDITY_SECONDS,
    )

    request_id = f"req-{uuid.uuid4().hex[:8]}"
    resolver = LfnResolver(settings)
    semaphore = asyncio.Semaphore(settings.DOWNLOAD_TOKEN_EXCHANGE_CONCURRENCY)

    async def guarded(original: str) -> tuple[SignedUrlEntry | None, FileError | None]:
        async with semaphore:
            return await _tokenise_one(
                original=original,
                request=request,
                user_access_token=user_access_token,
                validity_seconds=validity_seconds,
                settings=settings,
                resolver=resolver,
            )

    results = await asyncio.gather(*(guarded(file_) for file_ in request.files))

    signed_urls = [entry for entry, _error in results if entry is not None]
    errors = [error for _entry, error in results if error is not None]
    token_exchange_count = len(signed_urls)

    if signed_urls and errors:
        final_status: RequestStatus = "partial"
    elif signed_urls:
        final_status = "completed"
    else:
        final_status = "failed"

    status_store.put(
        SignedUrlRequestStatus(
            request_id=request_id,
            created_at=datetime.now(UTC),
            file_count=len(request.files),
            storage_elements=sorted({storage_element_from_url(e.storage_url) for e in signed_urls}),
            token_exchange_count=token_exchange_count,
            status=final_status,
        )
    )

    return request_id, signed_urls, errors, token_exchange_count, final_status
