from typing import Optional, List, Dict, Any
import base64
import httpx
import xmltodict
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.responses import Response
from pathlib import Path
import mimetypes
from urllib.parse import urlparse
from .config import get_settings

settings = get_settings()
from .deps import get_current_user
import time
from datetime import datetime, timedelta, timezone
from .metrics import (
    opus_record_submit,
    opus_record_submit_failure,
    opus_observe_submit,
    opus_record_job_outcome_once,
)

router = APIRouter(prefix="/api/opus", tags=["opus"])

# OPUS configuration
_raw_root = settings.OPUS_ROOT.rstrip("/")
OPUS_ROOT = _raw_root[:-5] if _raw_root.endswith("/rest") else _raw_root
OPUS_SERVICE = settings.OPUS_SERVICE.strip("/")
OPUS_APP_TOKEN = settings.OPUS_APP_TOKEN


# helpers
def _rest_url(*parts: str) -> str:
    base = OPUS_ROOT.rstrip("/")
    path = "/".join(str(p).strip("/") for p in parts if p is not None)
    return f"{base}/{path}"


def _xml_to_json(xml_text: str) -> Dict[str, Any]:
    try:
        return xmltodict.parse(xml_text)
    except Exception:
        return {"raw": xml_text}


def _basic_headers(user_id: str) -> Dict[str, str]:
    if not OPUS_APP_TOKEN:
        raise HTTPException(500, "OPUS_APP_TOKEN is not configured on the server")
    token = base64.b64encode(f"{user_id}:{OPUS_APP_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _extract_phase_from_doc(doc: dict) -> str | None:
    j = doc.get("uws:job") or doc.get("job") or doc
    if not isinstance(j, dict):
        return None
    phase = j.get("uws:phase") or j.get("phase")
    if isinstance(phase, dict):
        phase = phase.get("#text")
    return phase


def _extract_job_id_from_doc(doc: dict) -> str | None:
    j = doc.get("uws:job") or doc.get("job") or doc
    if not isinstance(j, dict):
        return None
    jid = j.get("uws:jobId") or j.get("jobId")
    return jid


# Schemas
class QuickLookParams(BaseModel):
    obs_ids: List[str] = []  # not used by OPUS
    RA: float
    Dec: float
    nxpix: int = 400
    nypix: int = 400
    binsz: float = 0.02
    obsids: Optional[str] = None  # space-separated list used by OPUS


class OpusJobCreateResponse(BaseModel):
    job_id: str
    location: str


# Debug
@router.get("/_debug_base")
async def debug_base(user=Depends(get_current_user)):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    return {
        "OPUS_ROOT": OPUS_ROOT,
        "OPUS_SERVICE": OPUS_SERVICE,
        "has_app_token": bool(OPUS_APP_TOKEN),
        "iam_subject_id": uid or None,
    }


# Jobs
@router.get("/jobs")
async def list_jobs(
    request: Request,
    user=Depends(get_current_user),
    days: int = 30,  # how far back to look
):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    headers = _basic_headers(uid)
    headers.update(
        {
            "Accept": "application/xml",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )

    phases = [
        "PENDING",
        "QUEUED",
        "EXECUTING",
        "SUSPENDED",
        "HELD",
        "COMPLETED",
        "ERROR",
        "ABORTED",
        "ARCHIVED",
    ]
    after_dt = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    after_iso = after_dt.strftime("%Y-%m-%dT%H:%M:%S")

    params = [("AFTER", after_iso), ("_ts", str(time.time()))] + [
        ("PHASE", p) for p in phases
    ]

    url = _rest_url("rest", OPUS_SERVICE)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    data = _xml_to_json(r.text)
    redis_client = getattr(request.app.state, "redis", None)

    root = data.get("uws:jobs") or data.get("jobs") or {}
    jobrefs = root.get("uws:jobref") or root.get("jobref") or []
    if isinstance(jobrefs, dict):
        jobrefs = [jobrefs]

    def _phase_of(ref):
        ph = ref.get("uws:phase") or ref.get("phase") or ""
        return ph.get("#text") if isinstance(ph, dict) else ph

    if redis_client:
        for ref in jobrefs:
            if not isinstance(ref, dict):
                continue
            jid = ref.get("uws:jobId") or ref.get("jobId") or ref.get("@id")
            ph = _phase_of(ref)
            if jid and ph:
                await opus_record_job_outcome_once(
                    redis_client,
                    job_id=jid,
                    phase=ph,
                    service=OPUS_SERVICE,
                )
    if data.get("uws:jobs"):
        data["uws:jobs"]["uws:jobref"] = jobrefs
    elif data.get("jobs"):
        data["jobs"]["jobref"] = jobrefs

    return data


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request, user=Depends(get_current_user)):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    headers = _basic_headers(uid)

    url = _rest_url("rest", OPUS_SERVICE, job_id)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    data = _xml_to_json(r.text)

    # Record terminal outcome once (COMPLETED / ERROR / FAILED / ABORTED)
    phase = _extract_phase_from_doc(data) or ""
    await opus_record_job_outcome_once(
        request.app.state.redis,
        job_id=job_id,
        phase=phase,
        service=OPUS_SERVICE,
    )

    return data


@router.get("/jobs/{job_id}/results")
async def list_results(job_id: str, user=Depends(get_current_user)):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    headers = _basic_headers(uid)

    url = _rest_url("rest", OPUS_SERVICE, job_id, "results")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)


@router.post("/jobs", response_model=OpusJobCreateResponse)
async def create_job(params: QuickLookParams, user=Depends(get_current_user)):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    headers = _basic_headers(uid)

    form = {
        "JOBNAME": OPUS_SERVICE,
        "RA": str(params.RA),
        "Dec": str(params.Dec),
        "nxpix": str(params.nxpix),
        "nypix": str(params.nypix),
        "binsz": str(params.binsz),
        "obs_ids": ",".join(params.obs_ids or []),
    }
    if params.obsids:
        form["obsids"] = params.obsids

    create_url = _rest_url("rest", OPUS_SERVICE)
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            r = await client.post(create_url, data=form, headers=headers)

        if r.status_code not in (200, 201, 303):
            dt = time.perf_counter() - t0
            opus_observe_submit(dt, ok=False)
            opus_record_submit_failure()
            raise HTTPException(r.status_code, r.text)

        location = r.headers.get("Location") or r.headers.get("location")
        if not location:
            data = _xml_to_json(r.text)
            location = data.get("uws:job", {}).get("uws:jobId") or data.get("uws:jobId")
            if not location:
                dt = time.perf_counter() - t0
                opus_observe_submit(dt, ok=False)
                opus_record_submit_failure()
                raise HTTPException(502, "OPUS did not return job location")

        if location.startswith("http"):
            job_id = location.rstrip("/").split("/")[-1]
            job_url = location
        else:
            job_id = location.strip("/")
            job_url = _rest_url("rest", OPUS_SERVICE, job_id)

        run_url = _rest_url("rest", OPUS_SERVICE, job_id, "phase")
        async with httpx.AsyncClient(timeout=30) as client:
            r2 = await client.post(run_url, data={"PHASE": "RUN"}, headers=headers)
        if r2.status_code not in (200, 303):
            dt = time.perf_counter() - t0
            opus_observe_submit(dt, ok=False)
            opus_record_submit_failure()
            raise HTTPException(
                r2.status_code, f"Created {job_id} but failed to RUN: {r2.text}"
            )

    except Exception:
        # record failure for any exception path
        if "t0" in locals():
            dt = time.perf_counter() - t0
            opus_observe_submit(dt, ok=False)
        opus_record_submit_failure()
        raise

    # success path: record once after CREATE+RUN finished
    dt = time.perf_counter() - t0
    opus_observe_submit(dt, ok=True)
    opus_record_submit()

    return OpusJobCreateResponse(job_id=job_id, location=job_url)


def _guess_preview_mime(name: str, rid: Optional[str]) -> str:
    rid_l = (rid or "").lower()
    ext = Path(name or "").suffix.lower()
    ctype, _ = mimetypes.guess_type(name or "")
    if rid_l in ("stdout", "stderr") or ext in (
        ".txt",
        ".log",
        ".cfg",
        ".yaml",
        ".yml",
    ):
        return "text/plain; charset=utf-8"
    if rid_l == "provjson" or ext == ".json":
        return "application/json; charset=utf-8"
    if rid_l == "provxml" or ext == ".xml":
        return "text/xml; charset=utf-8"
    if rid_l == "provsvg" or ext == ".svg":
        return "image/svg+xml"
    if ext in (".png", ".jpg", ".jpeg"):
        return ctype or "image/png"
    return ctype or "application/octet-stream"


async def _get_with_auth(url: str, headers: Dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
        return await client.get(url, headers=headers)


@router.get("/jobs/{job_id}/fetch")
async def fetch_by_href(
    request: Request,
    job_id: str,
    href: str = Query(..., description="Absolute xlink:href returned by OPUS"),
    inline: bool = Query(False, description="If true, serve inline"),
    filename: Optional[str] = Query(None, description="Optional filename hint"),
    rid: Optional[str] = Query(
        None, description="OPUS result id, e.g. provjson/stdout/excess_map"
    ),
    user=Depends(get_current_user),
):
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    headers = _basic_headers(uid)

    if not href.startswith(OPUS_ROOT):
        raise HTTPException(400, "Invalid href")

    name_guess = (
        filename or Path(urlparse(href).path).name or f"{job_id}_{rid or 'result'}"
    )
    content_type = _guess_preview_mime(name_guess, rid) if inline else None

    resp = await _get_with_auth(href, headers)
    if resp.status_code == 404 and rid:
        legacy_url = _rest_url("store_old", job_id, rid)
        resp = await _get_with_auth(legacy_url, headers)

        if resp.status_code == 404 and rid.lower() in (
            "stdout",
            "stderr",
            "provjson",
            "provxml",
            "provsvg",
        ):
            special_url = _rest_url("rest", OPUS_SERVICE, job_id, rid.lower())
            resp = await _get_with_auth(special_url, headers)

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    media = (
        content_type or resp.headers.get("content-type") or "application/octet-stream"
    )
    disposition = "inline" if inline else "attachment"
    return Response(
        content=resp.content,
        media_type=media,
        headers={"Content-Disposition": f'{disposition}; filename="{name_guess}"'},
    )
