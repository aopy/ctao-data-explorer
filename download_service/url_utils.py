from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import HTTPException, status

from download_service.config import DownloadSettings

ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_iso_duration(value: str, *, max_seconds: int) -> int:
    match = ISO_DURATION_RE.fullmatch(value.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "validity must be a valid ISO 8601 duration",
            },
        )

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total = int(timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds())
    if total <= 0 or total > max_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "validity must be greater than zero and must not exceed P1D",
            },
        )
    return total


def validate_storage_url(url: str, settings: DownloadSettings) -> str:
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "Storage URL must use https",
            },
        )

    if parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "storage URL must not contain credentials or fragments",
            },
        )

    if not parsed.netloc or not parsed.path or parsed.path == "/":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": "storage URL must include a host and file path",
            },
        )

    allowed = settings.allowed_storage_hosts
    if parsed.netloc not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "HOST_NOT_ALLOWED",
                "message": "Storage host is not allowed",
            },
        )

    return url


def storage_scope_from_url(storage_url: str) -> str:
    parsed = urlparse(storage_url)
    return f"storage.read:{parsed.path}"


def storage_audience_from_url(storage_url: str) -> str:
    parsed = urlparse(storage_url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def storage_element_from_url(storage_url: str) -> str:
    return urlparse(storage_url).netloc


def is_lfn(value: str) -> bool:
    return value.startswith("lfn:/")
