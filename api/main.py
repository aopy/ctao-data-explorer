from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from .models import SearchResult
from .tap import perform_query, astropy_table_to_list
import pyvo as vo
import math

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

@app.get("/api/search", response_model=SearchResult, tags=["Search"])
async def api_search(
    target_raj2000: float = Query(..., ge=0.0, le=360.0, example=83.6331),
    target_dej2000: float = Query(..., ge=-90.0, le=90.0, example=22.0145),
    search_radius: float = Query(..., ge=0.0, le=90.0, example=0.1),
    tap_url: str = Query('http://voparis-tap-he.obspm.fr/tap', title="TAP Server URL"),
    obscore_table: str = Query('hess_dr.obscore_sdc', title="ObsCore Table Name")
):
    form_data = {
        'target_raj2000': {'value': target_raj2000},
        'target_dej2000': {'value': target_dej2000},
        'search_radius': {'value': search_radius},
        'tap_url': {'value': tap_url},
        'obscore_table': {'value': obscore_table},
    }
    error, res_table = perform_query(form_data)

    if error is None:
        columns, data = astropy_table_to_list(res_table)
        result = SearchResult(columns=columns, data=data)
        return result
    else:
        raise HTTPException(status_code=400, detail=error)

@app.post("/api/simbad_resolve", tags=["Search"])
async def simbad_resolve(data: dict = Body(...)):
    """
    Resolve an exact object name via Simbad TAP.
    """
    object_name = data.get("object_name")
    if not object_name:
        raise HTTPException(status_code=400, detail="No object_name provided")

    SIMBAD_TAP_SERVER = "https://simbad.cds.unistra.fr/simbad/sim-tap"
    service = vo.dal.TAPService(SIMBAD_TAP_SERVER)

    # Rename columns: oid as oid, RA as ra, DEC as dec, main_id as main_identifier
    query = (
        "SELECT basic.oid AS oid, ra AS ra, dec AS dec, main_id AS main_identifier "
        "FROM basic "
        "JOIN ident ON oidref = oid "
        f"WHERE id = '{object_name}';"
    )

    try:
        result_set = service.search(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simbad query failed: {e}")

    # print("fieldnames:", result_set.fieldnames)

    if len(result_set) == 0:
        return {"results": []}

    results = []
    for row in result_set:
        # Access with lowercase aliases
        oid_val = row['oid']
        ra_val = row['ra']
        dec_val = row['dec']
        main_id = row['main_identifier']

        # Convert to Python native types, handle NaN
        oid_val = int(oid_val)
        ra_val = float(ra_val)
        dec_val = float(dec_val)
        main_id = str(main_id)

        if math.isnan(ra_val) or math.isnan(dec_val):
            continue

        results.append({
            "oid": oid_val,
            "ra": ra_val,
            "dec": dec_val,
            "Main_identifier": main_id
        })

    return {"results": results}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
