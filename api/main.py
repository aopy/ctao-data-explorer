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
import traceback
import urllib.parse
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager, suppress
from datetime import datetime
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
from ctao_shared.config import get_settings
from ctao_shared.constants import (
    COOKIE_NAME_MAIN_SESSION,
    COORD_SYS_EQ_DEG,
    COORD_SYS_EQ_HMS,
    COORD_SYS_GAL,
)
from ctao_shared.db import get_async_session, get_redis_pool
from ctao_shared.logging_config import setup_logging
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.staticfiles import StaticFiles

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
from .session_auth import get_optional_session_user
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

settings = get_settings()

setup_logging(
    level=settings.LOG_LEVEL,
    include_access=settings.LOG_INCLUDE_ACCESS,
    json=settings.LOG_JSON,
)

logger = logging.getLogger(__name__)

SIMBAD_TAP_SYNC = settings.SIMBAD_TAP_SYNC
OBJECT_LOOKUP_URL = settings.NED_OBJECT_LOOKUP_URL
cookie_params = settings.cookie_params


def _is_testing_env() -> bool:
    v = os.getenv("TESTING", "")
    return v.lower() in {"1", "true", "yes", "on"} or "PYTEST_CURRENT_TEST" in os.environ


def _init_redis_for_app(app: FastAPI) -> redis.ConnectionPool | None:
    if _is_testing_env():
        from .tests.fakeredis import FakeRedis

        app.state.redis = FakeRedis()
        logger.info("Using in-memory FakeRedis for tests.")
        return None

    pool = get_redis_pool()
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


docs_enabled = settings.ENABLE_DOCS

app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access and analyse high-energy astrophysics data from CTAO",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_enabled else None,
)


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


@app.middleware("http")
async def rolling_session_cookie(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)

    existing = response.headers.getlist("set-cookie")
    if any(f"{COOKIE_NAME_MAIN_SESSION}=" in hdr for hdr in existing):
        return response

    cookie_name: str = COOKIE_NAME_MAIN_SESSION or "ctao_session_main"
    session_id = request.cookies.get(cookie_name)

    if session_id:
        response.set_cookie(
            cookie_name,
            session_id,
            max_age=settings.SESSION_DURATION_SECONDS,
            **cookie_params,
        )
    return response


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
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="MET value must be numeric (seconds)."
            ) from e
        t = epoch + seconds * u.s
    elif req.input_format == "mjd":
        try:
            mjd = float(str(req.value).replace(",", "."))
        except Exception as e:
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


@app.get("/api/search_coords", response_model=SearchResult, tags=["search"])
async def search_coords(
    request: Request,
    # Coordinate Params
    coordinate_system: str | None = None,
    ra: float | None = None,
    dec: float | None = None,
    l_deg: float | None = Query(None, alias="l"),
    b_deg: float | None = Query(None, alias="b"),
    search_radius: float = 5.0,
    # Time Params
    obs_start: str | None = None,
    obs_end: str | None = None,
    mjd_start: float | None = Query(None),
    mjd_end: float | None = Query(None),
    time_scale: str | None = Query("tt"),
    # Energy Search (TeV)
    energy_min: float | None = Query(None),
    energy_max: float | None = Query(None),
    # Observation Configuration
    tracking_mode: str | None = Query(None),
    pointing_mode: str | None = Query(None),
    obs_mode: str | None = Query(None),
    # Observation Program
    proposal_id: str | None = Query(None),
    proposal_title: str | None = Query(None),
    proposal_contact: str | None = Query(None),
    proposal_type: str | None = Query(None),
    # Observation Conditions
    moon_level: str | None = Query(None),
    sky_brightness: str | None = Query(None),
    # TAP Params
    tap_url: str = settings.DEFAULT_TAP_URL,
    obscore_table: str = settings.DEFAULT_OBSCORE_TABLE,
    # Auth
    user_session_data: dict[str, Any] | None = Depends(get_optional_session_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> SearchResult:
    redis_client = getattr(app.state, "redis", None)
    CACHE_TTL = 3600

    base_api_url = str(request.base_url).rstrip("/")

    fields: dict[str, Any] = {
        "tap_url": {"value": tap_url},
        "obscore_table": {"value": obscore_table},
        "search_radius": {"value": search_radius},
    }

    if coordinate_system is not None:
        coordinate_system = COORD_SYS_ALIASES.get(coordinate_system, coordinate_system)

    coords_present = False
    time_filter_present = False

    where_conditions: list[str] = []

    # TAP_SCHEMA discovery
    ignored_optional_filters: list[str] = []
    try:
        tap_cols = await get_tap_table_columns(tap_url, obscore_table)
    except Exception as e:
        logger.warning(
            "search_coords: TAP_SCHEMA lookup failed (%s). Optional filters may require fallback probing.",
            e,
        )
        tap_cols = set()

    tap_schema_available = bool(tap_cols)

    # Per-request cache for fallback probing of optional columns
    optional_cols_probe_cache: dict[str, bool] = {}

    def col_exists(col: str) -> bool:
        """TAP_SCHEMA-only check."""
        if not tap_schema_available:
            return False
        return col.lower() in tap_cols

    async def optional_col_exists(col: str) -> bool:
        """Return True if optional column exists.
        Use TAP_SCHEMA when available; otherwise probe actual table (cached per request).
        """
        if tap_schema_available:
            return col.lower() in tap_cols

        if col in optional_cols_probe_cache:
            return optional_cols_probe_cache[col]

        try:
            exists = await tap_supports_columns(tap_url, obscore_table, [col])
            optional_cols_probe_cache[col] = bool(exists)
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

    def esc(s: str) -> str:
        return (s or "").replace("'", "''")

    requested_optional_filters: list[str] = []
    applied_optional_filters: list[str] = []
    optional_filter_probe_failed = False

    async def add_optional_enum_eq(col: str, val: str | None) -> None:
        nonlocal optional_filter_probe_failed
        if not val:
            return
        requested_optional_filters.append(col)
        try:
            if await optional_col_exists(col):
                where_conditions.append(f"{col} = '{esc(val)}'")
                applied_optional_filters.append(col)
            else:
                ignored_optional_filters.append(col)
        except Exception:
            optional_filter_probe_failed = True
            ignored_optional_filters.append(col)

    async def add_optional_text_eq(col: str, val: str | None) -> None:
        nonlocal optional_filter_probe_failed
        if not val:
            return
        v = val.strip()
        if not v:
            return
        requested_optional_filters.append(col)
        try:
            if await optional_col_exists(col):
                where_conditions.append(f"{col} = '{esc(v)}'")
                applied_optional_filters.append(col)
            else:
                ignored_optional_filters.append(col)
        except Exception:
            optional_filter_probe_failed = True
            ignored_optional_filters.append(col)

    async def add_optional_text_like(col: str, val: str | None) -> None:
        nonlocal optional_filter_probe_failed
        if not val:
            return
        v = val.strip()
        if not v:
            return
        requested_optional_filters.append(col)
        try:
            if await optional_col_exists(col):
                where_conditions.append(f"ivo_nocasematch({col}, '%{esc(v)}%') = 1")
                applied_optional_filters.append(col)
            else:
                ignored_optional_filters.append(col)
        except Exception:
            optional_filter_probe_failed = True
            ignored_optional_filters.append(col)

    # Time processing (normalize to TT MJD)
    if mjd_start is not None and mjd_end is not None:
        MIN_VALID_MJD = 0
        MAX_VALID_MJD = 100000
        if not (
            MIN_VALID_MJD <= mjd_start <= MAX_VALID_MJD
            and MIN_VALID_MJD <= mjd_end <= MAX_VALID_MJD
        ):
            raise HTTPException(
                status_code=400,
                detail=f"MJD values out of expected range ({MIN_VALID_MJD}-{MAX_VALID_MJD}).",
            )
        if mjd_end <= mjd_start:
            raise HTTPException(status_code=400, detail="mjd_end must be greater than mjd_start.")

        scale = (time_scale or "tt").lower()
        if scale not in ("tt", "utc"):
            scale = "tt"

        if scale == "utc":
            mjd_start_tt = Time(mjd_start, format="mjd", scale="utc").tt.mjd
            mjd_end_tt = Time(mjd_end, format="mjd", scale="utc").tt.mjd
        else:
            mjd_start_tt = mjd_start
            mjd_end_tt = mjd_end

        fields["search_mjd_start"] = {"value": float(mjd_start_tt)}
        fields["search_mjd_end"] = {"value": float(mjd_end_tt)}
        time_filter_present = True

    elif obs_start and obs_end:
        try:
            dt_start = datetime.strptime(obs_start, "%d/%m/%Y %H:%M:%S")
            dt_end = datetime.strptime(obs_end, "%d/%m/%Y %H:%M:%S")
            if dt_end <= dt_start:
                raise HTTPException(status_code=400, detail="obs_end must be after obs_start.")

            scale = (time_scale or "tt").lower()
            if scale not in ("tt", "utc"):
                raise HTTPException(
                    status_code=400, detail=f"Unsupported time_scale '{time_scale}'"
                )

            if scale == "utc":
                t_start_tt = Time(dt_start, format="datetime", scale="utc").tt
                t_end_tt = Time(dt_end, format="datetime", scale="utc").tt
            else:
                t_start_tt = Time(dt_start, format="datetime", scale="tt")
                t_end_tt = Time(dt_end, format="datetime", scale="tt")

            fields["search_mjd_start"] = {"value": float(t_start_tt.mjd)}
            fields["search_mjd_end"] = {"value": float(t_end_tt.mjd)}
            time_filter_present = True
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid date/time format or value: {e}"
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected error during time processing: %s", e)
            raise HTTPException(status_code=500, detail="Error processing time parameters.") from e

    # Coordinate processing
    if coordinate_system in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
        if ra is not None and dec is not None:
            fields["target_raj2000"] = {"value": ra}
            fields["target_dej2000"] = {"value": dec}
            coords_present = True
    elif coordinate_system == COORD_SYS_GAL:
        if l_deg is not None and b_deg is not None:
            try:
                c_gal = SkyCoord(l_deg * u.deg, b_deg * u.deg, frame="galactic")
                c_icrs = c_gal.icrs
                fields["target_raj2000"] = {"value": c_icrs.ra.deg}
                fields["target_dej2000"] = {"value": c_icrs.dec.deg}
                coords_present = True
            except Exception as e:
                logger.error("Galactic conversion failed: %s", e)
                raise HTTPException(
                    status_code=400, detail="Invalid galactic coordinates provided."
                ) from e

    # Normalization (treat empty strings as None)
    proposal_id = (proposal_id or "").strip() or None
    proposal_title = (proposal_title or "").strip() or None
    proposal_contact = (proposal_contact or "").strip() or None
    proposal_type = (proposal_type or "").strip() or None

    tracking_mode = (tracking_mode or "").strip() or None
    pointing_mode = (pointing_mode or "").strip() or None
    obs_mode = (obs_mode or "").strip() or None

    moon_level = (moon_level or "").strip() or None
    sky_brightness = (sky_brightness or "").strip() or None

    # Determine whether any criteria were provided
    energy_filter_requested = (energy_min is not None) or (energy_max is not None)

    other_filter_requested = any(
        v is not None
        for v in [
            tracking_mode,
            pointing_mode,
            obs_mode,
            proposal_id,
            proposal_title,
            proposal_contact,
            proposal_type,
            moon_level,
            sky_brightness,
        ]
    )

    if not (
        coords_present or time_filter_present or energy_filter_requested or other_filter_requested
    ):
        raise HTTPException(status_code=400, detail="Provide at least one search criterion.")

    # Spatial / time WHERE clauses
    if coords_present:
        where_conditions.append(
            build_spatial_icrs_condition(
                float(fields["target_raj2000"]["value"]),
                float(fields["target_dej2000"]["value"]),
                float(fields["search_radius"]["value"]),
            )
        )

    if time_filter_present:
        where_conditions.append(
            build_time_overlap_condition(
                float(fields["search_mjd_start"]["value"]),
                float(fields["search_mjd_end"]["value"]),
            )
        )

    # Energy filtering (TeV)
    if energy_filter_requested:
        have_energy_cols = False

        if tap_schema_available:
            have_energy_cols = col_exists("energy_min") and col_exists("energy_max")
        else:
            # Fallback probe against the actual table
            try:
                have_energy_cols = await tap_supports_columns(
                    tap_url, obscore_table, ["energy_min", "energy_max"]
                )
            except Exception as e:
                logger.warning(
                    "Energy column probe failed for tap_url=%s table=%s (%s)",
                    tap_url,
                    obscore_table,
                    e,
                    exc_info=True,
                )
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
                    f"Energy filtering requires columns 'energy_min' and 'energy_max' to be present in '{obscore_table}', "
                    "but they were not found. Please choose a table that provides energy columns, or disable Energy Search."
                ),
            )

        # Overlap logic
        if energy_min is not None:
            where_conditions.append(f"energy_max >= {float(energy_min)}")
        if energy_max is not None:
            where_conditions.append(f"energy_min <= {float(energy_max)}")

    # Other optional filters
    await add_optional_enum_eq("tracking_type", tracking_mode)
    await add_optional_enum_eq("pointing_mode", pointing_mode)
    await add_optional_enum_eq("obs_mode", obs_mode)

    await add_optional_text_eq("proposal_id", proposal_id)
    await add_optional_text_like("proposal_title", proposal_title)
    await add_optional_text_like("proposal_contact", proposal_contact)
    await add_optional_enum_eq("proposal_type", proposal_type)

    await add_optional_enum_eq("moon_level", moon_level)
    await add_optional_enum_eq("sky_brightness", sky_brightness)

    if ignored_optional_filters:
        logger.info(
            "search_coords: Ignored optional filters (missing columns or probe failure): %s",
            sorted(set(ignored_optional_filters)),
        )

    if requested_optional_filters and applied_optional_filters and not tap_schema_available:
        logger.info(
            "search_coords: Applied optional filters via fallback column probe (TAP_SCHEMA unavailable): %s",
            sorted(set(applied_optional_filters)),
        )

    only_optional_filters_requested = not (
        coords_present or time_filter_present or energy_filter_requested
    )

    if (
        requested_optional_filters
        and not applied_optional_filters
        and only_optional_filters_requested
    ):
        # If probe failed, this is a service validation problem (503)
        if optional_filter_probe_failed:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The requested optional filters could not be validated because the TAP service returned an error "
                    "while checking column availability. Please try again later, choose another table/service, or add "
                    "coordinates/time criteria to narrow the search."
                ),
            )

        # Otherwise, validation succeeded and columns are simply missing (400)
        raise HTTPException(
            status_code=400,
            detail=(
                "The requested optional filters could not be applied because the selected table does not "
                f"provide the required columns: {', '.join(sorted(set(ignored_optional_filters)))}."
            ),
        )

    # Build ADQL once
    where_sql = build_where_clause(where_conditions)
    adql_query_str = build_select_query(str(fields["obscore_table"]["value"]), where_sql, limit=100)

    cache_key = "search:" + hashlib.sha256(adql_query_str.encode()).hexdigest()

    # Redis cache GET (instrumented)
    if redis_client:
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

    # Execute query
    res_table: Table | None = None
    error: str | None = None
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

        columns = list(columns) if columns else []
        data = [list(row) for row in data] if data else []

        # Add datalink_url column if obs_publisher_did present
        columns_with_datalink = columns[:]
        data_with_datalink = data

        if "obs_publisher_did" in columns_with_datalink:
            datalink_col = "datalink_url"
            if datalink_col not in columns_with_datalink:
                columns_with_datalink.append(datalink_col)

            did_idx = columns_with_datalink.index("obs_publisher_did")
            datalink_idx = columns_with_datalink.index(datalink_col)

            new_rows: list[list[Any]] = []
            for original_row in data:
                new_row = original_row[:]
                # ensure slot
                while len(new_row) < len(columns_with_datalink):
                    new_row.append(None)

                did = new_row[did_idx] if did_idx < len(new_row) else None
                if did:
                    encoded_did = urllib.parse.quote(str(did), safe="")
                    new_row[datalink_idx] = f"{base_api_url}/api/datalink?ID={encoded_did}"
                new_rows.append(new_row)

            data_with_datalink = new_rows

        search_result_obj = SearchResult(columns=columns_with_datalink, data=data_with_datalink)

        # Redis SET (instrumented)
        if redis_client:
            t0 = time.perf_counter()
            ok = False
            try:
                await redis_client.set(cache_key, search_result_obj.model_dump_json(), ex=CACHE_TTL)
                ok = True
            except Exception:
                logger.warning("Redis set failed for key=%s", cache_key, exc_info=True)
            finally:
                observe_redis("set", time.perf_counter() - t0, ok)

        # Save history (optional)
        if user_session_data:
            app_user_id = user_session_data["app_user_id"]
            try:
                params_to_save: dict[str, Any] = {
                    "tap_url": tap_url,
                    "obscore_table": obscore_table,
                    "search_radius": search_radius,
                    "coordinate_system": coordinate_system,
                }

                # coords
                if coordinate_system in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
                    if ra is not None:
                        params_to_save["ra"] = ra
                    if dec is not None:
                        params_to_save["dec"] = dec
                elif coordinate_system == COORD_SYS_GAL:
                    if l_deg is not None:
                        params_to_save["l"] = l_deg
                    if b_deg is not None:
                        params_to_save["b"] = b_deg

                # time
                if obs_start:
                    params_to_save["obs_start_input"] = obs_start
                if obs_end:
                    params_to_save["obs_end_input"] = obs_end
                if mjd_start is not None:
                    params_to_save["mjd_start"] = mjd_start
                if mjd_end is not None:
                    params_to_save["mjd_end"] = mjd_end
                if time_scale:
                    params_to_save["time_scale"] = time_scale

                # energy
                if energy_min is not None:
                    params_to_save["energy_min"] = energy_min
                if energy_max is not None:
                    params_to_save["energy_max"] = energy_max

                # other filters
                if tracking_mode:
                    params_to_save["tracking_mode"] = tracking_mode
                if pointing_mode:
                    params_to_save["pointing_mode"] = pointing_mode
                if obs_mode:
                    params_to_save["obs_mode"] = obs_mode

                if proposal_id:
                    params_to_save["proposal_id"] = proposal_id
                if proposal_title:
                    params_to_save["proposal_title"] = proposal_title
                if proposal_contact:
                    params_to_save["proposal_contact"] = proposal_contact
                if proposal_type:
                    params_to_save["proposal_type"] = proposal_type

                if moon_level:
                    params_to_save["moon_level"] = moon_level
                if sky_brightness:
                    params_to_save["sky_brightness"] = sky_brightness

                history_payload = QueryHistoryCreate(
                    query_params=params_to_save,
                    results=search_result_obj.model_dump(),
                )
                await _internal_create_query_history(
                    history=history_payload,
                    app_user_id=app_user_id,
                    session=db_session,
                )
            except Exception as history_error:
                logger.error(
                    "saving query history for user app_id=%s: %s", app_user_id, history_error
                )
                traceback.print_exc()

        return search_result_obj

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ERROR search_coords: Exception during results processing: %s", e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Internal error processing search results."
        ) from e


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
        results.extend(_resolve_via_simbad(object_name, settings.SIMBAD_TAP_BASE))

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
    url = settings.NED_TAP_SYNC_URL
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

# alias mounts
app.include_router(basket_router, prefix="/api", include_in_schema=False)
app.include_router(query_history_router, prefix="/api", include_in_schema=False)

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
