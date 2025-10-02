from typing import Optional, List, Dict, Any, Union
import base64
import httpx
import xmltodict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from .config import get_settings
from .db import encrypt_token as enc_str, decrypt_token as dec_str
from .deps import get_db, get_current_user
from .models import ExternalToken

router = APIRouter(prefix="/api/opus", tags=["opus"])
settings = get_settings()

# OPUS configuration from .env
OPUS_ROOT = settings.OPUS_ROOT.rstrip("/")
OPUS_SERVICE = settings.OPUS_SERVICE.strip("/")

# Helpers
def _user_id(user: Union[dict, object]) -> Optional[int]:
    """Return numeric user id from dict or object (None if missing)."""
    if isinstance(user, dict):
        return user.get("id") or user.get("app_user_id") or user.get("user_id")
    return getattr(user, "id", None)


def _auth_header(email: str, token: str) -> Dict[str, str]:
    b = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": f"Basic {b}"}


def _rest_url(*parts: str) -> str:
    """Join OPUS_ROOT with path segments, avoiding duplicate slashes."""
    base = OPUS_ROOT.rstrip("/")
    path = "/".join(str(p).strip("/") for p in parts if p is not None)
    return f"{base}/{path}"


def _xml_to_json(xml_text: str) -> Dict[str, Any]:
    try:
        return xmltodict.parse(xml_text)
    except Exception:
        return {"raw": xml_text}


async def _get_creds(db: AsyncSession, user_id: int) -> Dict[str, str]:
    row = await db.execute(
        select(ExternalToken).where(
            ExternalToken.user_id == user_id,
            ExternalToken.service == "opus",
        )
    )
    rec: Optional[ExternalToken] = row.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=400, detail="OPUS credentials not set")
    token = dec_str(rec.token_encrypted)
    if not token:
        raise HTTPException(status_code=500, detail="Cannot decrypt OPUS token")
    return {"email": rec.email, "token": token}


# Schemas
class OpusCredentialsIn(BaseModel):
    email: str
    token: str

class QuickLookParams(BaseModel):
    # basket ids, OPUS ignores this
    obs_ids: List[str] = []
    # Fields expected by OPUS service gammapy_maps
    RA: float
    Dec: float
    nxpix: int = 400
    nypix: int = 400
    binsz: float = 0.02

    # If provided, OPUS will use these obs IDs
    obsids: Optional[str] = None


class OpusJobCreateResponse(BaseModel):
    job_id: str
    location: str


# debug
@router.get("/_debug_base")
async def debug_base():
    return {"OPUS_ROOT": OPUS_ROOT, "OPUS_SERVICE": OPUS_SERVICE}


# Routes
@router.post("/settings", status_code=204)
async def save_settings(
    payload: OpusCredentialsIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    row = await db.execute(
        select(ExternalToken).where(
            ExternalToken.user_id == uid,
            ExternalToken.service == "opus",
        )
    )
    rec = row.scalar_one_or_none()
    if rec:
        rec.email = payload.email
        rec.token_encrypted = enc_str(payload.token)
    else:
        rec = ExternalToken(
            user_id=uid,
            service="opus",
            email=payload.email,
            token_encrypted=enc_str(payload.token),
        )
        db.add(rec)
    await db.commit()
    return


@router.get("/jobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    user_id = _user_id(user)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, user_id)
    headers = _auth_header(**creds)

    url = _rest_url(OPUS_SERVICE)  # e.g. /rest/gammapy_maps
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"LAST": "50"})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    if not uid:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, uid)
    headers = _auth_header(**creds)

    url = _rest_url(OPUS_SERVICE, job_id)  # GET /rest/{service}/{job_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)


@router.get("/jobs/{job_id}/results")
async def list_results(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    if not uid:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, uid)
    headers = _auth_header(**creds)

    url = _rest_url(OPUS_SERVICE, job_id, "results")  # GET /rest/{service}/{job_id}/results
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)


@router.post("/jobs", response_model=OpusJobCreateResponse)
async def create_job(
    params: QuickLookParams,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    if not uid:
        raise HTTPException(401, "Not authenticated")

    creds = await _get_creds(db, uid)
    headers = _auth_header(**creds)

    # Form fields for OPUS (gammapy_maps)
    form = {
        "JOBNAME": OPUS_SERVICE,
        "RA": str(params.RA),
        "Dec": str(params.Dec),
        "nxpix": str(params.nxpix),
        "nypix": str(params.nypix),
        "binsz": str(params.binsz),
        # keep your basket ids (not used by OPUS)
        "obs_ids": ",".join(params.obs_ids or []),
    }
    if params.obsids:
        form["obsids"] = params.obsids  # OPUS actually uses this

    # Create job: POST /rest/{service}
    create_url = _rest_url(OPUS_SERVICE)
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        r = await client.post(create_url, data=form, headers=headers)

    if r.status_code not in (200, 201, 303):
        raise HTTPException(r.status_code, r.text)

    # Extract job id/location
    location = r.headers.get("Location") or r.headers.get("location")
    if not location:
        data = _xml_to_json(r.text)
        location = data.get("uws:job", {}).get("uws:jobId") or data.get("uws:jobId")
        if not location:
            raise HTTPException(status_code=502, detail="OPUS did not return job location")

    if location.startswith("http"):
        job_id = location.rstrip("/").split("/")[-1]
        job_url = location
    else:
        job_id = location.strip("/")
        job_url = _rest_url(OPUS_SERVICE, job_id)

    # RUN the job
    run_url = _rest_url(OPUS_SERVICE, job_id, "phase")
    async with httpx.AsyncClient(timeout=30) as client:
        r2 = await client.post(run_url, data={"PHASE": "RUN"}, headers=headers)
    if r2.status_code not in (200, 303):
        raise HTTPException(r2.status_code, f"Created {job_id} but failed to RUN: {r2.text}")

    return OpusJobCreateResponse(job_id=job_id, location=job_url)
