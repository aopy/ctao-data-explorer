from __future__ import annotations

import html

from fastapi import APIRouter, Query, Response

router = APIRouter()


def _build_datalink_row(id_val: str) -> str:
    access_url = ""
    service_def = ""
    error_message = ""

    if id_val.lower().startswith("ivo://"):
        if "#" in id_val:
            obs_id_str = id_val.split("#", 1)[1]

            try:
                obs_id_int = int(obs_id_str)
                formatted_id = f"{obs_id_int:06d}"
                access_url = (
                    "https://hess-dr.obspm.fr/retrieve/"
                    f"hess_dl3_dr1_obs_id_{formatted_id}.fits.gz"
                )
            except Exception:
                error_message = f"NotFoundFault: Invalid numeric obs id in {id_val}"
        else:
            error_message = f"NotFoundFault: Missing '#' in {id_val}"
    else:
        error_message = f"NotFoundFault: {id_val} is not recognized as a valid ivo:// identifier"

    return (
        "                <TR>\n"
        f"                  <TD>{html.escape(id_val)}</TD>\n"
        f"                  <TD>{html.escape(access_url)}</TD>\n"
        f"                  <TD>{html.escape(service_def)}</TD>\n"
        f"                  <TD>{html.escape(error_message)}</TD>\n"
        "                </TR>\n"
    )


@router.get("/api/datalink", tags=["datalink"])
@router.get("/datalink", tags=["datalink"], include_in_schema=False)
async def datalink_endpoint(
    id_: list[str] = Query(
        ...,
        alias="ID",
        description="One or more dataset identifiers, e.g. ivo://padc.obspm/hess#23523",
    ),
) -> Response:
    rows = "".join(_build_datalink_row(id_val) for id_val in id_)

    votable_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
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
"""

    return Response(content=votable_xml, media_type="application/x-votable+xml")
