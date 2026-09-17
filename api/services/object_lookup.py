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

CATALOG_RE = re.compile(
    r"^(?:M\s*0*\d{1,3}|NGC\s*0*\d{1,4}|IC\s*0*\d{1,4})$",
    re.IGNORECASE,
)


class Suggestion(TypedDict):
    service: str
    display_name: str
    resolve_name: str
    canonical_name: str


class SuggestResult(TypedDict):
    results: list[Suggestion]
    complete: bool


def valid_suggestion(
    suggestion: Mapping[str, Any],
) -> bool:
    required_fields = (
        "service",
        "display_name",
        "resolve_name",
        "canonical_name",
    )

    return all(
        isinstance(suggestion.get(field), str) and bool(str(suggestion[field]).strip())
        for field in required_fields
    )


def _settings() -> ApiSettings:
    return get_api_settings()


def is_short_catalog(q: str) -> bool:
    return bool(CATALOG_RE.fullmatch(q.strip()))


def adql_escape(s: str) -> str:
    return s.replace("'", "''")


def unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        cleaned = value.strip()

        if not cleaned or cleaned in seen:
            continue

        seen.add(cleaned)
        result.append(cleaned)

    return result


def simbad_query_variants(
    query: str,
) -> list[str]:
    q = query.strip()

    variants = [
        q,
        q.title(),
        q.upper(),
    ]

    if not q.upper().startswith("NAME "):
        variants.extend(
            [
                f"NAME {q}",
                f"NAME {q.title()}",
                f"NAME {q.upper()}",
            ]
        )

    variants.extend(catalog_variants(q))

    return unique_strings(variants)


def simbad_prefix_variants(
    query: str,
) -> list[str]:
    q = query.strip()

    variants = [
        q,
        q.title(),
        q.upper(),
    ]

    variants.extend(catalog_variants(q))

    return unique_strings(variants)


NAME_PREFIX_RE = re.compile(r"^\s*NAME\s+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


def clean_identifier(name: str) -> str:
    """
    Convert a catalog identifier into a user-facing representation.

    SIMBAD stores many common names with a leading 'NAME ', for example:
        NAME Crab Nebula

    The prefix should normally not be shown in
    the autocomplete menu.
    """
    value = str(name).strip()
    value = NAME_PREFIX_RE.sub("", value)
    return WHITESPACE_RE.sub(" ", value).strip()


MESSIER_NAME_RE = re.compile(
    r"^\s*(?:M|MESSIER)\s*0*(?P<num>\d{1,3})\s*$",
    re.IGNORECASE,
)

NGC_NAME_RE = re.compile(
    r"^\s*NGC\s*0*(?P<num>\d{1,4})\s*$",
    re.IGNORECASE,
)

IC_NAME_RE = re.compile(
    r"^\s*IC\s*0*(?P<num>\d{1,4})\s*$",
    re.IGNORECASE,
)


def normalize_identifier(name: str) -> str:
    """
    Produce a comparison key for common astronomical object identifiers.
    """
    cleaned = clean_identifier(name)

    messier_match = MESSIER_NAME_RE.fullmatch(cleaned)
    if messier_match:
        return f"M{int(messier_match.group('num'))}"

    ngc_match = NGC_NAME_RE.fullmatch(cleaned)
    if ngc_match:
        return f"NGC{int(ngc_match.group('num'))}"

    ic_match = IC_NAME_RE.fullmatch(cleaned)
    if ic_match:
        return f"IC{int(ic_match.group('num'))}"

    return re.sub(r"[^A-Z0-9]+", "", cleaned.upper())


def suggestion_match_score(query: str, identifier: str) -> tuple[int, int, int]:
    """
    Lower values sort first.

    Priority:
      0: exact visible-name match
      1: exact normalized match
      2: visible name starts with the query
      3: normalized identifier starts with normalized query
      4: query occurs elsewhere in the identifier
      5: other catalog result
    """
    query_clean = clean_identifier(query)
    identifier_clean = clean_identifier(identifier)

    query_casefold = query_clean.casefold()
    identifier_casefold = identifier_clean.casefold()

    query_normalized = normalize_identifier(query_clean)
    identifier_normalized = normalize_identifier(identifier_clean)

    if identifier_casefold == query_casefold:
        rank = 0
    elif identifier_normalized == query_normalized:
        rank = 1
    elif identifier_casefold.startswith(query_casefold):
        rank = 2
    elif query_normalized and identifier_normalized.startswith(query_normalized):
        rank = 3
    elif query_casefold in identifier_casefold:
        rank = 4
    else:
        rank = 5

    # Prefer less transformation and shorter identifiers when ranks tie
    prefix_penalty = 1 if NAME_PREFIX_RE.match(str(identifier)) else 0

    return rank, prefix_penalty, len(identifier_clean)


def build_simbad_suggestions(
    *,
    rows: Iterable[Mapping[str, str]],
    query: str,
    limit: int,
) -> list[Suggestion]:
    scored: list[
        tuple[
            tuple[int, int, int],
            str,
            str,
        ]
    ] = []

    for row in rows:
        matched_id = row["matched_id"]
        main_id = row["main_id"]

        if not matched_id or not main_id:
            continue

        scored.append(
            (
                suggestion_match_score(
                    query,
                    matched_id,
                ),
                matched_id,
                main_id,
            )
        )

    suggestions: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()

    for _, matched_id, main_id in sorted(
        scored,
        key=lambda item: (
            item[0],
            clean_identifier(item[1]).casefold(),
            item[2].casefold(),
        ),
    ):
        display_name = clean_identifier(matched_id)

        key = (
            normalize_identifier(display_name),
            normalize_identifier(main_id),
        )

        if key in seen:
            continue

        seen.add(key)

        suggestions.append(
            {
                "service": "SIMBAD",
                "display_name": display_name,
                "resolve_name": matched_id,
                "canonical_name": main_id,
            }
        )

        if len(suggestions) >= limit:
            break

    return suggestions


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


async def ned_resolve_via_objectlookup(
    name: str,
) -> dict[str, Any] | None:
    object_lookup_url = _settings().NED_OBJECT_LOOKUP_URL
    form = {"json": json.dumps({"name": {"v": name}})}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

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
    except requests.Timeout:
        logger.warning(
            "NED ObjectLookup resolution timed out for %r",
            name,
        )
        return None

    except requests.RequestException as exc:
        logger.warning(
            "NED ObjectLookup resolution failed for %r: %s",
            name,
            exc,
        )
        return None
    finally:
        vo_observe_call(
            "ned-objectlookup",
            object_lookup_url,
            time.perf_counter() - t0,
            ok,
        )

    try:
        obj = cast(dict[str, Any], resp.json())
    except (TypeError, ValueError):
        logger.exception(
            "NED returned invalid JSON for %r",
            name,
        )
        return None

    if obj.get("ResultCode") != 3:
        return None

    interpreted = obj.get("Interpreted") or {}
    preferred = obj.get("Preferred") or {}
    position = preferred.get("Position") or {}

    interpreted_name = str(interpreted.get("Name") or name).strip()

    canonical_name = str(preferred.get("Name") or interpreted_name).strip()

    try:
        ra = float(position["RA"])
        dec = float(position["Dec"])
    except (KeyError, TypeError, ValueError):
        logger.warning(
            "NED returned no valid position for %r: %r",
            name,
            obj,
        )
        return None

    return {
        "service": "NED",
        "name": canonical_name,
        "canonical_name": canonical_name,
        "ra": ra,
        "dec": dec,
    }


def run_tap_sync(
    url: str,
    adql: str,
    maxrec: int = 50,
    timeout: float = 5.0,
) -> Table:
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

        response = requests.get(
            url,
            params=params,
            timeout=timeout,
        )

        if not response.ok:
            logger.error(
                "SIMBAD TAP query failed with HTTP %s.\nADQL:\n%s\nResponse:\n%s",
                response.status_code,
                adql,
                response.text[:4000],
            )

        response.raise_for_status()
        ok = True

        return parse_single_table(BytesIO(response.content)).to_table()

    finally:
        vo_observe_call(
            "simbad-tap",
            url,
            time.perf_counter() - t0,
            ok,
        )


async def simbad_suggest(
    prefix: str,
    limit: int,
) -> tuple[bool, list[Suggestion]]:
    q = prefix.strip()

    if len(q) < 2:
        return True, []

    simbad_tap_sync = _settings().SIMBAD_TAP_SYNC
    tap_limit = min(max(limit * 3, 30), 100)

    exact_ok = True
    common_name_ok = True
    alias_ok = True

    exact_rows: list[dict[str, str]] = []
    exact_variants = simbad_query_variants(q)

    exact_conditions = " OR ".join(
        f"i.id = '{adql_escape(candidate)}'" for candidate in exact_variants
    )

    exact_sql = (
        "SELECT TOP 20 "
        "i.id AS matched_id, "
        "b.main_id AS main_id "
        "FROM ident AS i "
        "JOIN basic AS b ON i.oidref = b.oid "
        f"WHERE {exact_conditions}"
    )

    try:
        table = await asyncio.to_thread(
            run_tap_sync,
            simbad_tap_sync,
            exact_sql,
            20,
            5.0,
        )

        for row in cast(
            Iterable[Mapping[str, Any]],
            table,
        ):
            exact_rows.append(
                {
                    "matched_id": str(row["matched_id"]).strip(),
                    "main_id": str(row["main_id"]).strip(),
                }
            )

    except requests.Timeout:
        exact_ok = False
        logger.warning(
            "SIMBAD exact suggestion query timed out for %r",
            q,
        )

    except requests.RequestException as exc:
        exact_ok = False
        logger.warning(
            "SIMBAD exact suggestion request failed for %r: %s",
            q,
            exc,
        )

    except Exception:
        exact_ok = False
        logger.exception(
            "Unexpected SIMBAD exact suggestion failure for %r",
            q,
        )

    if exact_rows and is_short_catalog(q):
        return (
            exact_ok,
            build_simbad_suggestions(
                rows=exact_rows,
                query=q,
                limit=limit,
            ),
        )

    common_name_rows: list[dict[str, str]] = []

    common_name_variant = q if q.upper().startswith("NAME ") else f"NAME {q.title()}"

    common_name_limit = min(limit, 20)

    common_name_sql = (
        f"SELECT TOP {common_name_limit} "
        "i.id AS matched_id, "
        "b.main_id AS main_id "
        "FROM ident AS i "
        "JOIN basic AS b ON i.oidref = b.oid "
        f"WHERE i.id LIKE "
        f"'{adql_escape(common_name_variant)}%'"
    )

    try:
        table = await asyncio.to_thread(
            run_tap_sync,
            simbad_tap_sync,
            common_name_sql,
            common_name_limit,
            5.0,
        )

        for row in cast(
            Iterable[Mapping[str, Any]],
            table,
        ):
            common_name_rows.append(
                {
                    "matched_id": str(row["matched_id"]).strip(),
                    "main_id": str(row["main_id"]).strip(),
                }
            )

    except requests.Timeout:
        common_name_ok = False
        logger.warning(
            "SIMBAD common-name suggestion query timed out for %r",
            q,
        )

    except requests.RequestException as exc:
        common_name_ok = False
        logger.warning(
            "SIMBAD common-name suggestion request failed for %r: %s",
            q,
            exc,
        )

    except Exception:
        common_name_ok = False
        logger.exception(
            "Unexpected SIMBAD common-name suggestion failure for %r",
            q,
        )

    if common_name_rows:
        return (
            exact_ok and common_name_ok,
            build_simbad_suggestions(
                rows=[
                    *exact_rows,
                    *common_name_rows,
                ],
                query=q,
                limit=limit,
            ),
        )

    alias_rows: list[dict[str, str]] = []
    prefix_variants = simbad_prefix_variants(q)

    prefix_conditions = " OR ".join(
        f"i.id LIKE '{adql_escape(candidate)}%'" for candidate in prefix_variants
    )

    alias_sql = (
        f"SELECT DISTINCT TOP {tap_limit} "
        "i.id AS matched_id, "
        "b.main_id AS main_id "
        "FROM ident AS i "
        "JOIN basic AS b ON i.oidref = b.oid "
        f"WHERE {prefix_conditions}"
    )

    try:
        table = await asyncio.to_thread(
            run_tap_sync,
            simbad_tap_sync,
            alias_sql,
            tap_limit,
            5.0,
        )

        for row in cast(
            Iterable[Mapping[str, Any]],
            table,
        ):
            alias_rows.append(
                {
                    "matched_id": str(row["matched_id"]).strip(),
                    "main_id": str(row["main_id"]).strip(),
                }
            )

    except requests.Timeout:
        alias_ok = False
        logger.warning(
            "SIMBAD alias suggestion query timed out for %r",
            q,
        )

    except requests.RequestException as exc:
        alias_ok = False
        logger.warning(
            "SIMBAD alias suggestion request failed for %r: %s",
            q,
            exc,
        )

    except Exception:
        alias_ok = False
        logger.exception(
            "Unexpected SIMBAD alias suggestion failure for %r",
            q,
        )

    suggestions = build_simbad_suggestions(
        rows=[
            *exact_rows,
            *common_name_rows,
            *alias_rows,
        ],
        query=q,
        limit=limit,
    )

    return (
        exact_ok and common_name_ok and alias_ok,
        suggestions,
    )


def ned_extract_suggestions(
    doc: dict[str, Any],
    query: str,
) -> list[Suggestion]:
    code = doc.get("ResultCode")
    out: list[Suggestion] = []

    if code == 1:
        for entry in doc.get("FuzzyMatches", []) or []:
            name = entry.get("Name")

            if not name:
                continue

            catalog_name = str(name).strip()

            out.append(
                {
                    "service": "NED",
                    "display_name": clean_identifier(catalog_name),
                    "resolve_name": catalog_name,
                    "canonical_name": catalog_name,
                }
            )

        return out

    if code == 3:
        interpreted = doc.get("Interpreted") or {}
        preferred = doc.get("Preferred") or {}

        interpreted_name = str(interpreted.get("Name") or "").strip()

        preferred_name = str(preferred.get("Name") or interpreted_name).strip()

        if not interpreted_name:
            return []

        query_clean = clean_identifier(query)
        interpreted_clean = clean_identifier(interpreted_name)

        query_norm = normalize_identifier(query_clean)
        interpreted_norm = normalize_identifier(interpreted_clean)

        display_name = query_clean if query_norm == interpreted_norm else interpreted_clean

        return [
            {
                "service": "NED",
                "display_name": display_name,
                "resolve_name": interpreted_name,
                "canonical_name": preferred_name,
            }
        ]

    return out


def dedupe_ned_suggestions(
    suggestions: list[Suggestion],
    query: str,
    limit: int,
) -> list[Suggestion]:
    seen: set[tuple[str, str]] = set()
    scored: list[tuple[tuple[int, int, int], Suggestion]] = []

    for suggestion in suggestions:
        display_name = suggestion["display_name"]
        resolve_name = suggestion["resolve_name"]

        key = (
            normalize_identifier(display_name),
            normalize_identifier(resolve_name),
        )

        if key in seen:
            continue

        seen.add(key)
        scored.append(
            (
                suggestion_match_score(query, display_name),
                suggestion,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1]["display_name"].casefold(),
        )
    )

    return [suggestion for _, suggestion in scored[:limit]]


async def ned_suggest_raw(
    prefix: str,
) -> tuple[bool, list[Suggestion]]:
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
    except requests.Timeout:
        logger.warning(
            "NED ObjectLookup suggestion timed out for %r",
            q,
        )
        return False, []
    except requests.RequestException as exc:
        logger.warning(
            "NED ObjectLookup suggestion failed for %r: %s",
            q,
            exc,
        )
        return False, []
    except (TypeError, ValueError):
        logger.exception(
            "NED returned invalid JSON for suggestion query %r",
            q,
        )
        return False, []

    return True, ned_extract_suggestions(doc, q)


async def ned_suggest(
    prefix: str,
    limit: int,
) -> tuple[bool, list[Suggestion]]:
    ok, suggestions = await ned_suggest_raw(prefix)

    if not ok:
        return False, []

    return True, dedupe_ned_suggestions(
        suggestions,
        query=prefix,
        limit=limit,
    )


async def object_suggest_impl(
    *,
    q: str,
    use_simbad: bool,
    use_ned: bool,
    limit: int,
) -> SuggestResult:
    q = q.strip()

    if len(q) < 4 and not is_short_catalog(q):
        return {
            "results": [],
            "complete": True,
        }

    if not (use_simbad or use_ned):
        return {
            "results": [],
            "complete": True,
        }

    simbad_task = simbad_suggest(q, limit) if use_simbad else asyncio.sleep(0, result=(True, []))

    ned_task = ned_suggest(q, limit) if use_ned else asyncio.sleep(0, result=(True, []))

    (simbad_ok, simbad_list), (ned_ok, ned_list) = await asyncio.gather(
        simbad_task,
        ned_task,
    )

    merged: list[Suggestion] = []

    for simbad_item, ned_item in itertools.zip_longest(
        simbad_list,
        ned_list,
        fillvalue=None,
    ):
        if simbad_item is not None:
            merged.append(simbad_item)

            if len(merged) >= limit:
                break

        if ned_item is not None:
            merged.append(ned_item)

            if len(merged) >= limit:
                break

    results = [suggestion for suggestion in merged if valid_suggestion(suggestion)][:limit]

    if use_simbad and not simbad_ok:
        logger.warning(
            "SIMBAD suggestions were incomplete for query %r",
            q,
        )

    if use_ned and not ned_ok:
        logger.warning(
            "NED suggestions were unavailable for query %r",
            q,
        )

    return {
        "results": results,
        "complete": ((not use_simbad or simbad_ok) and (not use_ned or ned_ok)),
    }


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
    except Exception as exc:
        logger.warning(
            "SIMBAD resolution failed for alias %r: %s",
            alias,
            exc,
        )
        return []


def collect_simbad_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for row in rows:
        try:
            ra_val = float(row["ra"])
            dec_val = float(row["dec"])
        except (KeyError, TypeError, ValueError):
            continue

        if math.isnan(ra_val) or math.isnan(dec_val):
            continue

        canonical_name = str(row["main_id"]).strip()

        if not canonical_name:
            continue

        out.append(
            {
                "service": "SIMBAD",
                # Keep name for backward compatibility
                "name": canonical_name,
                "canonical_name": canonical_name,
                "ra": ra_val,
                "dec": dec_val,
            }
        )

    return out


def resolve_via_simbad(
    name: str,
    tap_base: str,
) -> list[dict[str, Any]]:
    simbad = vo.dal.TAPService(tap_base)
    alias_raw = name.strip()

    candidates = unique_strings(
        [
            alias_raw,
            *catalog_variants(alias_raw),
            alias_raw.title(),
            alias_raw.upper(),
            *([] if alias_raw.upper().startswith("NAME ") else [f"NAME {alias_raw.title()}"]),
        ]
    )

    for alias in candidates:
        rows = simbad_search_aliases(
            simbad,
            alias,
            top=1,
        )
        results = collect_simbad_rows(rows)

        if results:
            return results

    return []


async def object_resolve_impl(
    *,
    resolve_name: str,
    use_simbad: bool,
    use_ned: bool,
) -> dict[str, list[dict[str, Any]]]:
    if not (use_simbad or use_ned):
        return {"results": []}

    cleaned_name = resolve_name.strip()

    allow_ned_resolution = use_ned and (len(cleaned_name) >= 4 or is_short_catalog(cleaned_name))

    simbad_task = (
        asyncio.to_thread(
            resolve_via_simbad,
            cleaned_name,
            _settings().SIMBAD_TAP_BASE,
        )
        if use_simbad
        else asyncio.sleep(0, result=[])
    )

    ned_task = (
        ned_resolve_via_objectlookup(cleaned_name)
        if allow_ned_resolution
        else asyncio.sleep(0, result=None)
    )

    simbad_results, ned_result = await asyncio.gather(
        simbad_task,
        ned_task,
    )

    results: list[dict[str, Any]] = list(simbad_results)

    if ned_result is not None:
        results.append(ned_result)

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
