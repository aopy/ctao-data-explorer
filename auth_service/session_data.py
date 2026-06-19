from __future__ import annotations

from typing import Any

from ctao_shared.constants import (
    SESSION_ACCESS_TOKEN_EXPIRY_KEY,
    SESSION_ACCESS_TOKEN_KEY,
    SESSION_IAM_EMAIL_KEY,
    SESSION_IAM_FAMILY_NAME_KEY,
    SESSION_IAM_GIVEN_NAME_KEY,
    SESSION_IAM_SUB_KEY,
    SESSION_REFRESH_TOKEN_KEY,
    SESSION_USER_ID_KEY,
)
from pydantic import BaseModel, ConfigDict, Field


class SessionData(BaseModel):
    """
    Canonical auth_service session payload stored in Redis.

    NOTE:
    - Keys in Redis remain the string constants from ctao_shared.constants
      for backward compatibility and consistency.
    - This model centralizes the schema and normalization of legacy aliases.
    """

    model_config = ConfigDict(extra="ignore")

    # Required (for a valid session)
    app_user_id: int = Field(alias=SESSION_USER_ID_KEY)
    iam_sub: str = Field(alias=SESSION_IAM_SUB_KEY)

    # Optional user fields
    iam_email: str | None = Field(default=None, alias=SESSION_IAM_EMAIL_KEY)
    first_name: str | None = Field(default=None, alias=SESSION_IAM_GIVEN_NAME_KEY)
    last_name: str | None = Field(default=None, alias=SESSION_IAM_FAMILY_NAME_KEY)

    # Token state (access token required for token relay)
    iam_at: str | None = Field(default=None, alias=SESSION_ACCESS_TOKEN_KEY)
    iam_at_exp: float | None = Field(default=None, alias=SESSION_ACCESS_TOKEN_EXPIRY_KEY)
    iam_rt: str | None = Field(default=None, alias=SESSION_REFRESH_TOKEN_KEY)

    iam_id_token: str | None = None

    @classmethod
    def from_redis_dict(cls, raw: dict[str, Any]) -> SessionData:
        """
        Parse raw dict from Redis.
        """
        if not isinstance(raw, dict):
            raise ValueError("Session payload is not a dict")

        # legacy aliases:
        # - subject id: "iam_subject_id", "sub"
        # - email: "email"
        # - names: "given_name", "family_name"
        normalized: dict[str, Any] = dict(raw)

        if SESSION_IAM_SUB_KEY not in normalized:
            normalized[SESSION_IAM_SUB_KEY] = normalized.get("iam_subject_id") or normalized.get(
                "sub"
            )

        if SESSION_IAM_EMAIL_KEY not in normalized:
            normalized[SESSION_IAM_EMAIL_KEY] = normalized.get("email")

        if SESSION_IAM_GIVEN_NAME_KEY not in normalized:
            normalized[SESSION_IAM_GIVEN_NAME_KEY] = normalized.get("given_name")

        if SESSION_IAM_FAMILY_NAME_KEY not in normalized:
            normalized[SESSION_IAM_FAMILY_NAME_KEY] = normalized.get("family_name")

        return cls.model_validate(normalized)

    def to_redis_dict(self) -> dict[str, Any]:
        """
        Dump using Redis key aliases (SESSION_* constants).
        """
        return self.model_dump(by_alias=True, exclude_none=True)

    # Convenience view used by endpoints / relay
    def user_payload(self) -> dict[str, Any]:
        """
        A stable, service-local payload for FastAPI deps and responses.
        """
        return {
            "app_user_id": self.app_user_id,
            "iam_subject_id": self.iam_sub,
            "email": self.iam_email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "iam_access_token": self.iam_at,
            "is_active": True,
            "is_superuser": False,
        }
