from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable

import httpx

logger = logging.getLogger(__name__)

# Cache value: (ts, cols, ok)
_TAP_COL_CACHE: dict[tuple[str, str], tuple[float, set[str], bool]] = {}

_TTL_OK_SECONDS = 3600
_TTL_ERR_SECONDS = 60
_MAX_CACHE = 256

_MISSING_COL_PATTERNS = (
    r"no such field",
    r"unknown column",
    r"could not be located",
    r"unknown identifier",
    r"column .* does not exist",
)

TAP_QUERY_STATUS_ERROR_MSG = "TAP query returned QUERY_STATUS=ERROR"


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


def _looks_like_missing_column(msg: str) -> bool:
    s = (msg or "").lower()
    return any(re.search(p, s) for p in _MISSING_COL_PATTERNS)


def _extract_tap_error_message(body: str) -> str | None:
    """
    Detect a TAP/VOTable error returned with HTTP 200.
    DaCHS commonly includes QUERY_STATUS value="ERROR" inside an <INFO> element.
    """
    if not body:
        return None

    b = body
    # Quick pre-checks to keep it fast
    if "QUERY_STATUS" not in b or 'value="ERROR"' not in b:
        return None

    # Find the error marker
    pos = b.find('value="ERROR"')
    if pos == -1:
        return None

    # Walk backwards to find the start of the INFO tag that contains it
    info_open = b.rfind("<INFO", 0, pos)
    if info_open == -1:
        return TAP_QUERY_STATUS_ERROR_MSG

    # Find end of opening tag
    info_tag_end = b.find(">", info_open)
    if info_tag_end == -1:
        return TAP_QUERY_STATUS_ERROR_MSG

    # Find closing tag
    info_close = b.find("</INFO>", info_tag_end)
    if info_close == -1:
        return TAP_QUERY_STATUS_ERROR_MSG

    # Extract and normalize whitespace
    msg = b[info_tag_end + 1 : info_close]
    msg = " ".join(msg.split())
    return msg.strip() or TAP_QUERY_STATUS_ERROR_MSG


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
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "csv",
                "QUERY": adql,
            },
        )
        body = r.text or ""
        tap_err = _extract_tap_error_message(body)
        if r.status_code == 200 and tap_err:
            if _looks_like_missing_column(tap_err) or _looks_like_missing_column(body):
                return False
            raise httpx.HTTPStatusError(
                f"TAP returned an error payload for column probe: {tap_err}",
                request=r.request,
                response=r,
            )
        if r.status_code != 200:
            if _looks_like_missing_column(body):
                return False
            r.raise_for_status()
        return True
    finally:
        if own_client:
            await http.aclose()


def _build_tap_schema_adql(schema_l: str | None, table_l: str) -> str:
    if schema_l:
        return (
            "SELECT column_name FROM TAP_SCHEMA.columns "
            f"WHERE lower(schema_name) = '{_adql_escape(schema_l)}' "
            f"AND lower(table_name)  = '{_adql_escape(table_l)}'"
        )
    return (
        "SELECT column_name FROM TAP_SCHEMA.columns "
        f"WHERE lower(table_name) = '{_adql_escape(table_l)}'"
    )


def _parse_single_col_csv(text: str) -> set[str]:
    """
    Parse a CSV response that contains a single column header: column_name
    and return a set of lowercased values.
    """
    raw = text or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return set()

    out: set[str] = set()
    for ln in lines[1:]:
        v = ln.strip().strip('"').strip("'").strip()
        if v:
            out.add(v.lower())
    return out


async def _run_tap_schema_query(
    http: httpx.AsyncClient, sync_url: str, adql_query: str
) -> set[str]:
    r = await http.post(
        sync_url,
        data={
            "REQUEST": "doQuery",
            "LANG": "ADQL",
            "FORMAT": "csv",
            "QUERY": adql_query,
        },
    )
    r.raise_for_status()
    return _parse_single_col_csv(r.text)


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

    sync_url = base_url + "/sync"
    adql = _build_tap_schema_adql(schema_l, table_l)
    fallback_adql = _build_tap_schema_adql(None, table_l) if schema_l else None

    async def _execute(http: httpx.AsyncClient) -> set[str]:
        cols = await _run_tap_schema_query(http, sync_url, adql)
        if fallback_adql and not cols:
            cols = await _run_tap_schema_query(http, sync_url, fallback_adql)
        return cols

    try:
        if client is not None:
            cols = await _execute(client)
        else:
            async with httpx.AsyncClient(timeout=20.0) as http:
                cols = await _execute(http)

        _cache_set(cache_key, cols, ok=True)
        return cols

    except Exception as e:
        logger.warning(
            "get_tap_table_columns: TAP_SCHEMA lookup failed (%s)",
            repr(e),
            exc_info=True,
        )
        _cache_set(cache_key, set(), ok=False)
        return set()
