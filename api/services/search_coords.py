from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from ctao_shared.constants import (
    COORD_SYS_EQ_DEG,
    COORD_SYS_EQ_HMS,
    COORD_SYS_GAL,
)
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt_verifier import VerifiedIdentity
from api.models import SearchResult
from api.query_history import QueryHistoryCreate, _internal_create_query_history
from api.services.cache import (
    build_cache_key_from_adql,
    redis_get_json_model,
    redis_set_json_model,
)
from api.services.result_formatting import augment_with_datalink
from api.tap import (
    astropy_table_to_list,
    build_select_query,
    build_spatial_icrs_condition,
    build_time_overlap_condition,
    build_where_clause,
    perform_query_with_conditions,
)
from api.tap_schema import get_tap_table_columns, tap_supports_columns

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600
TEV_TO_EV = 1e12

COORD_SYS_ALIASES: dict[str, str] = {
    "eq_deg": COORD_SYS_EQ_DEG,
    "eq_hms": COORD_SYS_EQ_HMS,
    "hmsdms": COORD_SYS_EQ_HMS,
    "gal": COORD_SYS_GAL,
}


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


@dataclass
class TimeInfo:
    present: bool
    mjd_start_tt: float | None = None
    mjd_end_tt: float | None = None


@dataclass
class CoordInfo:
    present: bool
    ra_deg: float | None = None
    dec_deg: float | None = None
    coordinate_system: str | None = None


@dataclass
class TapColumnContext:
    tap_schema_available: bool
    tap_cols: set[str]
    ignored_optional_filters: list[str]
    requested_optional_filters: list[str]
    applied_optional_filters: list[str]
    optional_filter_probe_failed: bool
    probe_cache: dict[str, bool]


def _esc_adql_str(s: str) -> str:
    return (s or "").replace("'", "''")


def _norm_opt(s: str | None) -> str | None:
    v = (s or "").strip()
    return v or None


def _process_mjd_range(params: SearchCoordsParams) -> TimeInfo | None:
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
        start_tt = params.mjd_start
        end_tt = params.mjd_end

    return TimeInfo(True, float(start_tt), float(end_tt))


def _process_obs_range(params: SearchCoordsParams) -> TimeInfo | None:
    if not params.obs_start and not params.obs_end:
        return None

    if not (params.obs_start and params.obs_end):
        raise HTTPException(status_code=400, detail="Both obs_start and obs_end are required.")

    try:
        dt_start = datetime.strptime(params.obs_start, "%d/%m/%Y %H:%M:%S")
        dt_end = datetime.strptime(params.obs_end, "%d/%m/%Y %H:%M:%S")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date/time format or value: {exc}",
        ) from exc

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
    except (ValueError, TypeError) as exc:
        logger.error("Unexpected error during time processing.", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing time parameters.") from exc

    return TimeInfo(True, float(t_start_tt.mjd), float(t_end_tt.mjd))


def _process_time(params: SearchCoordsParams) -> TimeInfo:
    out = _process_mjd_range(params)

    if out is not None:
        return out

    out = _process_obs_range(params)

    if out is not None:
        return out

    return TimeInfo(False)


def _process_coords(params: SearchCoordsParams) -> CoordInfo:
    cs = params.coordinate_system

    if cs is not None:
        cs = COORD_SYS_ALIASES.get(cs, cs)

    if cs in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
        if params.ra is not None and params.dec is not None:
            return CoordInfo(True, float(params.ra), float(params.dec), cs)

        return CoordInfo(False, None, None, cs)

    if cs == COORD_SYS_GAL:
        if params.l_deg is not None and params.b_deg is not None:
            try:
                c_gal = SkyCoord(params.l_deg * u.deg, params.b_deg * u.deg, frame="galactic")
                c_icrs = c_gal.icrs
                return CoordInfo(True, float(c_icrs.ra.deg), float(c_icrs.dec.deg), cs)
            except Exception as exc:
                logger.error("Galactic conversion failed: %s", exc)
                raise HTTPException(
                    status_code=400,
                    detail="Invalid galactic coordinates provided.",
                ) from exc

        return CoordInfo(False, None, None, cs)

    return CoordInfo(False, None, None, cs)


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


def _add_if(dst: dict[str, Any], key: str, val: Any) -> None:
    if val is not None and val != "":
        dst[key] = val


def _build_history_params(params: SearchCoordsParams, coord: CoordInfo) -> dict[str, Any]:
    out: dict[str, Any] = {
        "tap_url": params.tap_url,
        "obscore_table": params.obscore_table,
        "search_radius": params.search_radius,
        "coordinate_system": coord.coordinate_system,
    }

    if coord.coordinate_system in (COORD_SYS_EQ_DEG, COORD_SYS_EQ_HMS):
        _add_if(out, "ra", params.ra)
        _add_if(out, "dec", params.dec)
    elif coord.coordinate_system == COORD_SYS_GAL:
        _add_if(out, "l", params.l_deg)
        _add_if(out, "b", params.b_deg)

    _add_if(out, "obs_start_input", params.obs_start)
    _add_if(out, "obs_end_input", params.obs_end)
    _add_if(out, "mjd_start", params.mjd_start)
    _add_if(out, "mjd_end", params.mjd_end)
    _add_if(out, "time_scale", params.time_scale)

    _add_if(out, "energy_min", params.energy_min)
    _add_if(out, "energy_max", params.energy_max)

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
    coord: CoordInfo,
    db_session: AsyncSession,
    search_result_obj: SearchResult,
) -> None:
    if not identity:
        return

    try:
        history_payload = QueryHistoryCreate(
            query_params=_build_history_params(params, coord),
            results=search_result_obj.model_dump(),
        )
        await _internal_create_query_history(
            history=history_payload,
            user_sub=identity.sub,
            session=db_session,
        )
    except Exception:
        logger.exception("Saving query history failed")


async def _discover_tap_columns(tap_url: str, obscore_table: str) -> tuple[bool, set[str]]:
    try:
        cols = await get_tap_table_columns(tap_url, obscore_table)
        cols_norm = {c.lower() for c in cols} if cols else set()
        return bool(cols_norm), cols_norm
    except Exception as exc:
        logger.warning(
            "search_coords: TAP_SCHEMA lookup failed (%s). Optional filters may require fallback probing.",
            exc,
            exc_info=True,
        )
        return False, set()


async def _optional_col_exists(
    *,
    ctx: TapColumnContext,
    tap_url: str,
    obscore_table: str,
    col: str,
) -> bool:
    if ctx.tap_schema_available:
        return col.lower() in ctx.tap_cols

    if col in ctx.probe_cache:
        return ctx.probe_cache[col]

    exists = await tap_supports_columns(tap_url, obscore_table, [col])
    ctx.probe_cache[col] = bool(exists)
    return bool(exists)


async def _add_optional_enum_eq(
    *,
    ctx: TapColumnContext,
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
            ctx=ctx,
            tap_url=tap_url,
            obscore_table=obscore_table,
            col=col,
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
    ctx: TapColumnContext,
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
            ctx=ctx,
            tap_url=tap_url,
            obscore_table=obscore_table,
            col=col,
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
    ctx: TapColumnContext,
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
            ctx=ctx,
            tap_url=tap_url,
            obscore_table=obscore_table,
            col=col,
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
    energy_filter_requested = params.energy_min is not None or params.energy_max is not None

    if not energy_filter_requested:
        return

    if tap_schema_available:
        have_energy_cols = "energy_min" in tap_cols and "energy_max" in tap_cols
    else:
        try:
            have_energy_cols = await tap_supports_columns(
                params.tap_url,
                params.obscore_table,
                ["energy_min", "energy_max"],
            )
        except Exception as exc:
            logger.warning("Energy column probe failed.", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Energy filtering could not be validated because the TAP service returned an error while "
                    "checking column availability. Please try again later or choose another TAP table."
                ),
            ) from exc

    if not have_energy_cols:
        raise HTTPException(
            status_code=400,
            detail=(
                "Energy filtering requires columns 'energy_min' and 'energy_max' "
                f"to be present in '{params.obscore_table}', but they were not found. "
                "Please choose a table that provides energy columns, or disable Energy Search."
            ),
        )

    if params.energy_min is not None:
        where_conditions.append(f"energy_max >= {float(params.energy_min) * TEV_TO_EV:g}")

    if params.energy_max is not None:
        where_conditions.append(f"energy_min <= {float(params.energy_max) * TEV_TO_EV:g}")


def _validate_optional_filters_outcome(
    *,
    coords_present: bool,
    time_present: bool,
    energy_filter_requested: bool,
    ctx: TapColumnContext,
) -> None:
    if ctx.ignored_optional_filters:
        logger.info(
            "search_coords: Ignored optional filters: %s",
            sorted(set(ctx.ignored_optional_filters)),
        )

    if (
        ctx.requested_optional_filters
        and ctx.applied_optional_filters
        and not ctx.tap_schema_available
    ):
        logger.info(
            "search_coords: Applied optional filters via fallback column probe: %s",
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
    time_info: TimeInfo,
    coord: CoordInfo,
) -> tuple[bool, bool]:
    if time_info.present:
        if time_info.mjd_start_tt is None or time_info.mjd_end_tt is None:
            raise HTTPException(status_code=500, detail="Internal error: time range is incomplete.")

        fields["search_mjd_start"] = {"value": float(time_info.mjd_start_tt)}
        fields["search_mjd_end"] = {"value": float(time_info.mjd_end_tt)}

    if coord.present:
        if coord.ra_deg is None or coord.dec_deg is None:
            raise HTTPException(
                status_code=500,
                detail="Internal error: coordinates are incomplete.",
            )

        fields["target_raj2000"] = {"value": float(coord.ra_deg)}
        fields["target_dej2000"] = {"value": float(coord.dec_deg)}

    return coord.present, time_info.present


async def search_coords_impl(
    *,
    params: SearchCoordsParams,
    identity: VerifiedIdentity | None,
    db_session: AsyncSession,
    redis_client: Any,
) -> SearchResult:
    fields: dict[str, Any] = _build_fields_base(params)

    tap_schema_available, tap_cols = await _discover_tap_columns(
        params.tap_url,
        params.obscore_table,
    )

    time_info = _process_time(params)
    coord = _process_coords(params)
    coords_present, time_present = _apply_time_coord_fields(fields, time_info, coord)

    energy_filter_requested = params.energy_min is not None or params.energy_max is not None

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
        coords_present,
        time_present,
        energy_filter_requested,
        other_filter_requested,
    )

    where_conditions: list[str] = []

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

    await _apply_energy_filter(
        params=params,
        tap_schema_available=tap_schema_available,
        tap_cols=tap_cols,
        where_conditions=where_conditions,
    )

    ctx = TapColumnContext(
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

    where_sql = build_where_clause(where_conditions)
    adql_query_str = build_select_query(
        str(fields["obscore_table"]["value"]),
        where_sql,
        limit=100,
    )
    cache_key = build_cache_key_from_adql(adql_query_str)

    if redis_client:
        cached_obj = await redis_get_json_model(
            redis_client,
            cache_key,
            SearchResult,
            metric_name="search",
        )
        if cached_obj is not None:
            return cached_obj

    try:
        error, res_table, _ = perform_query_with_conditions(fields, where_conditions, limit=100)
    except Exception as exc:
        logger.error(
            "search_coords: Exception during perform_query call: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed during query execution.") from exc

    if error is not None:
        logger.error("search_coords: Query function returned error: %s", error)
        raise HTTPException(status_code=400, detail=error)

    try:
        columns, data = astropy_table_to_list(res_table)
        columns_list = list(columns) if columns else []
        data_list = [list(row) for row in data] if data else []

        columns_with, data_with = augment_with_datalink(columns_list, data_list)
        search_result_obj = SearchResult(columns=columns_with, data=data_with)

        if redis_client:
            await redis_set_json_model(
                redis_client,
                cache_key,
                search_result_obj,
                CACHE_TTL_SECONDS,
            )

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
    except Exception as exc:
        logger.error(
            "ERROR search_coords: Exception during results processing: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal error processing search results.",
        ) from exc
