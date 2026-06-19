from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CredentialType = Literal["bearer_token"]
RequestStatus = Literal["completed", "partial", "failed"]
FileErrorCode = Literal[
    "INVALID_REQUEST",
    "HOST_NOT_ALLOWED",
    "NOT_FOUND",
    "AUTHORIZATION_DENIED",
    "RESOLUTION_FAILED",
    "UPSTREAM_ERROR",
]


class SignedUrlRequest(BaseModel):
    files: list[str] = Field(..., min_length=1)
    validity: str = "PT1H"
    rse_preference: list[str] | None = None

    @field_validator("files")
    @classmethod
    def _strip_files(cls, values: list[str]) -> list[str]:
        out = [v.strip() for v in values if v and v.strip()]
        if not out:
            raise ValueError("files array must contain at least one entry")
        return out


class SignedUrlEntry(BaseModel):
    original: str
    storage_url: str
    access_token: str
    expires_at: datetime
    credential_type: CredentialType = "bearer_token"
    size_bytes: int | None = None
    checksum: str | None = None


class FileError(BaseModel):
    file: str
    code: FileErrorCode
    message: str
    status_code: int = 400


class SignedUrlResponse(BaseModel):
    request_id: str
    signed_urls: list[SignedUrlEntry]
    token_exchange_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class SignedUrlPartialResponse(BaseModel):
    request_id: str
    signed_urls: list[SignedUrlEntry]
    errors: list[FileError]
    token_exchange_count: int = 0


class SignedUrlRequestStatus(BaseModel):
    request_id: str
    created_at: datetime
    file_count: int
    storage_elements: list[str] = Field(default_factory=list)
    token_exchange_count: int = 0
    status: RequestStatus


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    iam_reachable: bool | None = None
    rucio_reachable: bool | None = None
    version: str


class ErrorResponse(BaseModel):
    error: str
    message: str


class UpstreamErrorResponse(ErrorResponse):
    upstream: str | None = None
