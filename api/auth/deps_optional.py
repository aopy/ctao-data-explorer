import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.jwt_verifier import VerifiedIdentity, verify_bearer

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


async def get_optional_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> VerifiedIdentity | None:
    if not creds or not creds.credentials:
        return None
    try:
        return verify_bearer(creds.credentials)
    except HTTPException as err:
        if err.status_code in (401, 403):
            return None
        logger.warning("Unexpected HTTPException in optional auth: %s", err.status_code)
        return None
