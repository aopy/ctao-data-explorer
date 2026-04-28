from __future__ import annotations

import asyncio
import hashlib
import inspect
import itertools
import json
import logging
import math
import os
import re
import time
import urllib.parse
from collections.abc import (
    AsyncIterator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from typing import (
    Any,
    Literal,
    TypedDict,
    cast,
)

import astropy.units as u
import pyvo as vo
import redis.asyncio as redis
import requests
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table
from astropy.table import Table
from astropy.time import Time
from ctao_shared.constants import (
    COORD_SYS_EQ_DEG,
    COORD_SYS_EQ_HMS,
    COORD_SYS_GAL,
)
from ctao_shared.logging_config import setup_logging
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.staticfiles import StaticFiles

from api.auth.deps_optional import get_optional_identity
from api.auth.jwt_verifier import VerifiedIdentity
from api.config import get_api_settings
from api.db import close_engine, get_async_session
from api.redis_client import close_redis, get_api_redis_pool

from .basket import basket_router
from .coords import coord_router
from .metrics import cache_hit, cache_miss, observe_redis, setup_metrics, vo_observe_call
from .models import SearchResult
from .opus import router as opus_router
from .query_history import (
    QueryHistoryCreate,
    _internal_create_query_history,
    query_history_router,
)
from .tap import (
    astropy_table_to_list,
    build_select_query,
    build_spatial_icrs_condition,
    build_time_overlap_condition,
    build_where_clause,
    perform_query_with_conditions,
)
from .tap_schema import get_tap_table_columns, tap_supports_columns

MAX_ALIAS_LEN = 32


COORD_SYS_ALIASES: dict[str, str] = {
    "eq_deg": COORD_SYS_EQ_DEG,
    "eq_hms": COORD_SYS_EQ_HMS,
    "hmsdms": COORD_SYS_EQ_HMS,
    "gal": COORD_SYS_GAL,
}


@lru_cache
def _settings() -> Any:
    return get_api_settings()


setup_logging(
    level=_settings().LOG_LEVEL,
    include_access=_settings().LOG_INCLUDE_ACCESS,
    json=_settings().LOG_JSON,
)

logger = logging.getLogger(__name__)

SIMBAD_TAP_SYNC = _settings().SIMBAD_TAP_SYNC
OBJECT_LOOKUP_URL = _settings().NED_OBJECT_LOOKUP_URL


def _is_testing_env() -> bool:
    v = os.getenv("TESTING", "")
    return v.lower() in {"1", "true", "yes", "on"} or "PYTEST_CURRENT_TEST" in os.environ


def _init_redis_for_app(app: FastAPI) -> redis.ConnectionPool | None:
    if _is_testing_env():
        from .tests.fakeredis import FakeRedis

        app.state.redis = FakeRedis()
        logger.info("Using in-memory FakeRedis for tests.")
        return None

    pool = get_api_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool, decode_responses=True)
    logger.info("Redis pool initialised.")
    return pool


async def _safe_close(obj: Any) -> None:
    """Call aclose/close/disconnect if present; await if needed; ignore RuntimeError on shutdown."""
    close = (
        getattr(obj, "aclose", None)
        or getattr(obj, "close", None)
        or getattr(obj, "disconnect", None)
    )
    if not close:
        return
    with suppress(RuntimeError):
        res = close()
        if inspect.isawaitable(res):
            await res


# App Event Handlers for Redis Pool
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("API starting up")
    pool = _init_redis_for_app(app)
    try:
        yield
    finally:
        r = getattr(app.state, "redis", None)
        if r is not None:
            await _safe_close(r)
        if pool is not None:
            await _safe_close(pool)
        logger.info("Redis resources closed.")


docs_enabled = _settings().ENABLE_DOCS

app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access and analyse high-energy astrophysics data from CTAO",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_enabled else None,
)


@app.on_event("shutdown")
async def _shutdown() -> None:
    r = getattr(app.state, "redis", None)
    if r is not None:
        await _safe_close(r)

    await close_redis()
    await close_engine()


@app.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    return {"status": "ok"}


setup_metrics(app)

logger.info("API starting up")

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


class ConvertReq(BaseModel):
    value: str
    input_format: Literal["isot", "mjd", "met"] = "isot"
    input_scale: Literal["utc", "tt", "tai"] = "utc"
    # MET only:
    met_epoch_isot: str | None = None
    met_epoch_scale: Literal["utc", "tt", "tai"] | None = "utc"


class ConvertResp(BaseModel):
    utc_isot: str
    utc_mjd: float
    tt_isot: str
    tt_mjd: float


FieldValue = str | float | int


class FieldBox(TypedDict):
    value: FieldValue


@app.post("/api/convert_time", response_model=ConvertResp, tags=["time"])
def convert_time(req: ConvertReq) -> ConvertResp:
    # Build Time object from the request
    if req.input_format == "met":
        if not req.met_epoch_isot:
            raise HTTPException(status_code=400, detail="met_epoch_isot required for MET.")
        iso = req.met_epoch_isot or ""
        scale = req.met_epoch_scale or "utc"
        if iso.endswith("Z") and scale != "utc":
            iso = iso[:-1]
        epoch = Time(iso, format="isot", scale=scale)
        # epoch = Time(req.met_epoch_isot, format="isot", scale=req.met_epoch_scale or "utc")
        try:
            seconds = float(str(req.value).replace(",", "."))
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=400, detail="MET value must be numeric (seconds)."
            ) from e
        t = epoch + seconds * u.s
    elif req.input_format == "mjd":
        try:
            mjd = float(str(req.value).replace(",", "."))
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail="MJD value must be numeric.") from e
        t = Time(mjd, format="mjd", scale=req.input_scale)
    else:  # "isot"
        t = Time(req.value, format="isot", scale=req.input_scale)

    return ConvertResp(
        utc_isot=t.utc.isot,
        utc_mjd=float(t.utc.mjd),
        tt_isot=t.tt.isot,
        tt_mjd=float(t.tt.mjd),
    )


async def _ned_resolve_via_objectlookup(name: str) -> dict[str, Any] | None:
    """
    Returns {'service','name','ra','dec'} or None if not found/error.
    """
    form = {"json": json.dumps({"name": {"v": name}})}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    t0 = time.perf_counter()
    ok = False
    try:
        resp = await asyncio.to_thread(
            requests.post, OBJECT_LOOKUP_URL, data=form, headers=headers, timeout=5
        )
        resp.raise_for_status()
        ok = True
    except Exception as e:
        logger.exception("NED ObjectLookup failed: %s", e)
        return None
    finally:
        vo_observe_call("ned-objectlookup", OBJECT_LOOKUP_URL, time.perf_counter() - t0, ok)

    obj = cast(dict[str, Any], resp.json())
    if obj.get("ResultCode") == 3:
        interp = obj["Interpreted"]
        pos = obj["Preferred"]["Position"]
        return {
            "service": "NED",
            "name": interp["Name"],
            "ra": float(pos["RA"]),
            "dec": float(pos["Dec"]),
        }
    return None


CATALOG_SPACED_RE = re.compile(
    r"^\s*(?P<cat>M|NGC|IC)\s{0,2}0*(?P<num>\d{1,4})\s*$",
    re.IGNORECASE,
)


CATALOG_RE = re.compile(r"^(?:M\d{1,3}|NGC\d{1,4}|IC\d{1,4})$", re.IGNORECASE)


def _catalog_variants(name: str) -> Iterator[str]:
    """
    Yield 'M  42', 'M   42', … or 'NGC  3242', etc., matching SIMBAD's
    fixed-width alias layout. If `name` is not a Messier/NGC/IC code, yields nothing.
    """
    s = name.strip()
    if len(s) > MAX_ALIAS_LEN:
        return

    m = CATALOG_SPACED_RE.fullmatch(s)
    if not m:
        return

    cat = m.group("cat").upper()
    num = m.group("num")

    # Enforce maximum digits per catalog (Messier ≤3, others ≤4)
    if cat == "M" and len(num) > 3:
        return

    width = 3 if cat == "M" else 4
    spaces_needed = max(1, width - len(num))
    for n_spaces in range(spaces_needed, spaces_needed + 3):
        yield f"{cat}{' ' * n_spaces}{num}"


def _is_short_catalog(q: str) -> bool:
    return bool(CATALOG_RE.match(q.strip()))


def _adql_escape(s: str) -> str:
    return s.replace("'", "''")


def _run_tap_sync(url: str, adql: str, maxrec: int = 50) -> Table:
    t0 = time.perf_counter()
    ok = False
    try:
        params: dict[str, str | int] = {
            "QUERY": adql,
            "LANG": "ADQL",
            "REQUEST": "doQuery",
            "FORMAT": "votable",
            "MAXREC": maxrec,
        }
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        ok = True
        return parse_single_table(BytesIO(r.content)).to_table()
    finally:
        vo_observe_call("simbad-tap", url, time.perf_counter() - t0, ok)


async def _simbad_suggest(prefix: str, limit: int) -> list[dict[str, Any]]:
    q = prefix.strip()
    if len(q) < 2:
        return []

    q_uc = q.upper()
    rows: list[str] = []

    exact_sql = (
        f"SELECT TOP 1 b.main_id "
        f"FROM ident i JOIN basic b ON i.oidref = b.oid "
        f"WHERE i.id = '{_adql_escape(q_uc)}'"
    )
    try:
        tab = await asyncio.to_thread(_run_tap_sync, SIMBAD_TAP_SYNC, exact_sql, 1)
        rows.extend(str(r["main_id"]).strip() for r in cast(Iterable[Mapping[str, Any]], tab))
    except Exception as exc:  # pragma: no cover
        logger.exception("SIMBAD exact failed: %s", exc)

    pat_raw = _adql_escape(q)
    pat_title = _adql_escape(q.title())
    pat_name = f"NAME {_adql_escape(q.title())}"

    alias_sql = (
        f"SELECT DISTINCT TOP 200 b.main_id "
        f"FROM ident i JOIN basic b ON i.oidref = b.oid "
        f"WHERE i.id LIKE '{pat_raw}%' "
        f"   OR i.id LIKE '{pat_title}%' "
        f"   OR i.id LIKE '{pat_name}%'"
    )
    try:
        tab = await asyncio.to_thread(_run_tap_sync, SIMBAD_TAP_SYNC, alias_sql, 200)
        rows.extend(str(r["main_id"]).strip() for r in tab)
    except Exception as exc:  # pragma: no cover
        logger.exception("SIMBAD alias LIKE failed: %s", exc)

    q_cmp = q_uc.replace(" ", "")
    scored = []
    for n in rows:
        n_cmp = n.upper().replace(" ", "")
        score = 0 if n_cmp == q_cmp else 1 if n_cmp.startswith(q_cmp) else 2
        scored.append((score, len(n_cmp), n))

    seen, ordered = set(), []
    for _, _, n in sorted(scored):
        if n not in seen:
            ordered.append(n)
            seen.add(n)
            if len(ordered) == limit:
                break

    return [{"service": "SIMBAD", "name": n} for n in ordered]


async def _ned_suggest(prefix: str, limit: int) -> list[dict[str, str]]:
    """
    Returns up to `limit` suggestions via the ObjectLookup FuzzyMatches.
    """
    q = prefix.strip()
    if len(q) < 2:
        return []

    form = {"json": json.dumps({"name": {"v": q}})}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = await asyncio.to_thread(
            requests.post, OBJECT_LOOKUP_URL, data=form, headers=headers, timeout=5
        )
        resp.raise_for_status()
        doc = resp.json()
    except Exception as e:
        logger.exception("NED ObjectLookup failed: %s", e)
        return []

    suggestions = []
    code = doc.get("ResultCode")
    if code == 1:
        for entry in doc.get("FuzzyMatches", []):
            name = entry.get("Name")
            if name:
                suggestions.append(name)
    elif code == 3:
        nm = doc.get("Interpreted", {}).get("Name")
        if nm:
            suggestions.append(nm)

    seen, out = set(), []
    for n in suggestions:
        if n not in seen:
            seen.add(n)
            out.append({"service": "NED", "name": n})
            if len(out) >= limit:
                break
    return out


class SuggestResult(TypedDict):
    results: list[dict[str, Any]]


@app.get("/api/object_suggest", tags=["object_resolve"])
async def object_suggest(
    q: str = Query(..., min_length=2, max_length=50),
    use_simbad: bool = True,
    use_ned: bool = False,
    limit: int = 15,
) -> SuggestResult:
    q = q.strip()
    if len(q) < 4 and not _is_short_catalog(q):
        return {"results": []}
    if not (use_simbad or use_ned):
        return {"results": []}

    cache_key = f"suggest:{q.lower()}:{use_simbad}:{use_ned}:{limit}"
    if hasattr(app.state, "redis"):
        t0 = time.perf_counter()
        ok = False
        cached = await app.state.redis.get(cache_key)
        ok = True
        observe_redis("get", time.perf_counter() - t0, ok)
        if cached:
            cache_hit("suggest")
            cached_obj = cast(
                SuggestResult,
                json.loads(cached.decode() if isinstance(cached, bytes) else cached),
            )
            return cached_obj
        else:
            cache_miss("suggest")

    tasks = []
    if use_simbad:
        tasks.append(_simbad_suggest(q, limit))
    else:
        tasks.append(asyncio.sleep(0, result=[]))
    if use_ned:
        tasks.append(_ned_suggest(q, limit))
    else:
        tasks.append(asyncio.sleep(0, result=[]))

    simbad_list, ned_list = await asyncio.gather(*tasks)

    # round-robin merge up to `limit` entries
    merged = []
    for sim, ned in itertools.zip_longest(simbad_list, ned_list, fillvalue=None):
        if sim:
            merged.append(sim)
            if len(merged) >= limit:
                break
        if ned:
            merged.append(ned)
            if len(merged) >= limit:
                break

    results: list[dict[str, Any]] = merged[:limit]

    # store in redis for 24 h
    if hasattr(app.state, "redis"):
        t0 = time.perf_counter()
        ok = False
        await app.state.redis.set(cache_key, json.dumps({"results": results}), ex=86400)
        ok = True
        observe_redis("set", time.perf_counter() - t0, ok)

    return {"results": results}


class SearchCoordsParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    coordinate_system: str | None = None
    ra: float | None = None
    dec: float | None = None
    l_deg: float | None = Field(default=None, alias="l")
    b_deg: float | None = Field(default=None, alias="b")
    search_radius: float = 5.0

    obs_start: str | None = None
    obs_end: str | None = None
    mjd_start: float | None = None
    mjd_end: float | None = None
    time_scale: str = "tt"

    energy_min: float | None = None
    energy_max: float | None = None

    tracking_mode: str | None = None
    pointing_mode: str | None = None
    obs_mode: str | None = None

    proposal_id: str | None = None
    proposal_title: str | None = None
    proposal_contact: str | None = None
    proposal_type: str | None = None

    moon_level: str | None = None
    sky_brightness: str | None = None

    tap_url: str
    obscore_table: str

    @field_validator(
        "proposal_id",
        "proposal_title",
        "proposal_contact",
        "proposal_type",
        "tracking_mode",
        "pointing_mode",
        "obs_mode",
        "moon_level",
        "sky_brightness",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


# helpers


def get_search_coords_params(request: Request) -> SearchCoordsParams:
    raw = dict(request.query_params)

    tap_url = (raw.get("tap_url") or "").strip()
    obscore = (raw.get("obscore_table") or "").strip()

    if not tap_url:
        raw["tap_url"] = _settings().DEFAULT_TAP_URL
    if not obscore:
        raw["obscore_table"] = _settings().DEFAULT_OBSCORE_TABLE

    return SearchCoordsParams.model_validate(raw)


def _esc_adql_str(s: str) -> str:
    return (s or "").replace("'", "''")


def _norm_opt(s: str | None) -> str | None:
    v = (s or "").strip()
    return v or None


@dataclass
class _TimeInfo:
    present: bool
    mjd_start_tt: float | None = None
    mjd_end_tt: float | None = None


def _process_mjd_range(params: SearchCoordsParams) -> _TimeInfo | None:
    if params.mjd_start is None or params.mjd_end is None:
        return None

    min_mjd, max_mjd = 0, 100000
    if not (min_mjd <= params.mjd_start <= max_mjd and min_mjd <= params.mjd_end <= max_mjd):
        raise HTTPException(
            status_code=400,
            detail=f"MJD values out of expected range ({min_mjd}-{max_mjd}).",
        )
    if params.mjd_end <= params.mjd_start:
        raise HTTPException(status_code=400, detail="mjd_end must be greater than mjd_start.")

    scale = (params.time_scale or "tt").lower()
    if scale not in ("tt", "utc"):
        scale = "tt"

    if scale == "utc":
        start_tt = Time(params.mjd_start, format="mjd", scale="utc").tt.mjd
        end_tt = Time(params.mjd_end, format="mjd", scale="utc").tt.mjd
    else:
        start_tt, end_tt = params.mjd_start, params.mjd_end

    return _TimeInfo(True, float(start_tt), float(end_tt))


def _process_obs_range(params: SearchCoordsParams) -> _TimeInfo | None:
    if not params.obs_start and not params.obs_end:
        return None
    if not (params.obs_start and params.obs_end):
        raise HTTPException(status_code=400, detail="Both obs_start and obs_end are required.")

    try:
        dt_start = datetime.strptime(params.obs_start, "%d/%m/%Y %H:%M:%S")
        dt_end = datetime.strptime(params.obs_end, "%d/%m/%Y %H:%M:%S")
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid date/time format or value: {e}"
        ) from e

    if dt_end <= dt_start:
        raise HTTPException(status_code=400, detail="obs_end must be after obs_start.")

    scale = (params.time_scale or "tt").lower()
    if scale not in ("tt", "utc"):
        raise HTTPException(status_code=400, detail=f"Unsupported time_scale '{params.time_scale}'")

    try:
        if scale == "utc":
            t_start_tt = Time(dt_start, format="datetime", scale="utc").tt
            t_end_tt = Time(dt_end, format="datetime", scale="utc").tt
        else:
            t_start_tt = Time(dt_start, format="datetime", scale="tt")
            t_end_tt = Time(dt_end, format="datetime", scale="tt")
    except (ValueError, TypeError) as e:
        logger.error("Unexpected error during time processing.")
        raise HTTPException(status_code=500, detail="Error processing time parameters.") from e

    return _TimeInfo(True, float(t_start_tt.mjd), float(t_end_tt.mjd))


def _process_time(params: SearchCoordsParams) -> _TimeInfo:
    out = _process_mjd_range(params)
    if out is not None:
        return out
    out = _process_obs_range(params)
    if out is not None:
        return out
    return _TimeInfo(False)


@dataclass
class _CoordInfo:
    present: bool
    ra_deg: float | None = None
    dec_deg: float | None = None
    coordinate_system: str | None = None


def _process_coords(params: SearchCoordsParams) -> _CoordInfo:
    cs = params.coordinate_system
    if cs is not None:
        cs = COORD_SYS_ALIASES.get(cs, cs)

    if cs in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
        if params.ra is not None and params.dec is not None:
            return _CoordInfo(True, float(params.ra), float(params.dec), cs)
        return _CoordInfo(False, None, None, cs)

    if cs == COORD_SYS_GAL:
        if params.l_deg is not None and params.b_deg is not None:
            try:
                c_gal = SkyCoord(params.l_deg * u.deg, params.b_deg * u.deg, frame="galactic")
                c_icrs = c_gal.icrs
                return _CoordInfo(True, float(c_icrs.ra.deg), float(c_icrs.dec.deg), cs)
            except Exception as e:
                logger.error("Galactic conversion failed: %s", e)
                raise HTTPException(
                    status_code=400, detail="Invalid galactic coordinates provided."
                ) from e
        return _CoordInfo(False, None, None, cs)

    return _CoordInfo(False, None, None, cs)


def _validate_at_least_one_criterion(
    coords_present: bool,
    time_present: bool,
    energy_filter_requested: bool,
    other_filter_requested: bool,
) -> None:
    if not (coords_present or time_present or energy_filter_requested or other_filter_requested):
        raise HTTPException(status_code=400, detail="Provide at least one search criterion.")


def _build_fields_base(params: SearchCoordsParams) -> dict[str, Any]:
    return {
        "tap_url": {"value": params.tap_url},
        "obscore_table": {"value": params.obscore_table},
        "search_radius": {"value": params.search_radius},
    }


def _build_cache_key_from_adql(adql_query_str: str) -> str:
    return "search:" + hashlib.sha256(adql_query_str.encode()).hexdigest()


async def _redis_get_cached(redis_client: Any, cache_key: str) -> SearchResult | None:
    t0 = time.perf_counter()
    ok = False
    cached: str | None
    try:
        cached = await redis_client.get(cache_key)
        ok = True
    except Exception:
        cached = None
        logger.warning("Redis get failed for key=%s", cache_key, exc_info=True)
    finally:
        observe_redis("get", time.perf_counter() - t0, ok)

    if cached:
        cache_hit("search")
        return SearchResult.model_validate_json(cached)

    cache_miss("search")
    return None


async def _redis_set_cached(redis_client: Any, cache_key: str, obj: SearchResult, ttl: int) -> None:
    t0 = time.perf_counter()
    ok = False
    try:
        await redis_client.set(cache_key, obj.model_dump_json(), ex=ttl)
        ok = True
    except Exception:
        logger.warning("Redis set failed for key=%s", cache_key, exc_info=True)
    finally:
        observe_redis("set", time.perf_counter() - t0, ok)


def _augment_with_datalink(
    base_api_url: str, columns: list[str], data: list[list[Any]]
) -> tuple[list[str], list[list[Any]]]:
    if "obs_publisher_did" not in columns:
        return columns, data

    datalink_col = "datalink_url"
    columns_with = columns[:]
    if datalink_col not in columns_with:
        columns_with.append(datalink_col)

    did_idx = columns_with.index("obs_publisher_did")
    datalink_idx = columns_with.index(datalink_col)

    new_rows: list[list[Any]] = []
    for original_row in data:
        new_row = original_row[:]
        while len(new_row) < len(columns_with):
            new_row.append(None)

        did = new_row[did_idx] if did_idx < len(new_row) else None
        if did:
            encoded_did = urllib.parse.quote(str(did), safe="")
            new_row[datalink_idx] = f"{base_api_url}/api/datalink?ID={encoded_did}"
        new_rows.append(new_row)

    return columns_with, new_rows


def _add_if(dst: dict[str, Any], key: str, val: Any) -> None:
    if val is not None and val != "":
        dst[key] = val


def _build_history_params(params: SearchCoordsParams, coord: _CoordInfo) -> dict[str, Any]:
    out: dict[str, Any] = {
        "tap_url": params.tap_url,
        "obscore_table": params.obscore_table,
        "search_radius": params.search_radius,
        "coordinate_system": coord.coordinate_system,
    }

    # coords
    if coord.coordinate_system in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
        _add_if(out, "ra", params.ra)
        _add_if(out, "dec", params.dec)
    elif coord.coordinate_system == COORD_SYS_GAL:
        _add_if(out, "l", params.l_deg)
        _add_if(out, "b", params.b_deg)

    # time
    _add_if(out, "obs_start_input", params.obs_start)
    _add_if(out, "obs_end_input", params.obs_end)
    _add_if(out, "mjd_start", params.mjd_start)
    _add_if(out, "mjd_end", params.mjd_end)
    _add_if(out, "time_scale", params.time_scale)

    # energy
    _add_if(out, "energy_min", params.energy_min)
    _add_if(out, "energy_max", params.energy_max)

    # other filters
    _add_if(out, "tracking_mode", params.tracking_mode)
    _add_if(out, "pointing_mode", params.pointing_mode)
    _add_if(out, "obs_mode", params.obs_mode)
    _add_if(out, "proposal_id", params.proposal_id)
    _add_if(out, "proposal_title", params.proposal_title)
    _add_if(out, "proposal_contact", params.proposal_contact)
    _add_if(out, "proposal_type", params.proposal_type)
    _add_if(out, "moon_level", params.moon_level)
    _add_if(out, "sky_brightness", params.sky_brightness)

    return out


async def _save_history_if_any(
    *,
    identity: VerifiedIdentity | None,
    params: SearchCoordsParams,
    coord: _CoordInfo,
    db_session: AsyncSession,
    search_result_obj: SearchResult,
) -> None:
    if not identity:
        return
    user_sub = identity.sub
    try:
        params_to_save = _build_history_params(params, coord)
        history_payload = QueryHistoryCreate(
            query_params=params_to_save,
            results=search_result_obj.model_dump(),
        )
        await _internal_create_query_history(
            history=history_payload, user_sub=user_sub, session=db_session
        )
    except Exception:
        logger.exception("saving query history failed")


# Optional filter + TAP column handling


@dataclass
class _TapColumnContext:
    tap_schema_available: bool
    tap_cols: set[str]
    ignored_optional_filters: list[str]
    requested_optional_filters: list[str]
    applied_optional_filters: list[str]
    optional_filter_probe_failed: bool
    probe_cache: dict[str, bool]


async def _discover_tap_columns(tap_url: str, obscore_table: str) -> tuple[bool, set[str]]:
    try:
        cols = await get_tap_table_columns(tap_url, obscore_table)
        cols_norm = {c.lower() for c in cols} if cols else set()
        return bool(cols_norm), cols_norm
    except Exception as e:
        logger.warning(
            "search_coords: TAP_SCHEMA lookup failed (%s). Optional filters may require fallback probing.",
            e,
        )
        return False, set()


async def _optional_col_exists(
    *,
    ctx: _TapColumnContext,
    tap_url: str,
    obscore_table: str,
    col: str,
) -> bool:
    # Use TAP_SCHEMA when available; otherwise probe actual table (cached per request).
    if ctx.tap_schema_available:
        return col.lower() in ctx.tap_cols

    if col in ctx.probe_cache:
        return ctx.probe_cache[col]

    try:
        exists = await tap_supports_columns(tap_url, obscore_table, [col])
        ctx.probe_cache[col] = bool(exists)
        return bool(exists)
    except Exception as e:
        logger.warning(
            "Optional column probe failed for tap_url=%s table=%s col=%s (%s)",
            tap_url,
            obscore_table,
            col,
            e,
            exc_info=True,
        )
        raise


async def _add_optional_enum_eq(
    *,
    ctx: _TapColumnContext,
    where_conditions: list[str],
    tap_url: str,
    obscore_table: str,
    col: str,
    val: str | None,
) -> None:
    if not val:
        return
    ctx.requested_optional_filters.append(col)
    try:
        if await _optional_col_exists(
            ctx=ctx, tap_url=tap_url, obscore_table=obscore_table, col=col
        ):
            where_conditions.append(f"{col} = '{_esc_adql_str(val)}'")
            ctx.applied_optional_filters.append(col)
        else:
            ctx.ignored_optional_filters.append(col)
    except Exception:
        ctx.optional_filter_probe_failed = True
        ctx.ignored_optional_filters.append(col)


async def _add_optional_text_eq(
    *,
    ctx: _TapColumnContext,
    where_conditions: list[str],
    tap_url: str,
    obscore_table: str,
    col: str,
    val: str | None,
) -> None:
    v = _norm_opt(val)
    if not v:
        return
    ctx.requested_optional_filters.append(col)
    try:
        if await _optional_col_exists(
            ctx=ctx, tap_url=tap_url, obscore_table=obscore_table, col=col
        ):
            where_conditions.append(f"{col} = '{_esc_adql_str(v)}'")
            ctx.applied_optional_filters.append(col)
        else:
            ctx.ignored_optional_filters.append(col)
    except Exception:
        ctx.optional_filter_probe_failed = True
        ctx.ignored_optional_filters.append(col)


async def _add_optional_text_like(
    *,
    ctx: _TapColumnContext,
    where_conditions: list[str],
    tap_url: str,
    obscore_table: str,
    col: str,
    val: str | None,
) -> None:
    v = _norm_opt(val)
    if not v:
        return
    ctx.requested_optional_filters.append(col)
    try:
        if await _optional_col_exists(
            ctx=ctx, tap_url=tap_url, obscore_table=obscore_table, col=col
        ):
            where_conditions.append(f"ivo_nocasematch({col}, '%{_esc_adql_str(v)}%') = 1")
            ctx.applied_optional_filters.append(col)
        else:
            ctx.ignored_optional_filters.append(col)
    except Exception:
        ctx.optional_filter_probe_failed = True
        ctx.ignored_optional_filters.append(col)


async def _apply_energy_filter(
    *,
    params: SearchCoordsParams,
    tap_schema_available: bool,
    tap_cols: set[str],
    where_conditions: list[str],
) -> None:
    energy_filter_requested = (params.energy_min is not None) or (params.energy_max is not None)
    if not energy_filter_requested:
        return

    have_energy_cols = False
    if tap_schema_available:
        have_energy_cols = ("energy_min" in tap_cols) and ("energy_max" in tap_cols)
    else:
        try:
            have_energy_cols = await tap_supports_columns(
                params.tap_url, params.obscore_table, ["energy_min", "energy_max"]
            )
        except Exception as e:
            logger.warning("Energy column probe failed (tap service error).", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Energy filtering could not be validated because the TAP service returned an error while "
                    "checking column availability. Please try again later or choose another TAP table."
                ),
            ) from e

    if not have_energy_cols:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Energy filtering requires columns 'energy_min' and 'energy_max' to be present in '{params.obscore_table}', "
                "but they were not found. Please choose a table that provides energy columns, or disable Energy Search."
            ),
        )

    # Overlap logic
    # Energy filtering (UI inputs are TeV, hess_dr.obscore energy_* columns are eV)
    TEV_TO_EV = 1e12
    if params.energy_min is not None:
        where_conditions.append(f"energy_max >= {float(params.energy_min) * TEV_TO_EV:g}")
    if params.energy_max is not None:
        where_conditions.append(f"energy_min <= {float(params.energy_max) * TEV_TO_EV:g}")


def _validate_optional_filters_outcome(
    *,
    coords_present: bool,
    time_present: bool,
    energy_filter_requested: bool,
    ctx: _TapColumnContext,
) -> None:
    if ctx.ignored_optional_filters:
        logger.info(
            "search_coords: Ignored optional filters (missing columns or probe failure): %s",
            sorted(set(ctx.ignored_optional_filters)),
        )

    if (
        ctx.requested_optional_filters
        and ctx.applied_optional_filters
        and not ctx.tap_schema_available
    ):
        logger.info(
            "search_coords: Applied optional filters via fallback column probe (TAP_SCHEMA unavailable): %s",
            sorted(set(ctx.applied_optional_filters)),
        )

    only_optional_filters_requested = not (
        coords_present or time_present or energy_filter_requested
    )

    if (
        ctx.requested_optional_filters
        and not ctx.applied_optional_filters
        and only_optional_filters_requested
    ):
        if ctx.optional_filter_probe_failed:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The requested optional filters could not be validated because the TAP service returned an error "
                    "while checking column availability. Please try again later, choose another table/service, or add "
                    "coordinates/time criteria to narrow the search."
                ),
            )

        raise HTTPException(
            status_code=400,
            detail=(
                "The requested optional filters could not be applied because the selected table does not "
                f"provide the required columns: {', '.join(sorted(set(ctx.ignored_optional_filters)))}."
            ),
        )


def _apply_time_coord_fields(
    fields: dict[str, Any],
    time_info: _TimeInfo,
    coord: _CoordInfo,
) -> tuple[bool, bool]:
    """Apply processed time/coord info into fields and return (coords_present, time_present)."""
    if time_info.present:
        if time_info.mjd_start_tt is None or time_info.mjd_end_tt is None:
            raise HTTPException(status_code=500, detail="Internal error: time range is incomplete.")
        fields["search_mjd_start"] = {"value": float(time_info.mjd_start_tt)}
        fields["search_mjd_end"] = {"value": float(time_info.mjd_end_tt)}

    if coord.present:
        if coord.ra_deg is None or coord.dec_deg is None:
            raise HTTPException(
                status_code=500, detail="Internal error: coordinates are incomplete."
            )
        fields["target_raj2000"] = {"value": float(coord.ra_deg)}
        fields["target_dej2000"] = {"value": float(coord.dec_deg)}

    return coord.present, time_info.present


# implementation function for search_coords


async def search_coords_impl(
    *,
    request: Request,
    params: SearchCoordsParams,
    identity: VerifiedIdentity | None,
    db_session: AsyncSession,
    redis_client: Any,
) -> SearchResult:
    CACHE_TTL = 3600
    base_api_url = str(request.base_url).rstrip("/")

    fields: dict[str, Any] = _build_fields_base(params)

    # TAP columns
    tap_schema_available, tap_cols = await _discover_tap_columns(
        params.tap_url, params.obscore_table
    )

    # Time + coords (normalized)
    time_info = _process_time(params)
    coord = _process_coords(params)
    coords_present, time_present = _apply_time_coord_fields(fields, time_info, coord)

    # Determine whether any criteria were provided
    energy_filter_requested = (params.energy_min is not None) or (params.energy_max is not None)
    other_filter_requested = any(
        v is not None
        for v in (
            params.tracking_mode,
            params.pointing_mode,
            params.obs_mode,
            params.proposal_id,
            params.proposal_title,
            params.proposal_contact,
            params.proposal_type,
            params.moon_level,
            params.sky_brightness,
        )
    )
    _validate_at_least_one_criterion(
        coords_present, time_present, energy_filter_requested, other_filter_requested
    )

    where_conditions: list[str] = []

    # Spatial / time WHERE clauses
    if coords_present:
        where_conditions.append(
            build_spatial_icrs_condition(
                float(fields["target_raj2000"]["value"]),
                float(fields["target_dej2000"]["value"]),
                float(fields["search_radius"]["value"]),
            )
        )

    if time_present:
        where_conditions.append(
            build_time_overlap_condition(
                float(fields["search_mjd_start"]["value"]),
                float(fields["search_mjd_end"]["value"]),
            )
        )

    # Energy filter
    await _apply_energy_filter(
        params=params,
        tap_schema_available=tap_schema_available,
        tap_cols=tap_cols,
        where_conditions=where_conditions,
    )

    # Optional filters
    ctx = _TapColumnContext(
        tap_schema_available=tap_schema_available,
        tap_cols=tap_cols,
        ignored_optional_filters=[],
        requested_optional_filters=[],
        applied_optional_filters=[],
        optional_filter_probe_failed=False,
        probe_cache={},
    )

    enum_filters: list[tuple[str, str | None]] = [
        ("tracking_type", params.tracking_mode),
        ("pointing_mode", params.pointing_mode),
        ("obs_mode", params.obs_mode),
        ("proposal_type", params.proposal_type),
        ("moon_level", params.moon_level),
        ("sky_brightness", params.sky_brightness),
    ]
    for col, val in enum_filters:
        await _add_optional_enum_eq(
            ctx=ctx,
            where_conditions=where_conditions,
            tap_url=params.tap_url,
            obscore_table=params.obscore_table,
            col=col,
            val=val,
        )

    await _add_optional_text_eq(
        ctx=ctx,
        where_conditions=where_conditions,
        tap_url=params.tap_url,
        obscore_table=params.obscore_table,
        col="proposal_id",
        val=params.proposal_id,
    )
    await _add_optional_text_like(
        ctx=ctx,
        where_conditions=where_conditions,
        tap_url=params.tap_url,
        obscore_table=params.obscore_table,
        col="proposal_title",
        val=params.proposal_title,
    )
    await _add_optional_text_like(
        ctx=ctx,
        where_conditions=where_conditions,
        tap_url=params.tap_url,
        obscore_table=params.obscore_table,
        col="proposal_contact",
        val=params.proposal_contact,
    )

    _validate_optional_filters_outcome(
        coords_present=coords_present,
        time_present=time_present,
        energy_filter_requested=energy_filter_requested,
        ctx=ctx,
    )

    # Build ADQL once
    where_sql = build_where_clause(where_conditions)
    adql_query_str = build_select_query(str(fields["obscore_table"]["value"]), where_sql, limit=100)
    cache_key = _build_cache_key_from_adql(adql_query_str)

    # Redis cache GET (instrumented)
    if redis_client:
        cached_obj = await _redis_get_cached(redis_client, cache_key)
        if cached_obj is not None:
            return cached_obj

    # Execute query
    try:
        error, res_table, _ = perform_query_with_conditions(fields, where_conditions, limit=100)
    except Exception as e:
        logger.error("search_coords: Exception during perform_query call: %s", e)
        raise HTTPException(status_code=500, detail="Failed during query execution.") from e

    if error is not None:
        logger.error("search_coords: Query function returned error: %s", error)
        raise HTTPException(status_code=400, detail=error)

    # Results processing + datalink + Redis SET + history
    try:
        columns, data = astropy_table_to_list(res_table)
        columns_list = list(columns) if columns else []
        data_list = [list(row) for row in data] if data else []

        columns_with, data_with = _augment_with_datalink(base_api_url, columns_list, data_list)
        search_result_obj = SearchResult(columns=columns_with, data=data_with)

        if redis_client:
            await _redis_set_cached(redis_client, cache_key, search_result_obj, CACHE_TTL)

        await _save_history_if_any(
            identity=identity,
            params=params,
            coord=coord,
            db_session=db_session,
            search_result_obj=search_result_obj,
        )

        return search_result_obj

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR search_coords: Exception during results processing: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal error processing search results."
        ) from e


# Public route (thin wrapper)


@app.get("/api/search_coords", response_model=SearchResult, tags=["search"])
async def search_coords(
    request: Request,
    params: SearchCoordsParams = Depends(get_search_coords_params),
    identity: VerifiedIdentity | None = Depends(get_optional_identity),
    db_session: AsyncSession = Depends(get_async_session),
) -> SearchResult:
    redis_client = getattr(app.state, "redis", None)
    return await search_coords_impl(
        request=request,
        params=params,
        identity=identity,
        db_session=db_session,
        redis_client=redis_client,
    )


def _simbad_search_aliases(
    simbad: vo.dal.TAPService, alias: str, top: int = 1
) -> Sequence[Mapping[str, Any]]:
    sql = (
        f"SELECT TOP {top} ra, dec, main_id "
        "FROM ident i JOIN basic b ON b.oid = i.oidref "
        f"WHERE i.id = '{_adql_escape(alias)}'"
    )
    try:
        res = simbad.search(sql)
        return cast(Sequence[Mapping[str, Any]], res)
    except Exception:
        return []


def _collect_simbad_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ra_val, dec_val = float(row["ra"]), float(row["dec"])
        if math.isnan(ra_val) or math.isnan(dec_val):
            continue
        out.append(
            {
                "service": "SIMBAD",
                "name": str(row["main_id"]).strip(),
                "ra": ra_val,
                "dec": dec_val,
            }
        )
    return out


def _resolve_via_simbad(name: str, tap_base: str) -> list[dict[str, Any]]:
    """Best-effort resolve using SIMBAD with several alias variants."""
    simbad = vo.dal.TAPService(tap_base)
    alias_raw = name.strip()

    # Try candidates in order
    candidates: list[str] = [alias_raw]
    candidates.extend(list(_catalog_variants(alias_raw)))
    candidates.append(alias_raw.title())
    candidates.append(alias_raw.upper())
    if not alias_raw.upper().startswith("NAME "):
        candidates.append("NAME " + alias_raw.title())

    seen: set[tuple[str, float, float]] = set()
    results: list[dict[str, Any]] = []

    for alias in candidates:
        rows = _simbad_search_aliases(simbad, alias, top=1)
        for item in _collect_simbad_rows(rows):
            key = (item["name"], item["ra"], item["dec"])
            if key not in seen:
                seen.add(key)
                results.append(item)

    return results


@app.post("/api/object_resolve", tags=["object_resolve"])
async def object_resolve(data: dict = Body(...)) -> dict[str, list[dict[str, Any]]]:
    """
    Unified endpoint to resolve an object name from either/both SIMBAD & NED.
    """
    object_name = str(data.get("object_name", "")).strip()
    use_simbad = bool(data.get("use_simbad", False))
    use_ned = bool(data.get("use_ned", False))

    if not object_name:
        raise HTTPException(status_code=400, detail="No object_name provided.")
    if not (use_simbad or use_ned):
        return {"results": []}

    results: list[dict[str, Any]] = []

    if use_simbad:
        results.extend(_resolve_via_simbad(object_name, _settings().SIMBAD_TAP_BASE))

    if use_ned:
        resolved = await _ned_resolve_via_objectlookup(object_name)
        if resolved:
            results.append(resolved)

    return {"results": results}


def _run_ned_sync_query(adql_query: str) -> list[dict[str, Any]]:
    """
    Helper function to run a synchronous NED TAP query (returns a list of dict).
    By default, NED returns a VOTable. Parse it with astropy.io.votable.
    """
    url = _settings().NED_TAP_SYNC_URL
    params: dict[str, str | int] = {
        "QUERY": adql_query,
        "LANG": "ADQL",
        "REQUEST": "doQuery",
        "FORMAT": "votable",
        "MAXREC": 5000,
    }

    out: list[dict[str, Any]] = []
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        votable_buf = BytesIO(r.content)
        table = parse_single_table(votable_buf).to_table()
        for row in cast(Iterable[Mapping[str, Any]], table):
            ra_val = float(row["ra"])
            dec_val = float(row["dec"])
            pref_val = str(row["prefname"])
            if math.isnan(ra_val) or math.isnan(dec_val):
                continue
            out.append({"ra": ra_val, "dec": dec_val, "prefname": pref_val})
    except Exception as e:
        logger.error("NED query error: %s", e)

    return out


@app.get("/api/datalink", tags=["datalink"])
async def datalink_endpoint(
    ID: list[str] = Query(
        ...,
        description="One or more dataset identifiers (e.g., ivo://padc.obspm/hess#23523)",
    )
) -> Response:
    """
    DataLink endpoint that returns a VOTable containing links for each dataset ID.
    """
    rows = ""
    for id_val in ID:
        if id_val.lower().startswith("ivo://"):
            if "#" in id_val:
                # Extract the portion after '#' (e.g. "23523")
                obs_id_str = id_val.split("#", 1)[1]
                try:
                    obs_id_int = int(obs_id_str)
                    # Format the number with zero-padding to 6 digits
                    formatted_id = f"{obs_id_int:06d}"
                    # Construct the direct download URL from the unique obs_id.
                    direct_download_url = f"https://hess-dr.obspm.fr/retrieve/hess_dl3_dr1_obs_id_{formatted_id}.fits.gz"
                    error_message = ""
                    access_url = direct_download_url
                    service_def = ""
                except Exception:
                    access_url = ""
                    error_message = f"NotFoundFault: Invalid numeric obs id in {id_val}"
                    service_def = ""
            else:
                access_url = ""
                error_message = f"NotFoundFault: Missing '#' in {id_val}"
                service_def = ""
        else:
            access_url = ""
            error_message = (
                f"NotFoundFault: {id_val} is not recognized as a valid ivo:// identifier"
            )
            service_def = ""
        rows += (
            "                <TR>\n"
            f"                  <TD>{id_val}</TD>\n"
            f"                  <TD>{access_url}</TD>\n"
            f"                  <TD>{service_def}</TD>\n"
            f"                  <TD>{error_message}</TD>\n"
            "                </TR>\n"
        )

    votable_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
  <RESOURCE type="results">
    <INFO name="standardID" value="ivo://ivoa.net/std/DataLink#links-1.1"/>
    <TABLE>
      <FIELD name="ID" datatype="char" arraysize="*"/>
      <FIELD name="access_url" datatype="char" arraysize="*"/>
      <FIELD name="service_def" datatype="char" arraysize="*"/>
      <FIELD name="error_message" datatype="char" arraysize="*"/>
      <DATA>
        <TABLEDATA>
{rows}        </TABLEDATA>
      </DATA>
    </TABLE>
  </RESOURCE>
</VOTABLE>
"""
    return Response(content=votable_xml, media_type="application/x-votable+xml")


app.include_router(basket_router)
app.include_router(opus_router)
app.include_router(query_history_router)
app.include_router(coord_router)


# Mount the React build folder
# app.mount("/", StaticFiles(directory="./js/build", html=True), name="js")
STATIC_DIR = os.getenv("STATIC_DIR", "./js/build")
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="js")
else:
    logger.warning("Static build dir '%s' not found; skipping static mount.", STATIC_DIR)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"status": "ok", "app": "CTAO Data Explorer API"}


# Run the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
