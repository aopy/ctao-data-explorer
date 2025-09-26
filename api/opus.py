from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session
import httpx, base64, urllib.parse
import xmltodict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field
from .db import encrypt_token as enc_str, decrypt_token as dec_str
from .models import ExternalToken
from .config import get_settings
from .deps import get_db, get_current_user
from .auth import get_required_session_user

router = APIRouter(prefix="/api/opus", tags=["opus"])
settings = get_settings()

OPUS_ROOT = settings.OPUS_ROOT.rstrip("/")
OPUS_SERVICE = settings.OPUS_SERVICE

def _extract_user_id(user: Union[dict, object]) -> Optional[int]:
    if isinstance(user, dict):
        return user.get("id") or user.get("app_user_id") or user.get("user_id")
    return getattr(user, "id", None)

def _auth_header(email: str, token: str) -> Dict[str, str]:
    b = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": f"Basic {b}"}

def _xml_to_json(xml_text: str) -> Dict[str, Any]:
    try:
        return xmltodict.parse(xml_text)
    except Exception:
        return {"raw": xml_text}

def _rest_url(*parts: str) -> str:
    return "/".join([OPUS_ROOT, *[p.strip("/") for p in parts if p is not None]])

async def _get_creds(db: AsyncSession, user_id: int) -> Dict[str, str]:
    row = await db.execute(select(ExternalToken).where(
        ExternalToken.user_id == user_id, ExternalToken.service == "opus"
    ))
    rec: Optional[ExternalToken] = row.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=400, detail="OPUS credentials not set")
    token = dec_str(rec.token_encrypted)
    if not token:
        raise HTTPException(status_code=500, detail="Cannot decrypt OPUS token")
    return {"email": rec.email, "token": token}

# URL helpers
def _svc(path: str) -> str:
    return f"{OPUS_ROOT}/{OPUS_SERVICE}{path}"

def _jobs_qs() -> str:
    return f"{OPUS_ROOT}/jobs?service={urllib.parse.quote(OPUS_SERVICE)}"

def _first_ok(status: int) -> bool:
    return status not in (404, 405)

# Schemas
class OpusCredentialsIn(BaseModel):
    email: str
    token: str

class QuickLookParams(BaseModel):
    job_name: str = "gammapy_maps"
    obs_ids: List[str] = []     # our basket ids
    RA: float
    Dec: float
    nxpix: int = 400
    nypix: int = 400
    binsz: float = 0.02
    obsids: Optional[str] = None  # OPUS obs IDs

class OpusJobCreateResponse(BaseModel):
    job_id: str
    location: str

# Debug
@router.get("/_debug_base")
async def debug_base():
    return {"OPUS_ROOT": OPUS_ROOT, "OPUS_SERVICE": OPUS_SERVICE}

@router.get("/_probe_verbose")
async def probe_verbose(
    db: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    creds = await _get_creds(db, user["app_user_id"] if isinstance(user, dict) else user.id)
    headers = _auth_header(**creds)

    root = settings.OPUS_ROOT.rstrip("/")
    service = settings.OPUS_SERVICE.strip("/")
    urls = [
        ("GET", f"{root}/"),
        ("GET", f"{root}/jobs"),
        ("GET", f"{root}/jobs?service={urllib.parse.quote(service)}"),
        ("GET", f"{root}/{service}/"),
        ("GET", f"{root}/{service}/jobs"),
        ("GET", f"{root}/{service}/jobs/"),
        ("POST", f"{root}/jobs?service={urllib.parse.quote(service)}"),
        ("POST", f"{root}/{service}/jobs"),
        ("POST", f"{root}/{service}/jobs/"),
    ]
    results = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for method, url in urls:
            try:
                if method == "GET":
                    r = await client.get(url, headers=headers)
                else:
                    r = await client.post(url, headers=headers, data={"PING":"1"})
                results.append({
                    "method": method,
                    "url": url,
                    "status": r.status_code,
                    "allow": r.headers.get("Allow"),
                    "content_type": r.headers.get("Content-Type"),
                    "server": r.headers.get("Server"),
                    "location": r.headers.get("Location"),
                    "snippet": (r.text or "")[:200]
                })
            except Exception as e:
                results.append({"method": method, "url": url, "error": str(e)})
    return {"root": root, "service": service, "results": results}

@router.get("/_probe")
async def probe():
    tests = [
        ("GET", f"{OPUS_ROOT}/"),
        ("GET", f"{OPUS_ROOT}/jobs"),
        ("GET", f"{_jobs_qs()}"),
        ("GET", f"{_svc('/')}"),
        ("GET", f"{_svc('/jobs')}"),
        ("GET", f"{_svc('/jobs/')}"),
    ]
    out = []
    async with httpx.AsyncClient(timeout=15) as client:
        for method, url in tests:
            try:
                r = await client.request(method, url)
                out.append({
                    "method": method,
                    "url": url,
                    "status": r.status_code,
                    "allow": r.headers.get("Allow"),
                    "content_type": r.headers.get("Content-Type"),
                })
            except Exception as e:
                out.append({"method": method, "url": url, "error": str(e)})
    return {"root": OPUS_ROOT, "service": OPUS_SERVICE, "results": out}

# Routes
@router.post("/settings", status_code=204)
async def save_settings(
    payload: OpusCredentialsIn,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    row = await db.execute(
        select(ExternalToken).where(
            ExternalToken.user_id == user_id,
            ExternalToken.service == "opus",
        )
    )
    rec = row.scalar_one_or_none()
    if rec:
        rec.email = payload.email
        rec.token_encrypted = enc_str(payload.token)
    else:
        rec = ExternalToken(
            user_id=user_id,
            service="opus",
            email=payload.email,
            token_encrypted=enc_str(payload.token),
        )
        db.add(rec)
    await db.commit()
    return

@router.get("/jobs/{job_id}/fetch")
async def fetch_by_href(
    job_id: str,
    href: str = Query(..., description="Absolute xlink:href returned by OPUS"),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    creds = await _get_creds(db, user_id)
    headers = _auth_header(**creds)

    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.get(href, headers=headers, stream=True)
        if r.status_code >= 400:
            text = await r.aread()
            raise HTTPException(status_code=r.status_code, detail=text.decode("utf-8", "ignore"))
        disp = r.headers.get("Content-Disposition")
        ctype = r.headers.get("Content-Type", "application/octet-stream")
        return StreamingResponse(r.aiter_raw(), media_type=ctype, headers=({"Content-Disposition": disp} if disp else {}))

@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    user_id = _extract_user_id(user)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, user_id)
    headers = _auth_header(**creds)
    url = _rest_url(OPUS_SERVICE)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    user_id = _extract_user_id(user)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, user_id)
    headers = _auth_header(**creds)
    url = _rest_url(OPUS_SERVICE, job_id)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)

@router.get("/jobs/{job_id}/results")
async def list_results(job_id: str, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    user_id = _extract_user_id(user)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    creds = await _get_creds(db, user_id)
    headers = _auth_header(**creds)
    url = _rest_url(OPUS_SERVICE, job_id, "results")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)

@router.get("/jobs/{job_id}/results/{res_id}/content")
async def download_result_content(
    job_id: str,
    res_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_required_session_user),
):
    """Proxy any result (fits/png/txt, or stdout/stderr) via OPUS REST."""
    creds = await _get_creds(db, user["app_user_id"])
    headers = _auth_header(**creds)

    base = settings.OPUS_REST.rstrip("/")
    service = settings.OPUS_SERVICE.strip("/")

    job_url = f"{base}/{service}/{urllib.parse.quote(job_id)}"
    async with httpx.AsyncClient(timeout=30) as client:
        jr = await client.get(job_url, headers=headers)
    if jr.status_code >= 400:
        raise HTTPException(jr.status_code, jr.text)

    job_json = _xml_to_json(jr.text)  # dict
    results = (
        job_json.get("uws:job", {})
                .get("uws:results", {})
                .get("uws:result", [])
    )
    if isinstance(results, dict):
        results = [results]

    entry = next((r for r in results if r.get("@id") == res_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Result '{res_id}' not found")

    href = entry.get("@xlink:href")
    if not href:
        raise HTTPException(status_code=502, detail="Result has no xlink:href")

    async with httpx.AsyncClient(timeout=None) as client:
        rr = await client.get(href, headers=headers, stream=True)
        if rr.status_code >= 400:
            text = await rr.aread()
            raise HTTPException(status_code=rr.status_code, detail=text.decode(errors="replace"))

        cd = rr.headers.get("Content-Disposition")
        ct = rr.headers.get("Content-Type", "application/octet-stream")

        return StreamingResponse(
            rr.aiter_raw(),
            media_type=ct,
            headers=({ "Content-Disposition": cd } if cd else {})
        )

@router.post("/jobs", response_model=OpusJobCreateResponse)
async def create_job(
    params: QuickLookParams,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_required_session_user),
):
    # get OPUS creds for this user
    creds = await _get_creds(db, user["app_user_id"])
    headers = _auth_header(**creds)

    base = settings.OPUS_ROOT.rstrip("/")
    service = settings.OPUS_SERVICE.strip("/")

    # Form fields expected by the OPUS gammapy_maps service
    form = {
        "JOBNAME": params.job_name,
        "RA": str(params.RA),
        "Dec": str(params.Dec),
        "nxpix": str(params.nxpix),
        "nypix": str(params.nypix),
        "binsz": str(params.binsz),
        # keep obs_ids for bookkeeping
        "obs_ids": ",".join(params.obs_ids or []),
    }

    # OPUS reads this:
    if params.obsids:
        form["obsids"] = params.obsids

    # Create job: POST {REST}/{service}
    create_url = f"{base}/{service}"
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        r = await client.post(create_url, data=form, headers=headers)

    if r.status_code not in (200, 201, 303):
        raise HTTPException(r.status_code, r.text)

    location = r.headers.get("Location") or r.headers.get("location")
    if not location:
        data = _xml_to_json(r.text)
        location = (
            data.get("uws:job", {}).get("uws:jobId")
            or data.get("uws:jobId")
        )
        if not location:
            raise HTTPException(status_code=502, detail="OPUS did not return job location")

    if location.startswith("http"):
        job_id = location.rstrip("/").split("/")[-1]
    else:
        job_id = location.strip("/")

    run_url = f"{base}/{service}/{job_id}/phase"
    async with httpx.AsyncClient(timeout=30) as client:
        r2 = await client.post(run_url, data={"PHASE": "RUN"}, headers=headers)
    if r2.status_code not in (200, 303):
        raise HTTPException(r2.status_code, f"Created {job_id} but failed to RUN: {r2.text}")

    return OpusJobCreateResponse(job_id=job_id, location=f"{base}/{service}/{job_id}")
