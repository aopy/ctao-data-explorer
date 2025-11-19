from fastapi import APIRouter
from pydantic import BaseModel, Field, validator
from typing import Optional
from astropy.coordinates import SkyCoord
import astropy.units as u
import math
import logging

logger = logging.getLogger(__name__)

COORD_SYS_ALIASES = {
    "equatorial": "deg",
    "eqdeg": "deg",
    "icrs": "deg",
    "radec": "deg",
    "ra/dec": "deg",
    "galactic": "gal",
    "lb": "gal",
    "l/b": "gal",
    "hms": "hmsdms",
    "dms": "hmsdms",
    # keep canonical keys mapping to themselves
    "deg": "deg",
    "gal": "gal",
    "hmsdms": "hmsdms",
}


class CoordInput(BaseModel):
    coord1: str = Field(..., description="First coordinate string (e.g., RA, l)")
    coord2: str = Field(..., description="Second coordinate string (e.g., Dec, b)")
    system: str = Field(..., description="'hmsdms', 'deg', or 'gal'")

    @validator("system")
    def system_must_be_valid(cls, v):
        if v not in ["hmsdms", "deg", "gal"]:
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
    Parses coordinate strings in:
      - Decimal Degrees (ICRS): system='deg' (aliases: eqdeg/equatorial/icrs/radec/ra/dec)
      - HMS/DMS (ICRS): system='hmsdms' (aliases: hms/dms)
      - Galactic (l/b in degrees): system='gal' (aliases: galactic, lb, l/b)
    Returns RA/Dec in decimal degrees (ICRS). For galactic input, l/b are echoed back.
    """
    logger.debug("/api/parse_coords received: %s", coord_input)

    try:
        # Normalize system via aliases (case-insensitive)
        sys_raw = (coord_input.system or "").strip().lower()
        system = COORD_SYS_ALIASES.get(sys_raw, sys_raw)

        coord1_str = (coord_input.coord1 or "").strip()
        coord2_str = (coord_input.coord2 or "").strip()
        if not coord1_str or not coord2_str:
            raise ValueError("Coordinate strings cannot be empty.")

        if system == "deg":
            # Decimal degrees in ICRS
            ra = float(coord1_str)
            dec = float(coord2_str)
            if not (0.0 <= ra <= 360.0):
                raise ValueError("RA must be between 0 and 360 degrees.")
            if not (-90.0 <= dec <= 90.0):
                raise ValueError("Dec must be between -90 and +90 degrees.")
            c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")

        elif system == "hmsdms":
            # RA in hourangle, Dec in deg, still ICRS
            c = SkyCoord(
                coord1_str, coord2_str, unit=(u.hourangle, u.deg), frame="icrs"
            )

        elif system == "gal":
            # l/b in degrees → convert to ICRS
            gal_l = float(coord1_str)
            gal_b = float(coord2_str)
            if not (0.0 <= gal_l <= 360.0):
                raise ValueError("Galactic l must be between 0 and 360 degrees.")
            if not (-90.0 <= gal_b <= 90.0):
                raise ValueError("Galactic b must be between -90 and +90 degrees.")
            c = SkyCoord(l=gal_l * u.deg, b=gal_b * u.deg, frame="galactic").icrs
        else:
            raise ValueError("Unsupported coordinate system specified.")

        ra_deg = float(c.ra.deg) % 360.0
        dec_deg = float(c.dec.deg)
        if not (math.isfinite(ra_deg) and math.isfinite(dec_deg)):
            raise ValueError("Parsed coordinates are not finite.")

        extra = {}
        if system == "gal":
            extra = {"l_deg": float(coord1_str), "b_deg": float(coord2_str)}

        return CoordOutput(ra_deg=ra_deg, dec_deg=dec_deg, **extra)

    except ValueError as ve:
        logger.exception("ERROR parsing coordinates: %s", ve)
        return CoordOutput(error=f"Invalid input: {ve}")
    except Exception as e:
        logger.exception("ERROR unexpected during coordinate parsing: %s", e)
        return CoordOutput(error="Server error during coordinate parsing.")
