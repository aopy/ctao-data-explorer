import logging
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from api.logging_config import setup_logging
from api.metrics import (
    cache_hit,
    cache_miss,
    observe_redis,
    opus_record_job_outcome_once,
    setup_metrics,
    vo_observe_call,
)

# helpers

_METRIC_LINE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)\{(?P<labels>[^}]*)\}\s+(?P<value>[0-9.e+-]+)$"
)


def _parse_value(text: str, name: str, **labels) -> float:
    """Return the last observed value for metric 'name' with exact labels, or 0.0 if not present."""
    want = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    last = 0.0
    for line in text.splitlines():
        m = _METRIC_LINE.match(line)
        if not m:
            continue
        if m.group("name") != name:
            continue
        if m.group("labels") == want:
            last = float(m.group("value"))
    return last


# logging tests


def test_logging_levels_and_access_toggle():
    # debug + access muted
    setup_logging(level="DEBUG", include_access=False, json=False)
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("uvicorn.access").getEffectiveLevel() == logging.CRITICAL

    # info + access enabled
    setup_logging(level="INFO", include_access=True, json=False)
    assert logging.getLogger().getEffectiveLevel() == logging.INFO
    assert logging.getLogger("uvicorn.access").getEffectiveLevel() == logging.INFO


# metrics endpoint tests


def _patch_settings(monkeypatch, **overrides):
    base = {
        "METRICS_ENABLED": True,
        "METRICS_ROUTE": "/metrics",
        "METRICS_PROTECT_WITH_BASIC_AUTH": False,
        "METRICS_BASIC_USER": None,
        "METRICS_BASIC_PASS": None,
    }
    base.update(overrides)
    monkeypatch.setattr("api.metrics.get_settings", lambda: SimpleNamespace(**base))


def test_metrics_endpoint_disabled(monkeypatch):
    _patch_settings(monkeypatch, METRICS_ENABLED=False)
    app = FastAPI()
    setup_metrics(app)
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 404  # no route mounted


def test_metrics_endpoint_enabled_public(monkeypatch):
    _patch_settings(monkeypatch, METRICS_ENABLED=True, METRICS_PROTECT_WITH_BASIC_AUTH=False)
    app = FastAPI()
    setup_metrics(app)

    cache_hit("search")

    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "cache_hits_total" in body


def test_metrics_endpoint_basic_auth(monkeypatch):
    _patch_settings(
        monkeypatch,
        METRICS_ENABLED=True,
        METRICS_PROTECT_WITH_BASIC_AUTH=True,
        METRICS_BASIC_USER="alice",
        METRICS_BASIC_PASS="secret",
    )
    app = FastAPI()
    setup_metrics(app)
    client = TestClient(app)

    r = client.get("/metrics")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("basic")

    r = client.get("/metrics", auth=("alice", "wrong"))
    assert r.status_code == 401

    r = client.get("/metrics", auth=("alice", "secret"))
    assert r.status_code == 200


# metric helpers


@pytest.mark.anyio
async def test_custom_counters_histograms_and_opus_dedup(monkeypatch):
    # baseline snapshot
    before = generate_latest().decode()

    # cache counters
    v0 = _parse_value(before, "cache_hits_total", cache="search")
    cache_hit("search")
    after1 = generate_latest().decode()
    v1 = _parse_value(after1, "cache_hits_total", cache="search")
    assert v1 > v0

    v0m = _parse_value(before, "cache_misses_total", cache="suggest")
    cache_miss("suggest")
    after2 = generate_latest().decode()
    v1m = _parse_value(after2, "cache_misses_total", cache="suggest")
    assert v1m > v0m

    # VO upstream
    host = "simbad.cds.unistra.fr"
    s = "simbad-tap"
    v0f = _parse_value(after2, "vo_request_failures_total", service=s, host=host)
    vo_observe_call(s, f"https://{host}/simbad", seconds=0.12, ok=False)
    after3 = generate_latest().decode()
    v1f = _parse_value(after3, "vo_request_failures_total", service=s, host=host)
    assert v1f > v0f

    # Redis op histogram + failures counter
    v0r = _parse_value(after3, "redis_op_failures_total", op="get")
    observe_redis("get", seconds=0.01, ok=False)
    after4 = generate_latest().decode()
    v1r = _parse_value(after4, "redis_op_failures_total", op="get")
    assert v1r > v0r

    # OPUS outcome counters with Redis de-dup
    class FakeRedis:
        def __init__(self):
            self._seen = set()

        async def set(self, key, value, ex=None, nx=False):
            if nx:
                if key in self._seen:
                    return False
                self._seen.add(key)
                return True
            self._seen.add(key)
            return True

    fake = FakeRedis()
    svc = "svc-x"
    job = "job-42"

    v0c = _parse_value(after4, "opus_job_completed_total", service=svc)
    await opus_record_job_outcome_once(fake, job, "COMPLETED", svc)
    await opus_record_job_outcome_once(fake, job, "COMPLETED", svc)
    after5 = generate_latest().decode()
    v1c = _parse_value(after5, "opus_job_completed_total", service=svc)
    assert v1c == v0c + 1.0  # exactly once

    v0e = _parse_value(after5, "opus_job_failures_total", service=svc)
    await opus_record_job_outcome_once(fake, "job-err", "ERROR", svc)
    after6 = generate_latest().decode()
    v1e = _parse_value(after6, "opus_job_failures_total", service=svc)
    assert v1e == v0e + 1.0
