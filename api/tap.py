from __future__ import annotations

import logging
import math
import time
import traceback
from typing import Any

import numpy as np
import pyvo as vo
import requests
from astropy.table import Table
from requests import Response, Session

from .metrics import vo_observe_call

logger = logging.getLogger(__name__)


def build_spatial_icrs_condition(ra: float, dec: float, radius_deg: float) -> str:
    """
    CONTAINS(CIRCLE) spatial filter in ICRS using s_ra/s_dec from ObsCore.
    """
    return (
        "1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
        f"CIRCLE('ICRS', {float(ra)}, {float(dec)}, {float(radius_deg)}))"
    )


def build_time_overlap_condition(tstart_mjd_tt: float, tend_mjd_tt: float) -> str:
    """
    Half-open/overlap style constraint: any record overlapping [tstart, tend]
    """
    return f"t_min < {float(tend_mjd_tt)} AND t_max > {float(tstart_mjd_tt)}"


def build_where_clause(conditions: list[str]) -> str:
    """
    Join a list of WHERE snippets with AND, falling back to TRUE (1=1).
    """
    parts = [c.strip() for c in conditions if c and c.strip()]
    return " AND ".join(parts) if parts else "1=1"


def build_select_query(table: str, where: str, limit: int = 100, columns: str = "*") -> str:
    """
    Compose the final SELECT with WHERE.
    """
    return f"SELECT TOP {int(limit)} {columns} FROM {table} WHERE {where}"


def perform_query_with_conditions(
    fields: dict[str, Any], conditions: list[str], limit: int = 100
) -> tuple[str | None, Table | None, str]:
    url = fields["tap_url"]["value"]
    obscore_table = fields["obscore_table"]["value"]
    timeout = 5

    error: str | None = None
    astro_table: Table | None = None
    query = ""

    try:
        t = Tap(url)
        t.connect(timeout)

        # if caller already computed ADQL reuse it
        prebuilt = fields.get("adql_query_str", {}).get("value")
        if isinstance(prebuilt, str) and prebuilt.strip():
            query = prebuilt
        else:
            where = build_where_clause(conditions)
            query = build_select_query(obscore_table, where, limit=limit)

        logger.debug("Running ADQL Query: %s", query)
        exception, tap_results = t.query(query)

        if exception:
            error = f"Got exception with TAP query: {exception}"
        elif tap_results is None:
            error = "TAP query succeeded but returned no results object."
        else:
            astro_table = _process_tap_results(tap_results)
            if astro_table is None and error is None:
                error = "Failed processing TAP results after query."
    except Exception as outer_exception:
        error = f"Failed TAP operation: {outer_exception}"
        logger.exception("Error during TAP operation: %s", outer_exception)
        traceback.print_exc()
        astro_table = None

    logger.debug(
        "Returning from perform_query_with_conditions: error=%s, table type=%s",
        error,
        type(astro_table),
    )
    return error, astro_table, query


def _process_tap_results(tap_results: vo.dal.TAPResults) -> Table | None:
    """Converts TAPResults to Astropy Table."""
    if tap_results is None:
        return None
    try:
        astro_table = tap_results.to_table()
        logger.debug("Converted TAPResults to Astropy Table with %s rows.", len(astro_table))
        return astro_table
    except Exception as convert_error:
        logger.exception("Error: Failed converting TAPResults: %s", convert_error)
        traceback.print_exc()
        return None


class CTAOHTTPAdapter(requests.adapters.HTTPAdapter):
    """
    A subclass of HTTPAdapter to handle timeouts
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self.timeout = kwargs.pop("timeout", None)
        super().__init__(*args, **kwargs)

    def send(self, *args: Any, **kwargs: Any) -> Response:
        kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)


class Tap:
    """
    Class to handle TAP/ADQL queries
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.conn: vo.dal.TAPService | None = None

    def connect(self, timeout: int = 5) -> None:
        """
        Retrieve a connection to the TAP server, setting a timeout for the connection
        """
        session: Session = requests.Session()
        adapter = CTAOHTTPAdapter(timeout=timeout)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        self.conn = vo.dal.TAPService(self.url, session=session)

    # def query(self, query):
    def query(self, query: str) -> tuple[Exception | None, vo.dal.TAPResults | None]:
        """
        Launch a TAP query
        """
        table = None
        exception = None
        t0 = time.perf_counter()
        ok = False
        try:
            if self.conn is None:
                raise RuntimeError("TAPService connection not initialized")
            table = self.conn.search(query)
            ok = True
        except Exception as e:
            exception = e
        finally:
            vo_observe_call("tap", self.url, time.perf_counter() - t0, ok)
        return exception, table


def _bytes_to_text(b: bytes | np.bytes_) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return repr(b)


def _float_from(val: Any) -> float | None:
    """Return a finite float or None (handles NaN/Inf and odd types)."""
    try:
        f = float(str(val))
    except Exception:
        try:
            f = float(val)
        except Exception:
            return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _normalize_cell(cell: Any) -> Any:
    """Normalize an Astropy cell to JSON-safe value."""
    # Masked or void → None
    if cell is None or isinstance(cell, np.void) or isinstance(cell, np.ma.core.MaskedConstant):
        return None
    # Bytes → text (with safe fallback)
    if isinstance(cell, (bytes, np.bytes_)):
        return _bytes_to_text(cell)
    # Int-like
    if isinstance(cell, (int, np.integer)):
        return int(cell)
    # Float-like
    if isinstance(cell, (float, np.floating)):
        return _float_from(cell)
    # Everything else → string
    return str(cell)


def astropy_table_to_list(table: Table | None) -> tuple[list[str], list[list[Any]]]:
    """
    Convert an Astropy Table object to a list of lists suitable for JSON conversion,
    along with the list of column names.
    """
    if table is None:
        logger.debug("astropy_table_to_list: Received None table.")
        return [], []

    try:
        columns: list[str] = list(table.colnames)
        rows: list[list[Any]] = [[_normalize_cell(row[col]) for col in columns] for row in table]
        logger.debug("astropy_table_to_list: Processed %s rows.", len(rows))
        return columns, rows
    except Exception as e:  # pragma: no cover
        logger.exception("ERROR in astropy_table_to_list: %s", e)
        traceback.print_exc()
        return [], []


def perform_coords_query(fields: dict[str, Any]) -> tuple[str | None, Table | None, str]:
    conds = [
        build_spatial_icrs_condition(
            fields["target_raj2000"]["value"],
            fields["target_dej2000"]["value"],
            fields["search_radius"]["value"],
        )
    ]
    return perform_query_with_conditions(fields, conds, limit=100)


def perform_time_query(fields: dict[str, Any]) -> tuple[str | None, Table | None, str]:
    conds = [
        build_time_overlap_condition(
            fields["search_mjd_start"]["value"],
            fields["search_mjd_end"]["value"],
        )
    ]
    return perform_query_with_conditions(fields, conds, limit=100)


def perform_coords_time_query(fields: dict[str, Any]) -> tuple[str | None, Table | None, str]:
    conds = [
        build_spatial_icrs_condition(
            fields["target_raj2000"]["value"],
            fields["target_dej2000"]["value"],
            fields["search_radius"]["value"],
        ),
        build_time_overlap_condition(
            fields["search_mjd_start"]["value"],
            fields["search_mjd_end"]["value"],
        ),
    ]
    return perform_query_with_conditions(fields, conds, limit=100)
