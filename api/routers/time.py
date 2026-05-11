from __future__ import annotations

from typing import Literal

import astropy.units as u
from astropy.time import Time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ConvertReq(BaseModel):
    value: str
    input_format: Literal["isot", "mjd", "met"] = "isot"
    input_scale: Literal["utc", "tt", "tai"] = "utc"
    met_epoch_isot: str | None = None
    met_epoch_scale: Literal["utc", "tt", "tai"] | None = "utc"


class ConvertResp(BaseModel):
    utc_isot: str
    utc_mjd: float
    tt_isot: str
    tt_mjd: float


@router.post("/api/convert_time", response_model=ConvertResp, tags=["time"])
def convert_time(req: ConvertReq) -> ConvertResp:
    if req.input_format == "met":
        if not req.met_epoch_isot:
            raise HTTPException(status_code=400, detail="met_epoch_isot required for MET.")

        iso = req.met_epoch_isot
        scale = req.met_epoch_scale or "utc"

        if iso.endswith("Z") and scale != "utc":
            iso = iso[:-1]

        epoch = Time(iso, format="isot", scale=scale)

        try:
            seconds = float(str(req.value).replace(",", "."))
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=400,
                detail="MET value must be numeric (seconds).",
            ) from exc

        t = epoch + seconds * u.s

    elif req.input_format == "mjd":
        try:
            mjd = float(str(req.value).replace(",", "."))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="MJD value must be numeric.") from exc

        t = Time(mjd, format="mjd", scale=req.input_scale)

    else:
        t = Time(req.value, format="isot", scale=req.input_scale)

    return ConvertResp(
        utc_isot=t.utc.isot,
        utc_mjd=float(t.utc.mjd),
        tt_isot=t.tt.isot,
        tt_mjd=float(t.tt.mjd),
    )
