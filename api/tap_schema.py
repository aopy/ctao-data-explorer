from __future__ import annotations

import logging
import time
from collections.abc import Iterable

import httpx

logger = logging.getLogger(__name__)


# in-memory cache: (tap_url, table_fullname_lower) -> (timestamp, set(columns_lower))
_TAP_COL_CACHE: dict[tuple[str, str], tuple[float, set[str]]] = {}
_TTL_SECONDS = 3600


def _split_table_name(table_fullname: str) -> tuple[str | None, str]:
    """
    Split a table name into (schema, table). Accepts:
      - "schema.table"
      - "table"
      - whitespace around parts
    Returns (None, table) if no schema.
    """
    raw = (table_fullname or "").strip()
    if "." in raw:
        schema, table = raw.split(".", 1)
        schema = schema.strip()
        table = table.strip()
        return (schema or None, table)
    return (None, raw)


def _adql_escape(s: str) -> str:
    # ADQL string literal escape
    return (s or "").replace("'", "''")


async def tap_supports_columns(tap_url: str, table_fullname: str, columns: Iterable[str]) -> bool:
    """
    Fallback check when TAP_SCHEMA is unavailable:
    try a minimal query selecting the candidate columns from the real table.

    Returns True if the query succeeds, False if TAP reports "unknown field/column".
    Raises for other HTTP/network errors.
    """
    base_url = tap_url.rstrip("/")
    sync_url = base_url + "/sync"

    cols = [c.strip() for c in columns if c and c.strip()]
    if not cols:
        return True

    # Minimal query: TOP 1 with selected columns
    select_list = ", ".join(cols)
    adql = f"SELECT TOP 1 {select_list} FROM {table_fullname}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            sync_url,
            data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql},
        )

    # If TAP returns non-200, try to interpret as "unknown column"
    if r.status_code != 200:
        txt = (r.text or "").lower()
        if (
            ("no such field" in txt)
            or ("unknown column" in txt)
            or ("could not be located" in txt)
            or ("unknown identifier" in txt)
        ):
            return False
        # otherwise it's a real server error
        r.raise_for_status()

    return True


async def get_tap_table_columns(tap_url: str, table_fullname: str) -> set[str]:
    """
    Query TAP_SCHEMA.columns to find available columns for the given table.
    Returns a set of column names (lower-cased).
    Cached to avoid repeated schema hits.
    """
    base_url = tap_url.rstrip("/")
    cache_key = (base_url, (table_fullname or "").strip().lower())
    now = time.time()

    cached = _TAP_COL_CACHE.get(cache_key)
    if cached and (now - cached[0] < _TTL_SECONDS):
        return cached[1]

    schema, table = _split_table_name(table_fullname)
    schema_l = schema.lower() if schema else None
    table_l = table.lower()

    # Preferred ADQL: schema + table (when schema provided)
    if schema_l:
        adql = (
            "SELECT column_name FROM TAP_SCHEMA.columns "
            f"WHERE lower(schema_name) = '{_adql_escape(schema_l)}' "
            f"AND lower(table_name)  = '{_adql_escape(table_l)}'"
        )
    else:
        adql = (
            "SELECT column_name FROM TAP_SCHEMA.columns "
            f"WHERE lower(table_name) = '{_adql_escape(table_l)}'"
        )

    sync_url = base_url + "/sync"

    async def _run(adql_query: str) -> set[str]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                sync_url,
                data={
                    "REQUEST": "doQuery",
                    "LANG": "ADQL",
                    "FORMAT": "json",
                    "QUERY": adql_query,
                },
            )
            r.raise_for_status()
            payload = r.json()

        cols: set[str] = set()
        for row in payload.get("data", []) or []:
            if row and isinstance(row[0], str):
                cols.add(row[0].strip().lower())
        return cols

    cols = set()
    try:
        cols = await _run(adql)

        # if schema-qualified lookup returns nothing try table-only
        if schema_l and not cols:
            fallback_adql = (
                "SELECT column_name FROM TAP_SCHEMA.columns "
                f"WHERE lower(table_name) = '{_adql_escape(table_l)}'"
            )
            cols = await _run(fallback_adql)

    except Exception as e:
        logger.warning(
            "get_tap_table_columns: TAP_SCHEMA lookup failed for tap_url=%s table=%s (%s)",
            tap_url,
            table_fullname,
            e,
            exc_info=True,
        )
        cols = set()

    _TAP_COL_CACHE[cache_key] = (now, cols)
    return cols
