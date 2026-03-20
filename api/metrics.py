import secrets
from typing import Any
from urllib.parse import urlparse

from ctao_shared.config import get_settings
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

# HTTP instrumentation
_security = HTTPBasic()


def _metrics_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    s = get_settings()
    if not s.METRICS_PROTECT_WITH_BASIC_AUTH:
        return
    if not (s.METRICS_BASIC_USER and s.METRICS_BASIC_PASS):
        raise HTTPException(status_code=503, detail="metrics auth misconfigured")
    uok = secrets.compare_digest(credentials.username or "", s.METRICS_BASIC_USER)
    pok = secrets.compare_digest(credentials.password or "", s.METRICS_BASIC_PASS)
    if not (uok and pok):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


def setup_metrics(app: FastAPI) -> None:
    s = get_settings()
    if not s.METRICS_ENABLED:
        return

    # Instrument all endpoints (excluding health + metrics)
    instr = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[s.METRICS_ROUTE, "/health/live", "/health/ready"],
    ).instrument(app)

    def _metrics_handler() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if s.METRICS_PROTECT_WITH_BASIC_AUTH:
        app.add_api_route(
            s.METRICS_ROUTE,
            _metrics_handler,
            methods=["GET"],
            include_in_schema=False,
            dependencies=[Depends(_metrics_auth)],
        )
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
    buckets=(0.2, 0.5, 1, 2, 5, 10, 20),
)


def opus_record_submit() -> None:
    _opus_submit_total.inc()


def opus_record_submit_failure() -> None:
    _opus_submit_fail_total.inc()


def opus_observe_submit(seconds: float, ok: bool) -> None:
    _ = ok
    _opus_submit_request_seconds.observe(seconds)
    # failures are counted separately via opus_record_submit_failure


# OPUS job outcomes

# Count jobs that ended COMPLETED vs ERROR/FAILED/ABORTED
_opus_job_completed = Counter(
    "opus_job_completed_total",
    "OPUS jobs that reached COMPLETED",
    ["service"],
)
_opus_job_failed = Counter(
    "opus_job_failures_total",
    "OPUS jobs that ended in ERROR/FAILED/ABORTED",
    ["service"],
)


async def opus_record_job_outcome_once(redis: Any, job_id: str, phase: str, service: str) -> None:
    """
    Increment outcome counters once per (job_id, phase). If a Redis client is
    provided (app.state.redis), we use it to ensure we don't double count
    the same job on repeated polls of /jobs or /jobs/{id}.
    """
    phase = (phase or "").upper()
    if phase not in ("COMPLETED", "ERROR", "FAILED", "ABORTED"):
        return
    key = f"metrics:opus:outcome:{job_id}:{phase}"
    wrote = True

    # De-dup with Redis if available
    if redis:
        try:
            # only first time returns True
            wrote = await redis.set(key, "1", ex=60 * 60 * 24 * 90, nx=True)
        except Exception:
            wrote = True  # fall through
    if not wrote:
        return

    if phase == "COMPLETED":
        _opus_job_completed.labels(service=service).inc()
    else:
        _opus_job_failed.labels(service=service).inc()


# VO upstreams (TAP, SIMBAD/NED helpers, etc.)
_vo_req_dur = Histogram(
    "vo_request_duration_seconds",
    "VO upstream call duration (s)",
    ["service", "host"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)
_vo_req_fail = Counter("vo_request_failures_total", "VO upstream failures", ["service", "host"])


def vo_observe_call(service: str, url_or_host: str, seconds: float, ok: bool) -> None:
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
    "redis_op_duration_seconds",
    "Redis operation latency (s)",
    ["op"],
    buckets=(0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1),
)
_redis_op_fail = Counter("redis_op_failures_total", "Redis operation failures", ["op"])


def cache_hit(cache: str) -> None:
    _cache_hits.labels(cache=cache).inc()


def cache_miss(cache: str) -> None:
    _cache_misses.labels(cache=cache).inc()


def observe_redis(op: str, seconds: float, ok: bool) -> None:
    _redis_op_dur.labels(op=op).observe(seconds)
    if not ok:
        _redis_op_fail.labels(op=op).inc()
