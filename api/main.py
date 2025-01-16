from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from .models import SearchResult
from .tap import perform_query, astropy_table_to_list
import pyvo as vo
import math
import requests
from astropy.io.votable import parse_single_table
from io import BytesIO
import astropy.units as u
from astropy.coordinates import SkyCoord

app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access and analyse high-energy astrophysics data from CTAO",
    version="1.0.0",
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/api/search_coords", response_model=SearchResult)
async def search_coords(
    coordinate_system: str,
    # if equatorial
    ra: float = None,
    dec: float = None,
    # if galactic
    l: float = None,
    b: float = None,
    search_radius: float = Query(..., ge=0.0, le=90.0),
    tap_url: str = Query('http://voparis-tap-he.obspm.fr/tap', title="TAP Server URL"),
    obscore_table: str = Query('hess_dr.obscore_sdc', title="ObsCore Table Name")
):
    """
    Endpoint that accepts coordinate_system='equatorial' or 'galactic'.
    If galactic, transform (l, b) => (RA, Dec) before running the cone search.
    """
    # Validate coordinate_system
    if coordinate_system not in ('equatorial', 'galactic'):
        raise HTTPException(status_code=400, detail="Invalid coordinate system")

    # transform to RA/Dec if needed
    if coordinate_system == 'equatorial':
        if ra is None or dec is None:
            raise HTTPException(status_code=400, detail="Missing RA/Dec in equatorial mode")
        final_ra = ra
        final_dec = dec
    else:
        # coordinate_system == 'galactic'
        if l is None or b is None:
            raise HTTPException(status_code=400, detail="Missing l/b in galactic mode")
        # Use astropy to convert l,b => RA,Dec
        c_gal = SkyCoord(l*u.deg, b*u.deg, frame='galactic')
        c_icrs = c_gal.icrs
        final_ra = c_icrs.ra.deg
        final_dec = c_icrs.dec.deg

    form_data = {
        'target_raj2000': {'value': final_ra},
        'target_dej2000': {'value': final_dec},
        'search_radius': {'value': search_radius},
        'tap_url': {'value': tap_url},
        'obscore_table': {'value': obscore_table},
    }
    error, res_table = perform_query(form_data)
    if error is None:
        columns, data = astropy_table_to_list(res_table)
        return SearchResult(columns=columns, data=data)
    else:
        raise HTTPException(status_code=400, detail=error)

@app.post("/api/object_resolve", tags=["Search"])
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

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
