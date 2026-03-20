from __future__ import annotations

import logging
import time
from collections.abc import Iterable

import httpx

logger = logging.getLogger(__name__)

# Cache value: (ts, cols, ok)
_TAP_COL_CACHE: dict[tuple[str, str], tuple[float, set[str], bool]] = {}

_TTL_OK_SECONDS = 3600
_TTL_ERR_SECONDS = 60
_MAX_CACHE = 256


def _split_table_name(table_fullname: str) -> tuple[str | None, str]:
    raw = (table_fullname or "").strip()
    if "." in raw:
        schema, table = raw.split(".", 1)
        schema = schema.strip()
        table = table.strip()
        return (schema or None, table)
    return (None, raw)


def _adql_escape(s: str) -> str:
    return (s or "").replace("'", "''")


def _cache_get(cache_key: tuple[str, str]) -> set[str] | None:
    now = time.time()
    item = _TAP_COL_CACHE.get(cache_key)
    if not item:
        return None
    ts, cols, ok = item
    ttl = _TTL_OK_SECONDS if ok else _TTL_ERR_SECONDS
    if now - ts < ttl:
        return cols
    _TAP_COL_CACHE.pop(cache_key, None)
    return None


def _cache_set(cache_key: tuple[str, str], cols: set[str], ok: bool) -> None:
    _TAP_COL_CACHE[cache_key] = (time.time(), cols, ok)

    # bound size
    if len(_TAP_COL_CACHE) > _MAX_CACHE:
        oldest_key = min(_TAP_COL_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _TAP_COL_CACHE.pop(oldest_key, None)


async def tap_supports_columns(
    tap_url: str,
    table_fullname: str,
    columns: Iterable[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    base_url = tap_url.rstrip("/")
    sync_url = base_url + "/sync"

    cols = [c.strip() for c in columns if c and c.strip()]
    if not cols:
        return True

    select_list = ", ".join(cols)
    adql = f"SELECT TOP 1 {select_list} FROM {table_fullname}"

    own_client = client is None
    http: httpx.AsyncClient = client if client is not None else httpx.AsyncClient(timeout=20.0)

    try:
        r = await http.post(
            sync_url,
            data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql},
        )

        if r.status_code != 200:
            txt = (r.text or "").lower()
            if (
                ("no such field" in txt)
                or ("unknown column" in txt)
                or ("could not be located" in txt)
                or ("unknown identifier" in txt)
            ):
                return False
            r.raise_for_status()

        return True
    finally:
        if own_client:
            await http.aclose()


async def get_tap_table_columns(
    tap_url: str,
    table_fullname: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> set[str]:
    base_url = tap_url.rstrip("/")
    cache_key = (base_url, (table_fullname or "").strip().lower())

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    schema, table = _split_table_name(table_fullname)
    schema_l = schema.lower() if schema else None
    table_l = table.lower()

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

    own_client = client is None
    http: httpx.AsyncClient = client if client is not None else httpx.AsyncClient(timeout=20.0)

    async def _run(adql_query: str) -> set[str]:
        r = await http.post(
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

        cols_out: set[str] = set()
        for row in payload.get("data", []) or []:
            if row and isinstance(row[0], str):
                cols_out.add(row[0].strip().lower())
        return cols_out

    try:
        cols = await _run(adql)

        if schema_l and not cols:
            fallback_adql = (
                "SELECT column_name FROM TAP_SCHEMA.columns "
                f"WHERE lower(table_name) = '{_adql_escape(table_l)}'"
            )
            cols = await _run(fallback_adql)

        _cache_set(cache_key, cols, ok=True)
        return cols

    except Exception as e:
        logger.warning(
            "get_tap_table_columns: TAP_SCHEMA lookup failed for tap_url=%s table=%s (%s)",
            tap_url,
            table_fullname,
            e,
            exc_info=True,
        )
        _cache_set(cache_key, set(), ok=False)
        return set()

    finally:
        if own_client:
            await http.aclose()
