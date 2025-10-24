from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
from fastapi import Depends, Response, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from urllib.parse import urlparse
from api.config import get_settings

# HTTP instrumentation
_security = HTTPBasic()

def _metrics_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    s = get_settings()
    if not s.METRICS_PROTECT_WITH_BASIC_AUTH:
        return True
    if not (s.METRICS_BASIC_USER and s.METRICS_BASIC_PASS):
        raise HTTPException(status_code=503, detail="metrics auth misconfigured")
    uok = secrets.compare_digest(credentials.username, s.METRICS_BASIC_USER)
    pok = secrets.compare_digest(credentials.password, s.METRICS_BASIC_PASS)
    if not (uok and pok):
        raise HTTPException(status_code=401, detail="Unauthorized",
                            headers={"WWW-Authenticate": "Basic"})
    return True

def setup_metrics(app):
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
        instr.expose(app, endpoint=s.METRICS_ROUTE, include_in_schema=False)

# Custom app metrics
# OPUS
_opus_submit_total = Counter("opus_submit_total", "OPUS job submissions")
_opus_submit_fail_total = Counter("opus_submit_failures_total", "Failed OPUS submissions")
# Duration of the create+run HTTP interaction
_opus_submit_request_seconds = Histogram(
    "opus_submit_request_seconds",
    "Time to create+RUN an OPUS job via REST (seconds)",
    buckets=(0.2, 0.5, 1, 2, 5, 10, 20)
)

def opus_record_submit(): _opus_submit_total.inc()
def opus_record_submit_failure(): _opus_submit_fail_total.inc()
def opus_observe_submit(seconds: float, ok: bool):
    _opus_submit_request_seconds.observe(seconds)
    # failures are counted separately via opus_record_submit_failure

# VO upstreams (TAP, SIMBAD/NED helpers, etc.)
_vo_req_dur = Histogram(
    "vo_request_duration_seconds", "VO upstream call duration (s)",
    ["service", "host"], buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10)
)
_vo_req_fail = Counter(
    "vo_request_failures_total", "VO upstream failures", ["service", "host"]
)

def vo_observe_call(service: str, url_or_host: str, seconds: float, ok: bool):
    """service: 'tap' | 'simbad-tap' | 'ned-objectlookup' | 'opus-rest' | etc."""
    host = url_or_host
    try:
        host = urlparse(url_or_host).hostname or url_or_host
    except Exception:
        pass
    _vo_req_dur.labels(service=service, host=host).observe(seconds)
    if not ok:
        _vo_req_fail.labels(service=service, host=host).inc()

_cache_hits = Counter("cache_hits_total", "Cache hits", ["cache"])
_cache_misses = Counter("cache_misses_total", "Cache misses", ["cache"])

_redis_op_dur = Histogram(
    "redis_op_duration_seconds", "Redis operation latency (s)", ["op"],
    buckets=(0.001,0.005,0.01,0.02,0.05,0.1,0.2,0.5,1)
)
_redis_op_fail = Counter("redis_op_failures_total", "Redis operation failures", ["op"])

def cache_hit(cache: str):   _cache_hits.labels(cache=cache).inc()
def cache_miss(cache: str):  _cache_misses.labels(cache=cache).inc()

def observe_redis(op: str, seconds: float, ok: bool):
    _redis_op_dur.labels(op=op).observe(seconds)
    if not ok: _redis_op_fail.labels(op=op).inc()

