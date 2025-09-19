import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Optional
from astropy.coordinates import SkyCoord
import astropy.units as u
import logging
logger = logging.getLogger(__name__)


class CoordInput(BaseModel):
    coord1: str = Field(..., description="First coordinate string (e.g., RA, l)")
    coord2: str = Field(..., description="Second coordinate string (e.g., Dec, b)")
    system: str = Field(..., description="'hmsdms', 'deg', or 'gal'")

    @validator('system')
    def system_must_be_valid(cls, v):
        if v not in ['hmsdms', 'deg', 'gal']:
            raise ValueError("System must be 'hmsdms', 'deg', or 'gal'")
        return v

class CoordOutput(BaseModel):
    # Output always includes decimal degrees if successful
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    l_deg: Optional[float] = None
    b_deg: Optional[float] = None
    error: Optional[str] = None

coord_router = APIRouter()

@coord_router.post("/api/parse_coords", response_model=CoordOutput, tags=["coords"])
async def parse_coordinates_endpoint(coord_input: CoordInput):
    """
    Parses coordinate strings (Decimal Degrees, HMS/DMS, Galactic)
    and returns decimal degree values (RA/Dec).
    """

    logger.debug("/api/parse_coords received: %s", coord_input )
    try:
        coord1_str = coord_input.coord1.strip()
        coord2_str = coord_input.coord2.strip()

        if not coord1_str or not coord2_str:
             raise ValueError("Coordinate strings cannot be empty.")

        if coord_input.system == 'hmsdms':
            # Assume RA in hourangle, Dec in degrees
            sc = SkyCoord(ra=coord1_str, dec=coord2_str, unit=(u.hourangle, u.deg), frame='icrs')
            # Validate parsed values are finite
            if not np.isfinite(sc.ra.deg) or not np.isfinite(sc.dec.deg):
                 raise ValueError("Parsed HMS/DMS resulted in non-finite values.")
            return CoordOutput(ra_deg=sc.ra.deg, dec_deg=sc.dec.deg)

        elif coord_input.system == 'deg':
            # Parse and validate decimal degrees
            ra = float(coord1_str)
            dec = float(coord2_str)
            if not (0 <= ra <= 360): raise ValueError("RA must be between 0 and 360.")
            if not (-90 <= dec <= 90): raise ValueError("Dec must be between -90 and 90.")
            return CoordOutput(ra_deg=ra, dec_deg=dec)

        elif coord_input.system == 'gal':
             # Parse and validate galactic coordinates
             l = float(coord1_str)
             b = float(coord2_str)
             if not (0 <= l <= 360): raise ValueError("Galactic l must be between 0 and 360.")
             if not (-90 <= b <= 90): raise ValueError("Galactic b must be between -90 and 90.")
             # Convert galactic to ICRS (RA/Dec) for consistency
             sc_gal = SkyCoord(l=l*u.deg, b=b*u.deg, frame='galactic')
             sc_icrs = sc_gal.icrs
             if not np.isfinite(sc_icrs.ra.deg) or not np.isfinite(sc_icrs.dec.deg):
                  raise ValueError("Parsed Galactic coords resulted in non-finite RA/Dec values.")
             return CoordOutput(ra_deg=sc_icrs.ra.deg, dec_deg=sc_icrs.dec.deg, l_deg=l, b_deg=b)

        else:
             raise ValueError("Unsupported coordinate system specified.")

    except ValueError as ve: # Catch specific parsing/validation errors
        logger.exception("ERROR parsing coordinates: %s", ve)
        # Return error in the response model using status code
        # raise HTTPException(status_code=400, detail=f"Invalid input: {ve}")
        return CoordOutput(error=f"Invalid input: {ve}")
    except Exception as e: # Catch other unexpected errors (e.g., SkyCoord issues)
        logger.exception("ERROR unexpected during coordinate parsing: %s", e)
        import traceback
        traceback.print_exc()
        # raise HTTPException(status_code=500, detail="Server error during coordinate parsing.")
        return CoordOutput(error="Server error during coordinate parsing.")
