import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.jwt_verifier import VerifiedIdentity, verify_bearer

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

_NOT_AUTHENTICATED = "Not authenticated"


async def get_required_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> VerifiedIdentity:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTHENTICATED)

    token = creds.credentials
    try:
        return verify_bearer(token)
    except HTTPException as err:
        logger.info(
            "JWT verification failed: %s", err.detail if hasattr(err, "detail") else "HTTPException"
        )
        raise
