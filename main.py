from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from models import SearchResult

from pydantic import BaseModel, Field
import uvicorn

from tap import Tap, perform_query, astropy_table_to_list

app = FastAPI(
    title="CTAO Data Explorer API",
    description="An API to access high-energy astrophysics data from CTAO",
    version="1.0.0",
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates directory
templates = Jinja2Templates(directory="templates")

# Pydantic model to define and validate the form data
class SearchForm(BaseModel):
    target_raj2000: float = Field(
        ..., title="Target RA (deg)", ge=0.0, le=360.0, description="Right Ascension of target in degrees (J2000)"
    )
    target_dej2000: float = Field(
        ..., title="Target DEC (deg)", ge=-90.0, le=90.0, description="Declination of target in degrees (J2000)"
    )
    search_radius: float = Field(
        ..., title="Cone Search Radius (deg)", ge=0.0, le=90.0, description="Cone Search radius in degrees"
    )


# Route handlers
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_get(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

@app.post("/search", response_class=HTMLResponse)
async def search_post(
    request: Request,
    target_raj2000: float = Form(...),
    target_dej2000: float = Form(...),
    search_radius: float = Form(...)
):
    # Validate and store form data
    form_data = {
        'target_raj2000': {'value': target_raj2000},
        'target_dej2000': {'value': target_dej2000},
        'search_radius': {'value': search_radius}
    }

    # Perform TAP query
    error, res_table = perform_query(form_data)

    if error is None:
        # Process results
        colnames = res_table.fieldnames
        rows = astropy_table_to_list(res_table)

        context = {
            "request": request,
            "data": rows,
            "columns": colnames
        }
        return templates.TemplateResponse("search_results.html", context)
    else:
        # Return to search page with error message
        return templates.TemplateResponse("search.html", {"request": request, "error": error})

@app.get("/api/search", response_model=SearchResult, tags=["Search"])
async def api_search(
    target_raj2000: float = Query(..., ge=0.0, le=360.0, description="Right Ascension in degrees (J2000)", example=83.6331),
    target_dej2000: float = Query(..., ge=-90.0, le=90.0, description="Declination in degrees (J2000)", example=22.0145),
    search_radius: float = Query(..., ge=0.0, le=90.0, description="Cone search radius in degrees", example=0.1),
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
