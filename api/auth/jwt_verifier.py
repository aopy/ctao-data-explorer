from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from api.config import get_api_settings

INVALID_BEARER_TOKEN_DETAIL = "Invalid bearer token"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifiedIdentity:
    sub: str
    email: str | None
    preferred_username: str | None
    given_name: str | None
    family_name: str | None
    name: str | None
    claims: dict[str, Any]


class JwtVerifier:
    """
    JWT verifier for the API resource server.

    Design:
    - Do NOT require OIDC_ISSUER at import time.
    - Only require it when a token is actually verified.
    - We disable PyJWT issuer verification and do our own normalized check
      (trailing-slash differences are common).
    """

    def __init__(self) -> None:
        self._settings = get_api_settings()
        self._jwks_client: PyJWKClient | None = None
        self._discovery_cache: tuple[float, dict[str, Any]] | None = None

    def _issuer_or_503(self) -> str:
        issuer = (self._settings.OIDC_ISSUER or "").strip()
        if not issuer:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC_ISSUER is not configured on the API service",
            )
        return issuer.rstrip("/")

    def _get_discovery(self) -> dict[str, Any]:
        now = time.time()
        if self._discovery_cache and (now - self._discovery_cache[0]) < 600:
            return self._discovery_cache[1]

        issuer = self._issuer_or_503()
        url = f"{issuer}/.well-known/openid-configuration"

        try:
            resp = httpx.get(url, timeout=5)
            resp.raise_for_status()
            data = cast(dict[str, Any], resp.json())
        except httpx.RequestError as err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC discovery endpoint unreachable",
            ) from err
        except httpx.HTTPStatusError as err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC discovery endpoint returned an error",
            ) from err
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC discovery endpoint returned invalid JSON",
            ) from err

        self._discovery_cache = (now, data)
        return data

    def _get_jwks_client(self) -> PyJWKClient:
        if self._jwks_client is not None:
            return self._jwks_client

        discovery = self._get_discovery()
        jwks_uri = discovery.get("jwks_uri")
        if not jwks_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC discovery document missing jwks_uri",
            )

        self._jwks_client = PyJWKClient(str(jwks_uri))
        return self._jwks_client

    def verify(self, token: str) -> VerifiedIdentity:
        s = self._settings

        jwk_client = self._get_jwks_client()
        try:
            signing_key = jwk_client.get_signing_key_from_jwt(token).key
        except (jwt.PyJWTError, ValueError) as err:
            logger.warning("JWT signing key lookup failed: %s", err)
            raise HTTPException(status_code=401, detail=INVALID_BEARER_TOKEN_DETAIL) from err

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256", "RS512"],
                audience=s.OIDC_AUDIENCE,
                options={
                    "verify_aud": bool(s.OIDC_AUDIENCE),
                    "verify_iss": False,
                },
                leeway=s.OIDC_CLOCK_SKEW_SECONDS,
            )
        except jwt.PyJWTError as err:
            logger.warning("JWT decode failed: %s", repr(err))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_BEARER_TOKEN_DETAIL,
            ) from err

        token_iss = str(claims.get("iss") or "").rstrip("/")
        expected_iss = self._issuer_or_503().rstrip("/")
        if token_iss != expected_iss:
            logger.warning("JWT issuer mismatch: token=%r expected=%r", token_iss, expected_iss)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_BEARER_TOKEN_DETAIL,
            )

        sub = (claims.get("sub") or "").strip()
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_BEARER_TOKEN_DETAIL,
            )

        return VerifiedIdentity(
            sub=sub,
            email=cast(str | None, claims.get("email")),
            preferred_username=cast(str | None, claims.get("preferred_username")),
            given_name=cast(str | None, claims.get("given_name")),
            family_name=cast(str | None, claims.get("family_name")),
            name=cast(str | None, claims.get("name")),
            claims=cast(dict[str, Any], claims),
        )


@lru_cache(maxsize=1)
def get_verifier() -> JwtVerifier:
    return JwtVerifier()


def verify_bearer(token: str) -> VerifiedIdentity:
    return get_verifier().verify(token)
