from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import re
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from io import BytesIO
from typing import Any, TypedDict, cast

import pyvo as vo
import requests
from astropy.io.votable import parse_single_table
from astropy.table import Table

from api.config import ApiSettings, get_api_settings
from api.metrics import vo_observe_call

logger = logging.getLogger(__name__)

MAX_ALIAS_LEN = 32

CATALOG_SPACED_RE = re.compile(
    r"^\s*(?P<cat>M|NGC|IC)\s{0,2}0*(?P<num>\d{1,4})\s*$",
    re.IGNORECASE,
)

CATALOG_RE = re.compile(r"^(?:M\d{1,3}|NGC\d{1,4}|IC\d{1,4})$", re.IGNORECASE)


class SuggestResult(TypedDict):
    results: list[dict[str, Any]]


def _settings() -> ApiSettings:
    return get_api_settings()


def is_short_catalog(q: str) -> bool:
    return bool(CATALOG_RE.match(q.strip()))


def adql_escape(s: str) -> str:
    return s.replace("'", "''")


def catalog_variants(name: str) -> Iterator[str]:
    s = name.strip()

    if len(s) > MAX_ALIAS_LEN:
        return

    m = CATALOG_SPACED_RE.fullmatch(s)

    if not m:
        return

    cat = m.group("cat").upper()
    num = m.group("num")

    if cat == "M" and len(num) > 3:
        return

    width = 3 if cat == "M" else 4
    spaces_needed = max(1, width - len(num))

    for n_spaces in range(spaces_needed, spaces_needed + 3):
        yield f"{cat}{' ' * n_spaces}{num}"


async def ned_resolve_via_objectlookup(name: str) -> dict[str, Any] | None:
    object_lookup_url = _settings().NED_OBJECT_LOOKUP_URL
    form = {"json": json.dumps({"name": {"v": name}})}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    t0 = time.perf_counter()
    ok = False

    try:
        resp = await asyncio.to_thread(
            requests.post,
            object_lookup_url,
            data=form,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        ok = True
    except Exception as exc:
        logger.exception("NED ObjectLookup failed: %s", exc)
        return None
    finally:
        vo_observe_call(
            "ned-objectlookup",
            object_lookup_url,
            time.perf_counter() - t0,
            ok,
        )

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


def run_tap_sync(url: str, adql: str, maxrec: int = 50) -> Table:
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


async def simbad_suggest(prefix: str, limit: int) -> list[dict[str, Any]]:
    q = prefix.strip()

    if len(q) < 2:
        return []

    simbad_tap_sync = _settings().SIMBAD_TAP_SYNC
    q_uc = q.upper()
    rows: list[str] = []

    exact_sql = (
        f"SELECT TOP 1 b.main_id "
        f"FROM ident i JOIN basic b ON i.oidref = b.oid "
        f"WHERE i.id = '{adql_escape(q_uc)}'"
    )

    try:
        tab = await asyncio.to_thread(run_tap_sync, simbad_tap_sync, exact_sql, 1)
        rows.extend(str(r["main_id"]).strip() for r in cast(Iterable[Mapping[str, Any]], tab))
    except Exception as exc:  # pragma: no cover
        logger.exception("SIMBAD exact failed: %s", exc)

    pat_raw = adql_escape(q)
    pat_title = adql_escape(q.title())
    pat_name = f"NAME {adql_escape(q.title())}"

    alias_sql = (
        f"SELECT DISTINCT TOP 200 b.main_id "
        f"FROM ident i JOIN basic b ON i.oidref = b.oid "
        f"WHERE i.id LIKE '{pat_raw}%' "
        f"   OR i.id LIKE '{pat_title}%' "
        f"   OR i.id LIKE '{pat_name}%'"
    )

    try:
        tab = await asyncio.to_thread(run_tap_sync, simbad_tap_sync, alias_sql, 200)
        rows.extend(str(r["main_id"]).strip() for r in tab)
    except Exception as exc:  # pragma: no cover
        logger.exception("SIMBAD alias LIKE failed: %s", exc)

    q_cmp = q_uc.replace(" ", "")
    scored: list[tuple[int, int, str]] = []

    for n in rows:
        n_cmp = n.upper().replace(" ", "")
        score = 0 if n_cmp == q_cmp else 1 if n_cmp.startswith(q_cmp) else 2
        scored.append((score, len(n_cmp), n))

    seen: set[str] = set()
    ordered: list[str] = []

    for _, _, n in sorted(scored):
        if n not in seen:
            ordered.append(n)
            seen.add(n)

            if len(ordered) == limit:
                break

    return [{"service": "SIMBAD", "name": n} for n in ordered]


def ned_extract_names(doc: dict[str, Any]) -> list[str]:
    code = doc.get("ResultCode")

    if code == 1:
        out: list[str] = []

        for entry in doc.get("FuzzyMatches", []) or []:
            name = entry.get("Name")

            if name:
                out.append(str(name))

        return out

    if code == 3:
        nm = (doc.get("Interpreted") or {}).get("Name")
        return [str(nm)] if nm else []

    return []


def dedupe_to_ned_out(names: list[str], limit: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    for n in names:
        if n in seen:
            continue

        seen.add(n)
        out.append({"service": "NED", "name": n})

        if len(out) >= limit:
            break

    return out


async def ned_suggest_raw(prefix: str) -> tuple[bool, list[str]]:
    q = prefix.strip()

    if len(q) < 2:
        return True, []

    object_lookup_url = _settings().NED_OBJECT_LOOKUP_URL
    form = {"json": json.dumps({"name": {"v": q}})}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = await asyncio.to_thread(
            requests.post,
            object_lookup_url,
            data=form,
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        doc = cast(dict[str, Any], resp.json())
    except Exception:
        logger.exception("NED ObjectLookup failed")
        return False, []

    return True, ned_extract_names(doc)


async def ned_suggest(prefix: str, limit: int) -> tuple[bool, list[dict[str, Any]]]:
    ok, names = await ned_suggest_raw(prefix)

    if not ok:
        return False, []

    return True, dedupe_to_ned_out(names, limit)


async def object_suggest_impl(
    *,
    q: str,
    use_simbad: bool,
    use_ned: bool,
    limit: int,
) -> SuggestResult:
    q = q.strip()

    if len(q) < 4 and not is_short_catalog(q):
        return {"results": []}

    if not (use_simbad or use_ned):
        return {"results": []}

    simbad_task = simbad_suggest(q, limit) if use_simbad else asyncio.sleep(0, result=[])
    ned_task = ned_suggest(q, limit) if use_ned else asyncio.sleep(0, result=(True, []))

    simbad_list, (ned_ok, ned_list) = await asyncio.gather(simbad_task, ned_task)

    merged: list[dict[str, Any]] = []

    for sim, ned in itertools.zip_longest(simbad_list, ned_list, fillvalue=None):
        if sim is not None:
            merged.append(sim)

            if len(merged) >= limit:
                break

        if ned is not None:
            merged.append(ned)

            if len(merged) >= limit:
                break

    results = merged[:limit]

    if use_ned and not ned_ok:
        # The router decides whether to cache. This marker is intentionally not exposed.
        return {"results": results}

    return {"results": results}


def simbad_search_aliases(
    simbad: vo.dal.TAPService,
    alias: str,
    top: int = 1,
) -> Sequence[Mapping[str, Any]]:
    sql = (
        f"SELECT TOP {top} ra, dec, main_id "
        "FROM ident i JOIN basic b ON b.oid = i.oidref "
        f"WHERE i.id = '{adql_escape(alias)}'"
    )

    try:
        res = simbad.search(sql)
        return cast(Sequence[Mapping[str, Any]], res)
    except Exception:
        return []


def collect_simbad_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for row in rows:
        ra_val = float(row["ra"])
        dec_val = float(row["dec"])

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


def resolve_via_simbad(name: str, tap_base: str) -> list[dict[str, Any]]:
    simbad = vo.dal.TAPService(tap_base)
    alias_raw = name.strip()

    candidates: list[str] = [alias_raw]
    candidates.extend(list(catalog_variants(alias_raw)))
    candidates.append(alias_raw.title())
    candidates.append(alias_raw.upper())

    if not alias_raw.upper().startswith("NAME "):
        candidates.append("NAME " + alias_raw.title())

    seen: set[tuple[str, float, float]] = set()
    results: list[dict[str, Any]] = []

    for alias in candidates:
        rows = simbad_search_aliases(simbad, alias, top=1)

        for item in collect_simbad_rows(rows):
            key = (str(item["name"]), float(item["ra"]), float(item["dec"]))

            if key not in seen:
                seen.add(key)
                results.append(item)

    return results


async def object_resolve_impl(
    *,
    object_name: str,
    use_simbad: bool,
    use_ned: bool,
) -> dict[str, list[dict[str, Any]]]:
    if not (use_simbad or use_ned):
        return {"results": []}

    results: list[dict[str, Any]] = []

    if use_simbad:
        results.extend(resolve_via_simbad(object_name, _settings().SIMBAD_TAP_BASE))

    if use_ned:
        resolved = await ned_resolve_via_objectlookup(object_name)

        if resolved:
            results.append(resolved)

    return {"results": results}


def run_ned_sync_query(adql_query: str) -> list[dict[str, Any]]:
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

    except Exception as exc:
        logger.error("NED query error: %s", exc)

    return out
