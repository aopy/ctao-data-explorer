"""Small TAP and storage mocks used only by the Helm load-test chart."""

from __future__ import annotations

import html
import os
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

# Captured from ``SELECT TOP 1 * FROM ctao_sdc.obscore`` on 2026-08-25.
OBSCORE_FIELDS: tuple[tuple[str, str, str | None], ...] = (
    ("dataproduct_type", "char", "*"),
    ("dataproduct_subtype", "char", "*"),
    ("calib_level", "short", None),
    ("obs_collection", "char", "*"),
    ("obs_id", "char", "*"),
    ("obs_title", "char", "*"),
    ("obs_publisher_did", "char", "*"),
    ("obs_creator_did", "char", "*"),
    ("access_url", "char", "*"),
    ("access_format", "char", "*"),
    ("access_estsize", "long", None),
    ("target_name", "char", "*"),
    ("target_class", "char", "*"),
    ("s_ra", "double", None),
    ("s_dec", "double", None),
    ("s_fov", "float", None),
    ("s_region", "char", "*"),
    ("s_resolution", "float", None),
    ("t_min", "double", None),
    ("t_max", "double", None),
    ("t_exptime", "float", None),
    ("t_resolution", "float", None),
    ("em_min", "float", None),
    ("em_max", "float", None),
    ("em_res_power", "float", None),
    ("o_ucd", "char", "*"),
    ("pol_states", "char", "*"),
    ("facility_name", "char", "*"),
    ("instrument_name", "char", "*"),
    ("s_xel1", "int", None),
    ("s_xel2", "int", None),
    ("t_xel", "int", None),
    ("em_xel", "int", None),
    ("pol_xel", "int", None),
    ("s_pixel_scale", "float", None),
    ("em_ucd", "char", "*"),
    ("preview", "char", "*"),
    ("source_table", "char", "*"),
    ("obs_creation_date", "char", "*"),
    ("obs_creator_name", "char", "*"),
    ("publisher_id", "char", "*"),
    ("obs_release_date", "char", "*"),
    ("data_rights", "char", "*"),
    ("s_calib_status", "char", "*"),
    ("t_calib_status", "char", "*"),
    ("em_calib_status", "char", "*"),
    ("em_unit", "char", "*"),
    ("proposal_id", "char", "*"),
    ("proposal_tag", "char", "*"),
    ("ev_xel", "int", None),
    ("s_ref_energy", "double", None),
    ("em_ref_energy", "double", None),
    ("s_ref_oaa", "double", None),
    ("em_ref_oaa", "double", None),
    ("t_intervals", "char", "*"),
    ("energy_min", "double", None),
    ("energy_max", "double", None),
    ("obs_mode", "char", "*"),
    ("tracking_mode", "char", "*"),
    ("scan_mode", "char", "*"),
    ("pointing_mode", "char", "*"),
    ("analysis_mode", "char", "*"),
    ("event_type", "char", "*"),
    ("messenger_name", "char", "*"),
    ("messenger_pdgid", "char", "*"),
    ("observing_period", "char", "*"),
    ("lunar_cycle_id", "char", "*"),
    ("release_reference", "char", "*"),
    ("alt_min", "char", "*"),
    ("alt_max", "char", "*"),
    ("alt_pnt", "char", "*"),
    ("az_pnt", "char", "*"),
    ("sky_brigthness", "char", "*"),
    ("ontime", "char", "*"),
    ("livetime", "char", "*"),
    ("deadc", "char", "*"),
    ("n_tels", "char", "*"),
    ("tellist", "char", "*"),
    ("ev_class", "char", "*"),
    ("coverage", "char", "*"),
    ("scs_id", "char", "*"),
    ("datalink", "char", "*"),
    ("access_url_this", "char", "*"),
    ("lfn", "char", "*"),
)
FIELD_NAMES = tuple(field[0] for field in OBSCORE_FIELDS)


def synthetic_obscore(count: int) -> list[dict[str, Any]]:
    """Return repeatable records; 100 records occupy each of 500 sky tiles."""
    rows: list[dict[str, Any]] = []
    for offset in range(count):
        obs_id = 5_000_000_001 + offset
        tile = offset // 100
        ra = 83.63 if tile == 0 else float((tile % 25) * 14 + 7)
        dec = 22.01 if tile == 0 else float(-70 + (tile // 25) * 7)
        rows.append(
            {
                "dataproduct_type": "event",
                "dataproduct_subtype": "event-list",
                "calib_level": 2,
                "obs_collection": "CTAO-SDC-load-test",
                "obs_id": str(obs_id),
                "obs_title": f"Synthetic observation {obs_id}",
                "obs_publisher_did": f"ivo://padc.obspm/ctao-sdc#{obs_id}",
                "obs_creator_did": f"ivo://padc.obspm/ctao-sdc#{obs_id}",
                "access_url": f"/api/datalink?ID=ivo%3A%2F%2Fpadc.obspm%2Fctao-sdc%23{obs_id}",
                "access_format": "application/x-votable+xml;content=datalink",
                "access_estsize": (1, 8, 64)[offset % 3],
                "target_name": "Synthetic sky tile",
                "target_class": "unknown",
                "s_ra": ra,
                "s_dec": dec,
                "s_fov": 5.0,
                "s_region": f"CIRCLE ICRS {ra} {dec} 2.5",
                "s_resolution": 0.1,
                "t_min": 60000.0 + tile,
                "t_max": 60000.5 + tile,
                "t_exptime": 1800.0,
                "em_min": 1e-13,
                "em_max": 1e-10,
                "energy_min": 1e11,
                "energy_max": 1e14,
                "facility_name": "CTAO",
                "instrument_name": "Synthetic",
                "proposal_id": f"LOAD-{tile:03d}",
                "obs_mode": "WOBBLE",
                "tracking_mode": "SIDEREAL",
                "pointing_mode": "PARALLEL",
                "datalink": f"/api/datalink?ID=ivo%3A%2F%2Fpadc.obspm%2Fctao-sdc%23{obs_id}",
                "access_url_this": f"https://localhost:9999/objects/{obs_id}",
                "lfn": f"lfn:/data/load-test/{obs_id}.fits",
            }
        )
    return rows


def _selected_columns(query: str) -> list[str]:
    normalized = " ".join(query.split())
    if not normalized.upper().startswith("SELECT "):
        return list(FIELD_NAMES)
    columns, separator, _ = normalized[7:].partition(" FROM ")
    if not separator:
        return list(FIELD_NAMES)
    top = columns.split(maxsplit=2)
    if len(top) >= 2 and top[0].upper() == "TOP" and top[1].isdigit():
        columns = top[2] if len(top) == 3 else ""
    if columns == "*":
        return list(FIELD_NAMES)
    return [column.strip().split(".")[-1] for column in columns.split(",")]


def _limit(query: str) -> int | None:
    match = re.search(r"SELECT\s+TOP\s+(\d+)", query, re.I)
    return int(match.group(1)) if match else None


def _filter_rows(rows: Iterable[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    circle = re.search(r"CIRCLE\('ICRS',\s*([\d.-]+),\s*([\d.-]+),\s*([\d.-]+)\)", query, re.I)
    if not circle:
        return list(rows)
    ra, dec, radius = (float(value) for value in circle.groups())
    return [
        row for row in rows if abs(row["s_ra"] - ra) <= radius and abs(row["s_dec"] - dec) <= radius
    ]


def _votable(columns: list[str], rows: Iterable[dict[str, Any]]) -> str:
    field_defs = {name: (datatype, arraysize) for name, datatype, arraysize in OBSCORE_FIELDS}
    fields = "".join(
        f'<FIELD name="{html.escape(column)}" datatype="{field_defs.get(column, ("char", "*"))[0]}"'
        + (
            f' arraysize="{field_defs[column][1]}"'
            if column in field_defs and field_defs[column][1]
            else ""
        )
        + "/>"
        for column in columns
    )
    data = "".join(
        "<TR>"
        + "".join(f"<TD>{html.escape(str(row.get(column, '')))}</TD>" for column in columns)
        + "</TR>"
        for row in rows
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<VOTABLE version="1.5" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">'
        '<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK">Query successful</INFO>'
        f"<TABLE>{fields}<DATA><TABLEDATA>{data}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"
    )


def create_tap_app(count: int | None = None) -> FastAPI:
    rows = synthetic_obscore(count or int(os.getenv("MOCK_TAP_RECORD_COUNT", "1000")))
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, int | str]:
        return {"status": "ok", "records": len(rows)}

    @app.post("/tap/sync")
    async def sync(request: Request) -> Response:
        form = parse_qs((await request.body()).decode())
        query = form.get("QUERY", [""])[0]
        fmt = form.get("FORMAT", ["votable"])[0].lower()
        if "tap_schema.columns" in query.lower():
            return PlainTextResponse("column_name\n" + "\n".join(FIELD_NAMES) + "\n")
        columns = _selected_columns(query)
        result_rows = _filter_rows(rows, query)
        limit = _limit(query)
        if limit is not None:
            result_rows = result_rows[:limit]
        if fmt == "csv":
            return PlainTextResponse(
                ",".join(columns)
                + "\n"
                + "\n".join(
                    ",".join(str(row.get(column, "")) for column in columns) for row in result_rows
                )
            )
        return Response(_votable(columns, result_rows), media_type="application/x-votable+xml")

    return app


tap_app = create_tap_app()
