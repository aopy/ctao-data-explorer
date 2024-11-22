from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import SearchResult
from .tap import perform_query, astropy_table_to_list

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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# API endpoint
@app.get("/api/search", response_model=SearchResult, tags=["Search"])
async def api_search(
    target_raj2000: float = Query(..., ge=0.0, le=360.0),
    target_dej2000: float = Query(..., ge=-90.0, le=90.0),
    search_radius: float = Query(..., ge=0.0, le=90.0)
):
    form_data = {
        'target_raj2000': {'value': target_raj2000},
        'target_dej2000': {'value': target_dej2000},
        'search_radius': {'value': search_radius},
    }
    error, res_table = perform_query(form_data)

    if error is None:
        colnames = res_table.fieldnames
        rows = astropy_table_to_list(res_table)
        result = SearchResult(columns=colnames, data=rows)
        return result
    else:
        raise HTTPException(status_code=400, detail=error)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
