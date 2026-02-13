from __future__ import annotations

import time

import httpx

# in-memory cache: (tap_url, table_fullname_lower) -> (timestamp, set(columns_lower))
_TAP_COL_CACHE: dict[tuple[str, str], tuple[float, set[str]]] = {}
_TTL_SECONDS = 15 * 60  # 15 minutes


def _split_table_name(full: str) -> tuple[str | None, str]:
    """
    TAP_SCHEMA.columns uses table_name (no schema) and sometimes schema_name.
    For "schema.table", return ("schema", "table"). Otherwise (None, "table").
    """
    if "." in full:
        s, t = full.split(".", 1)
        return s, t
    return None, full


async def get_tap_table_columns(tap_url: str, table_fullname: str) -> set[str]:
    """
    Query TAP_SCHEMA.columns to find available columns for the given table.
    Returns a set of column names (lower-cased).
    Cached to avoid repeated schema hits.
    """
    key = (tap_url.rstrip("/"), table_fullname.lower())
    now = time.time()

    cached = _TAP_COL_CACHE.get(key)
    if cached and (now - cached[0] < _TTL_SECONDS):
        return cached[1]

    schema, table = _split_table_name(table_fullname)

    # ADQL against TAP_SCHEMA.columns
    if schema:
        adql = (
            "SELECT column_name FROM TAP_SCHEMA.columns "
            f"WHERE lower(schema_name) = '{schema.lower()}' "
            f"AND lower(table_name) = '{table.lower()}'"
        )
    else:
        adql = (
            "SELECT column_name FROM TAP_SCHEMA.columns "
            f"WHERE lower(table_name) = '{table.lower()}'"
        )

    # Standard TAP sync endpoint
    sync_url = key[0] + "/sync"

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            sync_url,
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "json",
                "QUERY": adql,
            },
        )
        r.raise_for_status()
        payload = r.json()

    cols: set[str] = set()

    for row in payload.get("data", []) or []:
        if row and isinstance(row[0], str):
            cols.add(row[0].lower())

    _TAP_COL_CACHE[key] = (now, cols)
    return cols
