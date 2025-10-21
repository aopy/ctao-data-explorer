from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from .config import get_settings

_security = HTTPBasic()

def _metrics_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    s = get_settings()
    if not s.METRICS_PROTECT_WITH_BASIC_AUTH:
        return True
    if not (s.METRICS_BASIC_USER and s.METRICS_BASIC_PASS):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="metrics auth misconfigured")
    user_ok = secrets.compare_digest(credentials.username, s.METRICS_BASIC_USER)
    pass_ok = secrets.compare_digest(credentials.password, s.METRICS_BASIC_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

def setup_metrics(app):
    """Instrument HTTP and expose a /metrics endpoint if enabled in settings."""
    s = get_settings()
    if not s.METRICS_ENABLED:
        return

    instr = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers={s.METRICS_ROUTE, "/health/live", "/health/ready"},
    ).instrument(app)

    if s.METRICS_PROTECT_WITH_BASIC_AUTH:
        @app.get(s.METRICS_ROUTE, include_in_schema=False)
        def metrics_endpoint(_: bool = Depends(_metrics_auth)):
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    else:
        # Expose the default endpoint (unprotected — protect at Nginx)
        instr.expose(app, endpoint=s.METRICS_ROUTE, include_in_schema=False)
