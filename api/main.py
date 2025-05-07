from fastapi import FastAPI, Query, HTTPException, Body, Response, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from .models import SearchResult, UserTable
from .tap import (
    perform_coords_query,
    perform_time_query,
    perform_coords_time_query,
    astropy_table_to_list
)
import pyvo as vo
import math
import requests
from astropy.io.votable import parse_single_table
from io import BytesIO
import astropy.units as u
from astropy.coordinates import SkyCoord
from .auth import router as auth_router, current_optional_active_user
from starlette.middleware.sessions import SessionMiddleware
from .oidc import oidc_router
from starlette.staticfiles import StaticFiles
from .basket import basket_router
import urllib.parse
from astropy.time import Time
from datetime import datetime
from .query_history import query_history_router, QueryHistoryCreate, create_query_history
from typing import Optional
import fastapi_users
from .db import AsyncSessionLocal
import traceback
from .coords import coord_router


app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access and analyse high-energy astrophysics data from CTAO",
    version="1.0.0",
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key="SECRET_KEY",
    session_cookie="ctao_session",
    same_site="lax",  # 'lax'/'strict','none'
    https_only=False,
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/api/search_coords", response_model=SearchResult, tags=["search"])
async def search_coords(
    request: Request,
    # Coordinate Params
    coordinate_system: Optional[str] = None,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    l: Optional[float] = None,
    b: Optional[float] = None,
    search_radius: float = 5.0,
    # Time Params
    obs_start: Optional[str] = None,
    obs_end: Optional[str] = None,
    mjd_start: Optional[float] = Query(None),
    mjd_end: Optional[float] = Query(None),
    # TAP Params
    tap_url: str = 'http://voparis-tap-he.obspm.fr/tap',
    obscore_table: str = 'hess_dr.obscore_sdc',
    # Auth
    user: Optional[UserTable] = Depends(current_optional_active_user),
):
    print(f"DEBUG search_coords: START. Params received: {request.query_params}")

    fields = {
        'tap_url': {'value': tap_url},
        'obscore_table': {'value': obscore_table},
        'search_radius': {'value': search_radius}
    }
    coords_present = False
    time_filter_present = False

    # Process Time - prioritize MJD
    if mjd_start is not None and mjd_end is not None:
        if mjd_end <= mjd_start:
            raise HTTPException(status_code=400, detail="mjd_end must be greater than mjd_start.")
        fields['search_mjd_start'] = {'value': mjd_start}
        fields['search_mjd_end'] = {'value': mjd_end}
        time_filter_present = True
        print(f"DEBUG search_coords: Using MJD filter: {mjd_start} - {mjd_end}")
    elif obs_start and obs_end:  # Fallback to date/time strings
        try:
            dt_start = datetime.strptime(obs_start, "%d/%m/%Y %H:%M:%S")
            dt_end = datetime.strptime(obs_end, "%d/%m/%Y %H:%M:%S")
            if dt_end <= dt_start:
                raise HTTPException(status_code=400, detail="obs_end must be after obs_start.")
            t_start = Time(dt_start, scale='utc')
            t_end = Time(dt_end, scale='utc')
            fields['search_mjd_start'] = {'value': t_start.mjd}
            fields['search_mjd_end'] = {'value': t_end.mjd}
            time_filter_present = True
            print(f"DEBUG search_coords: Using Date/Time filter (converted to MJD): {t_start.mjd} - {t_end.mjd}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date/time format...")
        except Exception as e:
            print(f"ERROR: Unexpected error during time processing: {e}")
            raise HTTPException(status_code=500, detail="Error processing time parameters.")

    # Process coordinates
    if coordinate_system == 'equatorial':
        if ra is not None and dec is not None:
            fields['target_raj2000'] = {'value': ra}
            fields['target_dej2000'] = {'value': dec}
            coords_present = True
    elif coordinate_system == 'galactic':
        if l is not None and b is not None:
            try:
                c_gal = SkyCoord(l * u.deg, b * u.deg, frame='galactic')
                c_icrs = c_gal.icrs
                fields['target_raj2000'] = {'value': c_icrs.ra.deg}
                fields['target_dej2000'] = {'value': c_icrs.dec.deg}
                coords_present = True
            except Exception as coord_exc:
                 print(f"ERROR: Galactic conversion failed: {coord_exc}")
                 raise HTTPException(status_code=400, detail="Invalid galactic coordinates provided.")

    print(f"DEBUG search_coords: Fields prepared: {fields}")
    print(f"DEBUG search_coords: Coords present: {coords_present}, Time present: {time_filter_present}")

    adql_query_str = None
    res_table = None
    error = None

    try:
        if not coords_present and not time_filter_present:
            print("ERROR search_coords: No valid search criteria provided.")
            raise HTTPException(status_code=400, detail="Provide Coordinates or Time Interval.")

        if coords_present and time_filter_present:
            error, res_table, adql_query_str = perform_coords_time_query(fields)
        elif coords_present:
            error, res_table, adql_query_str = perform_coords_query(fields)
        elif time_filter_present:
            error, res_table, adql_query_str = perform_time_query(fields)

        print(f"DEBUG search_coords: After query call: error={error}, type(res_table)={type(res_table)}")

    except Exception as query_exc:
        print(f"ERROR search_coords: Exception during perform_query call: {query_exc}")
        raise HTTPException(status_code=500, detail="Failed during query execution.")

    if error is None:
        print(f"DEBUG search_coords: No error from query function. Processing table.")
        try:
            columns, data = astropy_table_to_list(res_table)
            print(f"DEBUG search_coords: astropy_table_to_list returned {len(columns)} cols, {len(data)} rows.")

            if not columns and not data and res_table is not None and len(res_table) > 0:
                 print("ERROR search_coords: astropy_table_to_list returned empty lists despite input.")
                 raise HTTPException(status_code=500, detail="Internal error processing results.")

            columns = list(columns) if columns else []
            data = [list(row) for row in data] if data else []
            print(f"DEBUG search_coords: Constructing SearchResult object.")

            search_result_obj = SearchResult(columns=columns, data=data)
            print(f"DEBUG search_coords: SearchResult object created: {type(search_result_obj)}")

            data_with_datalink = data
            columns_with_datalink = columns[:]

            if "obs_publisher_did" in columns_with_datalink:
                datalink_col = "datalink_url"
                if datalink_col not in columns_with_datalink:
                    columns_with_datalink.append(datalink_col)
                idx = columns_with_datalink.index("obs_publisher_did")

                # Create new data rows with the link appended
                data_with_datalink = []
                for row_idx, original_row in enumerate(data):
                    new_row = original_row[:]
                    # Ensure row has enough elements
                    if idx < len(new_row):
                        did = new_row[idx]
                        if did: # Check if DID is not None or empty
                           encoded_did = urllib.parse.quote(str(did), safe='')
                           # TODO: Construct URL based on actual request host/port if needed
                           # base_api_url = f"{request.url.scheme}://{request.url.netloc}"
                           # datalink_url = f"{base_api_url}/api/datalink?ID={encoded_did}"
                           datalink_url = f"http://localhost:8000/api/datalink?ID={encoded_did}"
                           if len(new_row) == len(columns_with_datalink) -1:
                               new_row.append(datalink_url)
                           elif len(new_row) == len(columns_with_datalink):
                               # If column existed, overwrite
                               new_row[columns_with_datalink.index(datalink_col)] = datalink_url
                           else:
                               print(f"WARN: Row {row_idx} length mismatch when adding datalink.")
                        else: # Handle empty DID
                             if len(new_row) == len(columns_with_datalink) -1: new_row.append(None)

                    else:
                         print(f"WARN: Row {row_idx} too short for DID index {idx}.")
                         if len(new_row) == len(columns_with_datalink) -1: new_row.append(None)

                    data_with_datalink.append(new_row)


            # recreate SearchResult with datalink info
            search_result_obj = SearchResult(columns=columns_with_datalink, data=data_with_datalink)
            print(f"DEBUG search_coords: SearchResult RECREATED with datalink.")

            if user:
                print(f"DEBUG: User {user.id} logged in, attempting to save history. ADQL: {adql_query_str}")
                try:
                    history_payload = QueryHistoryCreate(
                        query_params=fields,
                        adql_query=adql_query_str,
                        results=search_result_obj.model_dump()
                    )
                    async with AsyncSessionLocal() as history_session:
                         await create_query_history(history=history_payload, user=user, session=history_session)
                    print(f"DEBUG: Called create_query_history for user {user.id}")
                except Exception as history_error:
                     print(f"ERROR saving query history for user {user.id}: {history_error}")
                     traceback.print_exc()

            print(f"DEBUG search_coords: Returning SearchResult object.")
            return search_result_obj

        except Exception as processing_exc:
             print(f"ERROR search_coords: Exception during results processing: {processing_exc}")
             traceback.print_exc()
             raise HTTPException(status_code=500, detail="Internal error processing search results.")

    else:
        print(f"ERROR search_coords: Query function returned error: {error}")
        raise HTTPException(status_code=400, detail=error)

    # Failsafe
    print("ERROR search_coords: Reached end of function unexpectedly.")
    raise HTTPException(status_code=500, detail="Unexpected end of search processing.")


@app.post("/api/object_resolve", tags=["object_resolve"])
async def object_resolve(data: dict = Body(...)):
    """
    Unified endpoint to resolve an object name from either/both SIMBAD & NED,
    Example JSON:
    {
      "object_name": "M1",
      "use_simbad": true,
      "use_ned": false
    }
    """
    object_name = data.get("object_name", "").strip()
    use_simbad = data.get("use_simbad", False)
    use_ned = data.get("use_ned", False)

    if not object_name:
        raise HTTPException(status_code=400, detail="No object_name provided.")
    if not (use_simbad or use_ned):
        # Must pick at least one source
        return {"results": []}

    results = []
    simbad_list = []
    ned_list = []

    if use_simbad:
        SIMBAD_TAP_SERVER = "https://simbad.cds.unistra.fr/simbad/sim-tap"
        simbad_service = vo.dal.TAPService(SIMBAD_TAP_SERVER)

        query_simbad = (
            "SELECT basic.oid AS oid, ra AS ra, dec AS dec, main_id AS main_identifier "
            "FROM basic JOIN ident ON oidref=oid "
            f"WHERE id = '{object_name}'"
        )
        try:
            simbad_result = simbad_service.search(query_simbad)
        except Exception as e:
            print(f"Simbad query failed: {e}")
            simbad_result = []

        if len(simbad_result) > 0:
            for row in simbad_result:
                oid_val = row['oid']
                ra_val  = float(row['ra'])
                dec_val = float(row['dec'])
                main_id = str(row['main_identifier'])

                if math.isnan(ra_val) or math.isnan(dec_val):
                    continue

                simbad_list.append({
                    "service": "SIMBAD",
                    "name": main_id,
                    "ra": ra_val,
                    "dec": dec_val
                })

        results.extend(simbad_list)

    if use_ned:
        direct_query = (
            f"SELECT ra, dec, prefname "
            "FROM NEDTAP.objdir "
            f"WHERE prefname = '{object_name}'"
        )
        direct_results = _run_ned_sync_query(direct_query)
        ned_list.extend(direct_results)

        for nr in ned_list:
            results.append({
                "service": "NED",
                "name": nr["prefname"],
                "ra":  nr["ra"],
                "dec": nr["dec"]
            })

    return {"results": results}

def _run_ned_sync_query(adql_query):
    """
    Helper function to run a synchronous NED TAP query (returns a list of dict).
    By default, NED returns a VOTable. Parse it with astropy.io.votable.
    """
    url = "https://ned.ipac.caltech.edu/tap/sync"
    params = {
        "QUERY": adql_query,
        "LANG": "ADQL",
        "REQUEST": "doQuery",
        "FORMAT": "votable",
        "MAXREC": 5000
    }

    out = []
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()

        votable_buf = BytesIO(r.content)
        table = parse_single_table(votable_buf).to_table()

        # columns: ra, dec, prefname
        for row in table:
            ra_val  = float(row["ra"])
            dec_val = float(row["dec"])
            pref_val= str(row["prefname"])
            if math.isnan(ra_val) or math.isnan(dec_val):
                continue
            out.append({
                "ra": ra_val,
                "dec": dec_val,
                "prefname": pref_val
            })
    except Exception as e:
        print(f"NED query error: {e}")

    return out

@app.get("/api/datalink", tags=["datalink"])
async def datalink_endpoint(
    ID: list[str] = Query(..., description="One or more dataset identifiers (e.g., ivo://padc.obspm/hess#23523)")
):
    """
    DataLink endpoint that returns a VOTable containing links for each dataset ID.
    """
    rows = ""
    for id_val in ID:
        if id_val.lower().startswith("ivo://"):
            if '#' in id_val:
                # Extract the portion after '#' (e.g. "23523")
                obs_id_str = id_val.split('#', 1)[1]
                try:
                    obs_id_int = int(obs_id_str)
                    # Format the number with zero-padding to 6 digits
                    formatted_id = f"{obs_id_int:06d}"
                    # Construct the direct download URL from the unique obs_id.
                    direct_download_url = f"https://hess-dr.obspm.fr/retrieve/hess_dl3_dr1_obs_id_{formatted_id}.fits.gz"
                    error_message = ""
                    access_url = direct_download_url
                    service_def = ""
                except Exception:
                    access_url = ""
                    error_message = f"NotFoundFault: Invalid numeric obs id in {id_val}"
                    service_def = ""
            else:
                access_url = ""
                error_message = f"NotFoundFault: Missing '#' in {id_val}"
                service_def = ""
        else:
            access_url = ""
            error_message = f"NotFoundFault: {id_val} is not recognized as a valid ivo:// identifier"
            service_def = ""
        rows += (
            "                <TR>\n"
            f"                  <TD>{id_val}</TD>\n"
            f"                  <TD>{access_url}</TD>\n"
            f"                  <TD>{service_def}</TD>\n"
            f"                  <TD>{error_message}</TD>\n"
            "                </TR>\n"
        )

    votable_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
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
'''
    return Response(content=votable_xml, media_type="application/x-votable+xml")


app.include_router(auth_router)
# app.include_router(oidc_router)
app.include_router(oidc_router, prefix="/api")
app.include_router(basket_router)
app.include_router(query_history_router)
app.include_router(coord_router)
# Mount the React build folder
app.mount("/", StaticFiles(directory="./js/build", html=True), name="js")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
