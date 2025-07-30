from fastapi import FastAPI, Query, HTTPException, Body, Response, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from .models import SearchResult
from .tap import (
    perform_coords_query,
    perform_time_query,
    perform_coords_time_query,
    astropy_table_to_list,
)
import pyvo as vo
import math
from astropy.io.votable import parse_single_table
from astropy.coordinates import SkyCoord
from .auth import get_optional_session_user
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from .basket import basket_router
import urllib.parse
from astropy.time import Time
from datetime import datetime
from .query_history import query_history_router, QueryHistoryCreate, _internal_create_query_history
import fastapi_users
from .db import AsyncSessionLocal
import traceback
from .coords import coord_router
from typing import Dict, Any, List
import asyncio, re, json
from io import BytesIO
import requests
from astropy.io.votable import parse_single_table
from .db import get_redis_pool
from .auth import router as auth_api_router, SESSION_DURATION_SECONDS
from .oidc import oidc_router
from starlette.config import Config as StarletteConfig
from contextlib import asynccontextmanager
import itertools
import hashlib
from pydantic import BaseModel
from typing import Literal, Optional
from astropy.time import Time
import astropy.units as u


SIMBAD_TAP_SYNC = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
OBJECT_LOOKUP_URL = "https://ned.ipac.caltech.edu/srs/ObjectLookup"

config_env = StarletteConfig('.env')

BASE_URL = config_env("BASE_URL", default=None)
COOKIE_SAMESITE = config_env("COOKIE_SAMESITE", default="Lax")
COOKIE_SECURE = config_env("COOKIE_SECURE",  cast=bool, default=False)
RAW_COOKIE_DOMAIN = config_env("COOKIE_DOMAIN", default=None)
COOKIE_DOMAIN = RAW_COOKIE_DOMAIN or None
PRODUCTION = bool(BASE_URL)

if COOKIE_SAMESITE.lower() == "none" and not COOKIE_SECURE:
    COOKIE_SAMESITE = "Lax"
else:
    COOKIE_SAMESITE = COOKIE_SAMESITE.capitalize()

cookie_params = {
    "secure": COOKIE_SECURE,
    "httponly": True,
    "samesite": COOKIE_SAMESITE,
    "path": "/",
}
if COOKIE_DOMAIN:
  cookie_params["domain"] = COOKIE_DOMAIN

# coordinate cystem constants
COORD_SYS_EQ_DEG = 'equatorial_deg'
COORD_SYS_EQ_HMS = 'equatorial_hms'
COORD_SYS_GAL = 'galactic'

# App Event Handlers for Redis Pool
@asynccontextmanager
async def lifespan(app: FastAPI):
    import redis.asyncio as redis
    pool = await get_redis_pool()
    app.state.redis = redis.Redis(connection_pool=pool)
    print("Redis pool initialised.")
    try:
        yield
    finally:
        await app.state.redis.close()
        await pool.disconnect()
        print("Redis pool closed.")

app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access and analyse high-energy astrophysics data from CTAO",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
# SessionMiddleware for OIDC state/nonce (temporary cookie)
app.add_middleware(
    SessionMiddleware,
    secret_key=config_env("SESSION_SECRET_KEY_OIDC", default="a_different_strong_secret_for_oidc_state"),
    session_cookie="ctao_oidc_state_session",
    https_only=False,
    # same_site="lax",
    max_age=600
)

# Add session middleware
# app.add_middleware(
#    SessionMiddleware,
#    secret_key="SECRET_KEY",
#    session_cookie="ctao_session",
#    same_site="lax",  # 'lax'/'strict','none'
#    https_only=False,
#)

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
async def rolling_session_cookie(request: Request, call_next):
    response = await call_next(request)

    existing = response.headers.getlist("set-cookie")
    if any("ctao_session_main=" in hdr for hdr in existing):
        return response

    session_id = request.cookies.get("ctao_session_main")
    if session_id:
        response.set_cookie(
            "ctao_session_main",
            session_id,
            max_age=SESSION_DURATION_SECONDS,
            **cookie_params,
        )
    return response


class ConvertReq(BaseModel):
    value: str
    input_format: Literal["isot", "mjd", "met"] = "isot"
    input_scale:  Literal["utc", "tt", "tai"] = "utc"
    # MET only:
    met_epoch_isot: Optional[str] = None
    met_epoch_scale: Optional[Literal["utc","tt","tai"]] = "utc"

class ConvertResp(BaseModel):
    utc_isot: str
    utc_mjd: float
    tt_isot: str
    tt_mjd: float

@app.post("/api/convert_time", response_model=ConvertResp, tags=["time"])
def convert_time(req: ConvertReq):
    # Build Time object from the request
    if req.input_format == "met":
        if not req.met_epoch_isot:
            raise HTTPException(status_code=400, detail="met_epoch_isot required for MET.")
        epoch = Time(req.met_epoch_isot, format="isot", scale=req.met_epoch_scale or "utc")
        try:
            seconds = float(str(req.value).replace(",", "."))
        except Exception:
            raise HTTPException(status_code=400, detail="MET value must be numeric (seconds).")
        t = epoch + seconds * u.s
    elif req.input_format == "mjd":
        try:
            mjd = float(str(req.value).replace(",", "."))
        except Exception:
            raise HTTPException(status_code=400, detail="MJD value must be numeric.")
        t = Time(mjd, format="mjd", scale=req.input_scale)
    else:  # "isot"
        t = Time(req.value, format="isot", scale=req.input_scale)

    return ConvertResp(
        utc_isot=t.utc.isot,
        utc_mjd=float(t.utc.mjd),
        tt_isot=t.tt.isot,
        tt_mjd=float(t.tt.mjd),
    )


async def _ned_resolve_via_objectlookup(name: str) -> Optional[Dict[str, Any]]:
    """
    Returns {'service','name','ra','dec'} or None if not found/error.
    """
    form = {"json": json.dumps({"name": {"v": name}})}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = await asyncio.to_thread(
            requests.post,
            OBJECT_LOOKUP_URL,
            data=form,
            headers=headers,
            timeout=5
        )
        resp.raise_for_status()
    except Exception as e:
        print("NED ObjectLookup failed:", e)
        return None

    obj = resp.json()
    if obj.get("ResultCode") == 3:
        interp = obj["Interpreted"]
        pos    = obj["Preferred"]["Position"]
        return {
            "service": "NED",
            "name":    interp["Name"],
            "ra":      float(pos["RA"]),
            "dec":     float(pos["Dec"])
        }
    return None


def _catalog_variants(name: str):
    """
    Yield 'M  42', 'M   42', … or 'NGC  3242', etc., matching SIMBAD's
    fixed-width alias layout.  If `name` is not a Messier/NGC/IC code,
    yields nothing.
    """
    m = re.fullmatch(r"\s*(M|NGC|IC)\s*0*(\d+)\s*", name, re.I)
    if not m:
        return
    cat, num = m.group(1).upper(), m.group(2)
    width = 3 if cat == "M" else 4
    spaces_needed = max(1, width - len(num))
    for s in range(spaces_needed, spaces_needed + 3):
        yield f"{cat}{' ' * s}{num}"


CATALOG_RE = re.compile(r"^(M\d{1,3}|NGC\d{1,4}|IC\d{1,4})$", re.I)
def _is_short_catalog(q: str) -> bool:
    return bool(CATALOG_RE.match(q.strip()))


def _adql_escape(s: str) -> str:
    return s.replace("'", "''")

def _run_tap_sync(url: str, adql: str, maxrec: int = 50):
    r = requests.get(
        url,
        params=dict(QUERY=adql, LANG="ADQL", REQUEST="doQuery",
                    FORMAT="votable", MAXREC=maxrec),
        timeout=20,
    )
    r.raise_for_status()
    return parse_single_table(BytesIO(r.content)).to_table()

async def _simbad_suggest(prefix: str, limit: int) -> list[dict]:
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
        rows.extend(str(r['main_id']).strip() for r in tab)
    except Exception as exc:
        print("SIMBAD exact failed:", exc)

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
        rows.extend(str(r['main_id']).strip() for r in tab)
    except Exception as exc:
        print("SIMBAD alias LIKE failed:", exc)

    q_cmp = q_uc.replace(" ", "")
    scored = []
    for n in rows:
        n_cmp = n.upper().replace(" ", "")
        score = 0 if n_cmp == q_cmp else 1 if n_cmp.startswith(q_cmp) else 2
        scored.append((score, len(n_cmp), n))

    seen, ordered = set(), []
    for _, _, n in sorted(scored):
        if n not in seen:
            ordered.append(n); seen.add(n)
            if len(ordered) == limit:
                break

    return [{"service": "SIMBAD", "name": n} for n in ordered]


async def _ned_suggest(prefix: str, limit: int) -> List[Dict[str, str]]:
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
            requests.post,
            OBJECT_LOOKUP_URL,
            data=form,
            headers=headers,
            timeout=5
        )
        resp.raise_for_status()
        doc = resp.json()
    except Exception as e:
        print("NED ObjectLookup failed:", e)
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


@app.get("/api/object_suggest", tags=["object_resolve"])
async def object_suggest(
    q: str = Query(..., min_length=2, max_length=50),
    use_simbad: bool = True,
    use_ned: bool = False,
    limit: int = 15,
)-> Dict[str, List[Dict[str, Any]]]:
    q = q.strip()
    if len(q) < 4 and not _is_short_catalog(q):
        return {"results": []}
    if not (use_simbad or use_ned):
        return {"results": []}

    cache_key = f"suggest:{q.lower()}:{use_simbad}:{use_ned}:{limit}"
    if hasattr(app.state, "redis"):
        cached = await app.state.redis.get(cache_key)
        if cached:
            return json.loads(cached.decode() if isinstance(cached, bytes) else cached)

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

    results = merged[:limit]

    # store in redis for 24 h
    if hasattr(app.state, "redis"):
        await app.state.redis.set(cache_key, json.dumps({"results": results}), ex=86400)

    return {"results": results}


@app.get("/api/search_coords", response_model=SearchResult, tags=["search"])
async def search_coords(
    request: Request,
    # Coordinate Params
    coordinate_system: Optional[str] = None,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    l: Optional[float] = None,
    b: Optional[float] = None,
    search_radius: float = 5.0,
    # Time Params
    obs_start: Optional[str] = None,
    obs_end: Optional[str] = None,
    mjd_start: Optional[float] = Query(None),
    mjd_end: Optional[float] = Query(None),
    mjd_scale: Optional[str] = Query("tt", description="Scale of provided MJD: 'utc' or 'tt' (default tt)"),
    obs_scale: Optional[str] = Query("utc", description="Scale of provided obs_* strings if used (default utc)"),
    # TAP Params
    tap_url: str = 'http://voparis-tap-he.obspm.fr/tap',
    obscore_table: str = 'hess_dr.obscore_sdc',
    # Auth
    user_session_data: Optional[Dict[str, Any]] = Depends(get_optional_session_user),
):
    redis = getattr(app.state, "redis", None)
    CACHE_TTL = 3600

    base_api_url = f"{request.url.scheme}://{request.headers['host']}"
    # print(f"DEBUG search_coords: START. Params received: {request.query_params}")

    fields = {
        'tap_url': {'value': tap_url},
        'obscore_table': {'value': obscore_table},
        'search_radius': {'value': search_radius}
    }
    coords_present = False
    time_filter_present = False

    # Process Time - prioritize MJD
    if mjd_start is not None and mjd_end is not None:
        MIN_VALID_MJD = 0  # roughly Nov 17, 1858
        MAX_VALID_MJD = 100000  # roughly Nov 22, 2132
        if not (MIN_VALID_MJD <= mjd_start <= MAX_VALID_MJD and MIN_VALID_MJD <= mjd_end <= MAX_VALID_MJD):
            raise HTTPException(status_code=400,
                                detail=f"MJD values out of expected range ({MIN_VALID_MJD}-{MAX_VALID_MJD}).")
        if mjd_end <= mjd_start:
            raise HTTPException(status_code=400, detail="mjd_end must be greater than mjd_start.")
        # Normalize to TT because table t_min/t_max are in TT
        if mjd_scale and mjd_scale.lower() != "tt":
            try:
                t_start_tt = Time(mjd_start, format="mjd", scale=mjd_scale).tt
                t_end_tt = Time(mjd_end, format="mjd", scale=mjd_scale).tt
                mjd_start_tt = float(t_start_tt.mjd)
                mjd_end_tt = float(t_end_tt.mjd)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid mjd_scale '{mjd_scale}': {e}")
        else:
            mjd_start_tt = mjd_start
            mjd_end_tt = mjd_end
        fields['search_mjd_start'] = {'value': mjd_start_tt}
        fields['search_mjd_end'] = {'value': mjd_end_tt}
        time_filter_present = True
        print(f"DEBUG search_coords: Using MJD filter: {mjd_start} - {mjd_end}")
    elif obs_start and obs_end:  # Fallback to date/time strings
        try:
            dt_start = datetime.strptime(obs_start, "%d/%m/%Y %H:%M:%S")
            dt_end = datetime.strptime(obs_end, "%d/%m/%Y %H:%M:%S")
            if dt_end <= dt_start:
                raise HTTPException(status_code=400, detail="obs_end must be after obs_start.")

            if not (datetime.MINYEAR <= dt_start.year <= datetime.MAXYEAR and
                    datetime.MINYEAR <= dt_end.year <= datetime.MAXYEAR):
                raise ValueError("Date year is out of representable range.")
            scale = (obs_scale or "utc").lower()
            if scale not in ("utc", "tt", "tai"):
                raise HTTPException(status_code=400, detail=f"Unsupported obs_scale '{obs_scale}'")
            t_start_tt = Time(dt_start, scale=scale).tt
            t_end_tt = Time(dt_end, scale=scale).tt
            fields['search_mjd_start'] = {'value': float(t_start_tt.mjd)}
            fields['search_mjd_end'] = {'value': float(t_end_tt.mjd)}
            time_filter_present = True
            print(f"DEBUG search_coords: Date/Time -> TT MJD: {fields['search_mjd_start']['value']} - {fields['search_mjd_end']['value']} (obs_scale={obs_scale})")
        except ValueError as ve:  # Catch strptime errors or our custom ValueError
            raise HTTPException(status_code=400, detail=f"Invalid date/time format or value: {ve}")
        except Exception as e:
            print(f"ERROR: Unexpected error during time processing: {e}")
            raise HTTPException(status_code=500, detail="Error processing time parameters.")

    # Process coordinates
    if coordinate_system == COORD_SYS_EQ_DEG or coordinate_system == COORD_SYS_EQ_HMS:
        if ra is not None and dec is not None:
            fields['target_raj2000'] = {'value': ra}
            fields['target_dej2000'] = {'value': dec}
            coords_present = True
            print(f"DEBUG search_coords: Galactic coords processed and converted. L={l}, B={b}")
    elif coordinate_system == COORD_SYS_GAL:
        if l is not None and b is not None:
            try:
                c_gal = SkyCoord(l * u.deg, b * u.deg, frame='galactic')
                c_icrs = c_gal.icrs
                fields['target_raj2000'] = {'value': c_icrs.ra.deg}
                fields['target_dej2000'] = {'value': c_icrs.dec.deg}
                coords_present = True
            except Exception as coord_exc:
                 print(f"ERROR: Galactic conversion failed: {coord_exc}")
                 raise HTTPException(status_code=400, detail="Invalid galactic coordinates provided.")

    print(f"DEBUG search_coords: Fields prepared: {fields}")
    print(f"DEBUG search_coords: Coords present: {coords_present}, Time present: {time_filter_present}")

    # adql_query_str = None
    res_table = None
    error = None

    if not coords_present and not time_filter_present:
        raise HTTPException(status_code=400, detail="Provide Coordinates or Time Interval.")

    if coords_present and time_filter_present:
        adql_query_str = (
            "SELECT TOP 100 * FROM {tbl} WHERE "
            "1=CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE('ICRS', {ra}, {dec}, {rad})) "
            "AND t_min < {tend} AND t_max > {tstart}"
        ).format(
            tbl = obscore_table,
            ra = fields['target_raj2000']['value'],
            dec = fields['target_dej2000']['value'],
            rad = fields['search_radius']['value'],
            tend = fields['search_mjd_end']['value'],
            tstart = fields['search_mjd_start']['value'],
        )
    elif coords_present:
        adql_query_str = (
            "SELECT TOP 100 * FROM {tbl} WHERE "
            "1=CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE('ICRS', {ra}, {dec}, {rad}))"
        ).format(
            tbl = obscore_table,
            ra = fields['target_raj2000']['value'],
            dec = fields['target_dej2000']['value'],
            rad = fields['search_radius']['value'],
        )
    else:
        adql_query_str = (
            "SELECT TOP 100 * FROM {tbl} WHERE t_min < {tend} AND t_max > {tstart}"
        ).format(
            tbl = obscore_table,
            tend = fields['search_mjd_end']['value'],
            tstart = fields['search_mjd_start']['value'],
        )

    cache_key = "search:" + hashlib.sha256(adql_query_str.encode()).hexdigest()

    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return SearchResult.model_validate_json(cached)

    try:
        if coords_present and time_filter_present:
            error, res_table, adql_query_str = perform_coords_time_query(fields)
        elif coords_present:
            error, res_table, adql_query_str = perform_coords_query(fields)
        elif time_filter_present:
            error, res_table, adql_query_str = perform_time_query(fields)

        print(f"DEBUG search_coords: After query call: error={error}, type(res_table)={type(res_table)}")

    except Exception as query_exc:
        print(f"ERROR search_coords: Exception during perform_query call: {query_exc}")
        raise HTTPException(status_code=500, detail="Failed during query execution.")

    if error is None:
        # print(f"DEBUG search_coords: No error from query function. Processing table.")
        try:
            columns, data = astropy_table_to_list(res_table)
            # print(f"DEBUG search_coords: astropy_table_to_list returned {len(columns)} cols, {len(data)} rows.")

            if not columns and not data and res_table is not None and len(res_table) > 0:
                 print("ERROR search_coords: astropy_table_to_list returned empty lists despite input.")
                 raise HTTPException(status_code=500, detail="Internal error processing results.")

            columns = list(columns) if columns else []
            data = [list(row) for row in data] if data else []
            # print(f"DEBUG search_coords: Constructing SearchResult object.")

            search_result_obj = SearchResult(columns=columns, data=data)
            print(f"DEBUG search_coords: SearchResult object created: {type(search_result_obj)}")

            data_with_datalink = data
            columns_with_datalink = columns[:]

            if "obs_publisher_did" in columns_with_datalink:
                datalink_col = "datalink_url"
                if datalink_col not in columns_with_datalink:
                    columns_with_datalink.append(datalink_col)
                idx = columns_with_datalink.index("obs_publisher_did")

                # Create new data rows with the link appended
                data_with_datalink = []
                for row_idx, original_row in enumerate(data):
                    new_row = original_row[:]
                    # Ensure row has enough elements
                    if idx < len(new_row):
                        did = new_row[idx]
                        if did: # Check if DID is not None or empty
                           encoded_did = urllib.parse.quote(str(did), safe='')
                           datalink_url = f"{base_api_url}/api/datalink?ID={encoded_did}"
                           if len(new_row) == len(columns_with_datalink) -1:
                               new_row.append(datalink_url)
                           elif len(new_row) == len(columns_with_datalink):
                               # If column existed, overwrite
                               new_row[columns_with_datalink.index(datalink_col)] = datalink_url
                           else:
                               print(f"WARN: Row {row_idx} length mismatch when adding datalink.")
                        else: # Handle empty DID
                             if len(new_row) == len(columns_with_datalink) -1: new_row.append(None)

                    else:
                         print(f"WARN: Row {row_idx} too short for DID index {idx}.")
                         if len(new_row) == len(columns_with_datalink) -1: new_row.append(None)

                    data_with_datalink.append(new_row)


            # recreate SearchResult with datalink info
            search_result_obj = SearchResult(columns=columns_with_datalink, data=data_with_datalink)
            # print(f"DEBUG search_coords: SearchResult RECREATED with datalink.")

            if redis:
                await redis.set(
                    cache_key,
                    search_result_obj.model_dump_json(),
                    ex=CACHE_TTL
                )
            else:
                print("Redis client was None; skipping cache")

            if user_session_data:
                app_user_id = user_session_data["app_user_id"]
                iam_sub = user_session_data.get("iam_subject_id")
                print(f"DEBUG: User app_id={app_user_id} (IAM sub={iam_sub}) logged in, "
                      f"attempting to save history. ADQL: {adql_query_str}")
                try:
                    params_to_save = {
                        "tap_url": tap_url,
                        "obscore_table": obscore_table,
                        "search_radius": search_radius,
                        "coordinate_system": coordinate_system
                    }
                    if coordinate_system == COORD_SYS_EQ_DEG or coordinate_system == COORD_SYS_EQ_HMS:
                        if ra is not None: params_to_save["ra"] = ra
                        if dec is not None: params_to_save["dec"] = dec
                    elif coordinate_system == COORD_SYS_GAL:
                        if l is not None: params_to_save["l"] = l
                        if b is not None: params_to_save["b"] = b
                    # Store time parameters
                    if obs_start: params_to_save["obs_start_input"] = obs_start
                    if obs_end: params_to_save["obs_end_input"] = obs_end
                    if mjd_start is not None: params_to_save["mjd_start"] = mjd_start
                    if mjd_end is not None: params_to_save["mjd_end"] = mjd_end

                    history_payload = QueryHistoryCreate(
                        query_params=params_to_save,
                        results=search_result_obj.model_dump()
                    )
                    async with AsyncSessionLocal() as history_session:
                        await _internal_create_query_history(
                            history=history_payload,
                            app_user_id=app_user_id,
                            session=history_session
                        )
                    print(f"DEBUG: Called create_query_history for user app_id={app_user_id}")
                except Exception as history_error:
                    print(f"ERROR saving query history for user app_id={app_user_id}: {history_error}")
                    traceback.print_exc()

            print(f"DEBUG search_coords: Returning SearchResult object.")
            return search_result_obj

        except Exception as processing_exc:
             print(f"ERROR search_coords: Exception during results processing: {processing_exc}")
             traceback.print_exc()
             raise HTTPException(status_code=500, detail="Internal error processing search results.")

    else:
        print(f"ERROR search_coords: Query function returned error: {error}")
        raise HTTPException(status_code=400, detail=error)


@app.post("/api/object_resolve", tags=["object_resolve"])
async def object_resolve(data: dict = Body(...)):
    """
    Unified endpoint to resolve an object name from either/both SIMBAD & NED,
    Example JSON:
    {
      "object_name": "M1",
      "use_simbad": true,
      "use_ned": false
    }
    """
    object_name = data.get("object_name", "").strip()
    use_simbad = data.get("use_simbad", False)
    use_ned = data.get("use_ned", False)

    if not object_name:
        raise HTTPException(status_code=400, detail="No object_name provided.")
    if not (use_simbad or use_ned):
        # Must pick at least one source
        return {"results": []}

    results = []
    simbad_list = []
    ned_list = []

    if use_simbad:
        SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap"
        simbad = vo.dal.TAPService(SIMBAD_TAP)

        def _try_alias(alias: str, top: int = 1):
            sql = (
                f"SELECT TOP {top} ra, dec, main_id "
                "FROM ident i JOIN basic b ON b.oid = i.oidref "
                f"WHERE i.id = '{_adql_escape(alias)}'"
            )
            try:
                return simbad.search(sql)
            except Exception:
                return []

        alias_raw = object_name.strip()
        tab = _try_alias(alias_raw)

        if len(tab) == 0:
            for alias in _catalog_variants(alias_raw):
                tab = _try_alias(alias)
                if len(tab):
                    break

        if len(tab) == 0:
            tab = _try_alias(alias_raw.title())

        if len(tab) == 0:
            tab = _try_alias(alias_raw.upper())

        if len(tab) == 0 and not alias_raw.upper().startswith("NAME "):
            tab = _try_alias("NAME " + alias_raw.title())

        # collect rows
        for row in tab:
            ra_val, dec_val = float(row["ra"]), float(row["dec"])
            if math.isnan(ra_val) or math.isnan(dec_val):
                continue
            simbad_list.append({
                "service": "SIMBAD",
                "name": str(row["main_id"]).strip(),
                "ra": ra_val,
                "dec": dec_val,
            })

        results.extend(simbad_list)

    if use_ned:
        resolved = await _ned_resolve_via_objectlookup(object_name)
        if resolved:
            results.append(resolved)

    return {"results": results}

def _run_ned_sync_query(adql_query):
    """
    Helper function to run a synchronous NED TAP query (returns a list of dict).
    By default, NED returns a VOTable. Parse it with astropy.io.votable.
    """
    url = "https://ned.ipac.caltech.edu/tap/sync"
    params = {
        "QUERY": adql_query,
        "LANG": "ADQL",
        "REQUEST": "doQuery",
        "FORMAT": "votable",
        "MAXREC": 5000
    }

    out = []
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()

        votable_buf = BytesIO(r.content)
        table = parse_single_table(votable_buf).to_table()

        # columns: ra, dec, prefname
        for row in table:
            ra_val  = float(row["ra"])
            dec_val = float(row["dec"])
            pref_val= str(row["prefname"])
            if math.isnan(ra_val) or math.isnan(dec_val):
                continue
            out.append({
                "ra": ra_val,
                "dec": dec_val,
                "prefname": pref_val
            })
    except Exception as e:
        print(f"NED query error: {e}")

    return out

@app.get("/api/datalink", tags=["datalink"])
async def datalink_endpoint(
    ID: list[str] = Query(..., description="One or more dataset identifiers (e.g., ivo://padc.obspm/hess#23523)")
):
    """
    DataLink endpoint that returns a VOTable containing links for each dataset ID.
    """
    rows = ""
    for id_val in ID:
        if id_val.lower().startswith("ivo://"):
            if '#' in id_val:
                # Extract the portion after '#' (e.g. "23523")
                obs_id_str = id_val.split('#', 1)[1]
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
            error_message = f"NotFoundFault: {id_val} is not recognized as a valid ivo:// identifier"
            service_def = ""
        rows += (
            "                <TR>\n"
            f"                  <TD>{id_val}</TD>\n"
            f"                  <TD>{access_url}</TD>\n"
            f"                  <TD>{service_def}</TD>\n"
            f"                  <TD>{error_message}</TD>\n"
            "                </TR>\n"
        )

    votable_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
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
'''
    return Response(content=votable_xml, media_type="application/x-votable+xml")


# app.include_router(auth_router)
app.include_router(auth_api_router, prefix="/api") # For /users/me_from_session, /auth/logout_session
# app.include_router(oidc_router)
app.include_router(oidc_router, prefix="/api")
app.include_router(basket_router)
app.include_router(query_history_router)
app.include_router(coord_router)

# alias mounts
app.include_router(basket_router, prefix="/api", include_in_schema=False)
app.include_router(query_history_router, prefix="/api", include_in_schema=False)

# Mount the React build folder
app.mount("/", StaticFiles(directory="./js/build", html=True), name="js")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
