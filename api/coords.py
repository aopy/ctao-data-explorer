import logging
import math

import astropy.units as u
from astropy.coordinates import SkyCoord
from fastapi import APIRouter
from pydantic import BaseModel, Field, validator

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
    def system_must_be_valid(cls: type["CoordInput"], v: str) -> str:
        if v not in ["hmsdms", "deg", "gal"]:
            raise ValueError("System must be 'hmsdms', 'deg', or 'gal'")
        return v


class CoordOutput(BaseModel):
    # Output always includes decimal degrees if successful
    ra_deg: float | None = None
    dec_deg: float | None = None
    l_deg: float | None = None
    b_deg: float | None = None
    error: str | None = None


class CoordConvertOutput(BaseModel):
    ra_deg: float | None = None
    dec_deg: float | None = None
    ra_hms: str | None = None
    dec_dms: str | None = None
    l_deg: float | None = None
    b_deg: float | None = None
    error: str | None = None


coord_router = APIRouter()


def _normalize_system(sys_raw: str) -> str:
    s = (sys_raw or "").strip().lower()
    return COORD_SYS_ALIASES.get(s, s)


def _parse_to_icrs(coord1_str: str, coord2_str: str, system: str) -> SkyCoord:
    """
    Return ICRS SkyCoord from an input pair in one of:
      - deg (ICRS ra/dec degrees)
      - hmsdms (ICRS ra hourangle, dec degrees)
      - gal (galactic l/b degrees)
    """
    if system == "deg":
        ra = float(coord1_str)
        dec = float(coord2_str)
        if not (0.0 <= ra <= 360.0):
            raise ValueError("RA must be between 0 and 360 degrees.")
        if not (-90.0 <= dec <= 90.0):
            raise ValueError("Dec must be between -90 and +90 degrees.")
        return SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")

    if system == "hmsdms":
        # RA in hourangle, Dec in degrees
        return SkyCoord(coord1_str, coord2_str, unit=(u.hourangle, u.deg), frame="icrs")

    if system == "gal":
        gal_l = float(coord1_str)
        gal_b = float(coord2_str)
        if not (0.0 <= gal_l <= 360.0):
            raise ValueError("Galactic l must be between 0 and 360 degrees.")
        if not (-90.0 <= gal_b <= 90.0):
            raise ValueError("Galactic b must be between -90 and +90 degrees.")
        return SkyCoord(l=gal_l * u.deg, b=gal_b * u.deg, frame="galactic").icrs

    raise ValueError("Unsupported coordinate system specified.")


def _format_hms_dms(c_icrs: SkyCoord) -> tuple[str, str]:
    """
    Match your example formatting:
      RA:  "05 34 31.9"
      Dec: "+22 00 52"
    """
    ra_hms = c_icrs.ra.to_string(unit=u.hourangle, sep=" ", precision=1, pad=True)
    dec_dms = c_icrs.dec.to_string(unit=u.deg, sep=" ", precision=0, alwayssign=True, pad=True)
    return ra_hms, dec_dms


@coord_router.post("/api/parse_coords", response_model=CoordOutput, tags=["coords"])
async def parse_coordinates_endpoint(coord_input: CoordInput) -> CoordOutput:
    """
    Parses coordinate strings in:
      - Decimal Degrees (ICRS): system='deg' (aliases: eqdeg/equatorial/icrs/radec/ra/dec)
      - HMS/DMS (ICRS): system='hmsdms' (aliases: hms/dms)
      - Galactic (l/b in degrees): system='gal' (aliases: galactic, lb, l/b)
    Returns RA/Dec in decimal degrees (ICRS). For galactic input, l/b are echoed back.
    """
    logger.debug("/api/parse_coords received: %s", coord_input)
    try:
        system = _normalize_system(coord_input.system)
        coord1_str = (coord_input.coord1 or "").strip()
        coord2_str = (coord_input.coord2 or "").strip()
        if not coord1_str or not coord2_str:
            raise ValueError("Coordinate strings cannot be empty.")

        c_icrs = _parse_to_icrs(coord1_str, coord2_str, system)

        ra_deg = float(c_icrs.ra.deg) % 360.0
        dec_deg = float(c_icrs.dec.deg)
        if not (math.isfinite(ra_deg) and math.isfinite(dec_deg)):
            raise ValueError("Parsed coordinates are not finite.")

        if system == "gal":
            # echo back original l/b
            return CoordOutput(
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                l_deg=float(coord1_str),
                b_deg=float(coord2_str),
            )
        return CoordOutput(ra_deg=ra_deg, dec_deg=dec_deg)

    except ValueError as ve:
        logger.exception("ERROR parsing coordinates: %s", ve)
        return CoordOutput(error=f"Invalid input: {ve}")
    except Exception as e:
        logger.exception("ERROR unexpected during coordinate parsing: %s", e)
        return CoordOutput(error="Server error during coordinate parsing.")


@coord_router.post("/api/convert_coords", response_model=CoordConvertOutput, tags=["coords"])
async def convert_coordinates_endpoint(coord_input: CoordInput) -> CoordConvertOutput:
    """
    Parse input coords in the given system and return:
      - ICRS ra/dec in degrees
      - ICRS ra in hms string + dec in dms string
      - Galactic l/b in degrees
    """
    logger.debug("/api/convert_coords received: %s", coord_input)
    try:
        system = _normalize_system(coord_input.system)
        coord1_str = (coord_input.coord1 or "").strip()
        coord2_str = (coord_input.coord2 or "").strip()
        if not coord1_str or not coord2_str:
            raise ValueError("Coordinate strings cannot be empty.")

        c_icrs = _parse_to_icrs(coord1_str, coord2_str, system)

        ra_deg = float(c_icrs.ra.deg) % 360.0
        dec_deg = float(c_icrs.dec.deg)
        if not (math.isfinite(ra_deg) and math.isfinite(dec_deg)):
            raise ValueError("Parsed coordinates are not finite.")

        ra_hms, dec_dms = _format_hms_dms(c_icrs)

        c_gal = c_icrs.galactic
        l_deg = float(c_gal.l.deg) % 360.0
        b_deg = float(c_gal.b.deg)
        if not (math.isfinite(l_deg) and math.isfinite(b_deg)):
            raise ValueError("Converted galactic coordinates are not finite.")

        return CoordConvertOutput(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            ra_hms=ra_hms,
            dec_dms=dec_dms,
            l_deg=l_deg,
            b_deg=b_deg,
        )

    except ValueError as ve:
        logger.exception("ERROR converting coordinates: %s", ve)
        return CoordConvertOutput(error=f"Invalid input: {ve}")
    except Exception as e:
        logger.exception("ERROR unexpected during coordinate conversion: %s", e)
        return CoordConvertOutput(error="Server error during coordinate conversion.")
