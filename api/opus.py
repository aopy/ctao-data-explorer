import base64
import mimetypes
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import httpx
import xmltodict
from ctao_shared.config import get_settings
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

from .deps import get_current_user_with_iam_sub
from .metrics import (
    opus_observe_submit,
    opus_record_job_outcome_once,
    opus_record_submit_failure,
)

settings = get_settings()

router = APIRouter(prefix="/api/opus", tags=["opus"])

# OPUS configuration
_raw_root = settings.OPUS_ROOT.rstrip("/")
OPUS_BASE = _raw_root[:-5] if _raw_root.endswith("/rest") else _raw_root
OPUS_REST_BASE = f"{OPUS_BASE}/rest"

OPUS_ROOT = OPUS_BASE

_raw_service = settings.OPUS_SERVICE.strip()
if _raw_service.lower().startswith("http"):
    OPUS_SERVICE_URL = _raw_service.rstrip("/")
    OPUS_SERVICE_NAME = OPUS_SERVICE_URL.rsplit("/", 1)[-1]
else:
    OPUS_SERVICE_NAME = _raw_service.strip("/")
    OPUS_SERVICE_URL = f"{OPUS_REST_BASE}/{OPUS_SERVICE_NAME}"

OPUS_APP_TOKEN = settings.OPUS_APP_TOKEN

try:
    _host_netloc = urlparse(OPUS_BASE).netloc
except Exception:
    _host_netloc = ""
try:
    _svc_netloc = urlparse(OPUS_SERVICE_URL).netloc
except Exception:
    _svc_netloc = ""
OPUS_ALLOWED_NETLOCS: set[str] = {n for n in {_host_netloc, _svc_netloc} if n}


# helpers
def _rest_url(*parts: str) -> str:
    """Join parts under the REST root (legacy endpoints)."""
    base = OPUS_REST_BASE.rstrip("/")
    path = "/".join(str(p).strip("/") for p in parts if p is not None)
    return f"{base}/{path}"


def _service_url(*parts: str) -> str:
    base = OPUS_SERVICE_URL.rstrip("/")
    path = "/".join(str(p).strip("/") for p in parts if p is not None)
    return f"{base}/{path}" if path else base


def _xml_to_json(xml_text: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], xmltodict.parse(xml_text))
    except Exception:
        return {"raw": xml_text}


def _basic_headers(user_id: str) -> dict[str, str]:
    if not OPUS_APP_TOKEN:
        raise HTTPException(500, "OPUS_APP_TOKEN is not configured on the server")
    token = base64.b64encode(f"{user_id}:{OPUS_APP_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _extract_phase_from_doc(doc: dict[str, Any]) -> str | None:
    j = doc.get("uws:job") or doc.get("job") or doc
    if not isinstance(j, dict):
        return None
    phase: Any = j.get("uws:phase") or j.get("phase")
    if isinstance(phase, dict):
        phase = phase.get("#text")
    return cast(str | None, phase)


def _extract_job_id_from_doc(doc: dict[str, Any]) -> str | None:
    j = doc.get("uws:job") or doc.get("job") or doc
    if not isinstance(j, dict):
        return None
    jid = j.get("uws:jobId") or j.get("jobId")
    return cast(str | None, jid)


def _extract_uid(user: Any) -> str:
    """Get IAM subject id from `user` or raise 401."""
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    if not uid:
        raise HTTPException(401, "Not authenticated")
    return str(uid)


def _build_job_form(params: "QuickLookParams") -> dict[str, str]:
    """Serialize QuickLookParams to the OPUS job form."""
    form: dict[str, str] = {
        "JOBNAME": OPUS_SERVICE_NAME,
        "RA": str(params.RA),
        "Dec": str(params.Dec),
        "nxpix": str(params.nxpix),
        "nypix": str(params.nypix),
        "binsz": str(params.binsz),
        "obs_ids": ",".join(params.obs_ids or []),
    }
    if params.obsids:
        form["obsids"] = params.obsids
    return form


async def _opus_create_job(form: dict[str, str], headers: dict[str, str]) -> tuple[str, str]:
    """POST create and return (job_id, job_url)."""
    create_url = _service_url()
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        r = await client.post(create_url, data=form, headers=headers)

    if r.status_code not in (200, 201, 303):
        raise HTTPException(r.status_code, r.text)

    location = r.headers.get("Location") or r.headers.get("location")
    if not location:
        data = _xml_to_json(r.text)
        location = data.get("uws:job", {}).get("uws:jobId") or data.get("uws:jobId")

    if not location:
        raise HTTPException(502, "OPUS did not return job location")

    if location.startswith("http"):
        job_id = location.rstrip("/").split("/")[-1]
        job_url = location
    else:
        job_id = location.strip("/")
        job_url = _service_url(job_id)

    return job_id, job_url


async def _opus_run_job(job_id: str, headers: dict[str, str]) -> None:
    """Transition job to RUN."""
    run_url = _service_url(job_id, "phase")
    async with httpx.AsyncClient(timeout=30) as client:
        r2 = await client.post(run_url, data={"PHASE": "RUN"}, headers=headers)

    if r2.status_code not in (200, 303):
        raise HTTPException(r2.status_code, f"Created {job_id} but failed to RUN: {r2.text}")


# Schemas
class QuickLookParams(BaseModel):
    obs_ids: list[str] = Field(default_factory=list)  # not used by OPUS
    RA: float
    Dec: float
    nxpix: int = 400
    nypix: int = 400
    binsz: float = 0.02
    obsids: str | None = None  # space-separated list used by OPUS


class OpusJobCreateResponse(BaseModel):
    job_id: str
    location: str


# Debug
@router.get("/_debug_base")
async def debug_base(user: Any = Depends(get_current_user_with_iam_sub)) -> dict[str, Any]:
    uid = (
        getattr(user, "iam_subject_id", None)
        if not isinstance(user, dict)
        else user.get("iam_subject_id")
    )
    return {
        "OPUS_BASE": OPUS_BASE,
        "OPUS_REST_BASE": OPUS_REST_BASE,
        "OPUS_SERVICE_URL": OPUS_SERVICE_URL,
        "OPUS_SERVICE_NAME": OPUS_SERVICE_NAME,
        "has_app_token": bool(OPUS_APP_TOKEN),
        "iam_subject_id": uid or None,
    }


# Jobs
@router.get("/jobs")
async def list_jobs(
    request: Request,
    user: Any = Depends(get_current_user_with_iam_sub),
    days: int = 30,  # how far back to look
) -> dict[str, Any]:
    uid = user.iam_subject_id
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
    after_dt = datetime.now(UTC) - timedelta(days=max(1, days))
    after_iso = after_dt.strftime("%Y-%m-%dT%H:%M:%S")

    params: list[tuple[str, str | int | float | bool | None]] = [
        ("AFTER", after_iso),
        ("_ts", str(time.time())),
    ]
    params.extend([("PHASE", p) for p in phases])

    url = _service_url()
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

    def _phase_of(ref: dict[str, Any]) -> str:
        ph = ref.get("uws:phase") or ref.get("phase") or ""
        if isinstance(ph, dict):
            ph = ph.get("#text") or ""
        return str(ph)

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
                    service=OPUS_SERVICE_NAME,
                )
    if data.get("uws:jobs"):
        data["uws:jobs"]["uws:jobref"] = jobrefs
    elif data.get("jobs"):
        data["jobs"]["jobref"] = jobrefs

    return data


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str, request: Request, user: Any = Depends(get_current_user_with_iam_sub)
) -> dict[str, Any]:
    uid = user.iam_subject_id
    headers = _basic_headers(uid)

    url = _service_url(job_id)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    data = _xml_to_json(r.text)

    # Record terminal outcome once (COMPLETED / ERROR / FAILED / ABORTED)
    phase = _extract_phase_from_doc(data) or ""
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        await opus_record_job_outcome_once(
            redis_client, job_id=job_id, phase=phase, service=OPUS_SERVICE_NAME
        )

    return data


@router.get("/jobs/{job_id}/results")
async def list_results(
    job_id: str, user: Any = Depends(get_current_user_with_iam_sub)
) -> dict[str, Any]:
    uid = user.iam_subject_id
    headers = _basic_headers(uid)

    url = _service_url(job_id, "results")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return _xml_to_json(r.text)


@router.post("/jobs", response_model=OpusJobCreateResponse)
async def create_job(
    params: QuickLookParams,
    user: Any = Depends(get_current_user_with_iam_sub),
) -> OpusJobCreateResponse:
    uid = _extract_uid(user)
    headers = _basic_headers(uid)
    form = _build_job_form(params)

    t0 = time.perf_counter()
    try:
        job_id, job_url = await _opus_create_job(form, headers)
        await _opus_run_job(job_id, headers)
        opus_observe_submit(time.perf_counter() - t0, ok=True)
        return OpusJobCreateResponse(
            job_id=job_id,
            location=job_url,
        )
    except HTTPException:
        opus_observe_submit(time.perf_counter() - t0, ok=False)
        opus_record_submit_failure()
        raise
    except Exception as e:
        opus_observe_submit(time.perf_counter() - t0, ok=False)
        opus_record_submit_failure()
        raise HTTPException(502, str(e)) from e


def _guess_preview_mime(name: str, rid: str | None) -> str:
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


async def _get_with_auth(url: str, headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
        resp = await client.get(url, headers=headers)
        if 300 <= resp.status_code < 400:
            loc = resp.headers.get("Location") or resp.headers.get("location")
            if not loc:
                return resp
            p = urlparse(loc)
            if p.netloc not in OPUS_ALLOWED_NETLOCS:
                raise HTTPException(400, "Redirect to disallowed host")
            return await client.get(loc, headers=headers)
        return resp


@router.get("/jobs/{job_id}/fetch")
async def fetch_by_href(
    request: Request,
    job_id: str,
    href: str = Query(..., description="Absolute xlink:href returned by OPUS"),
    inline: bool = Query(False, description="If true, serve inline"),
    filename: str | None = Query(None, description="Optional filename hint"),
    rid: str | None = Query(None, description="OPUS result id, e.g. provjson/stdout/excess_map"),
    user: Any = Depends(get_current_user_with_iam_sub),
) -> Response:
    _ = request
    uid = user.iam_subject_id
    headers = _basic_headers(uid)

    parsed = urlparse(href)
    if parsed.netloc not in OPUS_ALLOWED_NETLOCS:
        raise HTTPException(400, "Invalid href")

    name_guess = filename or Path(urlparse(href).path).name or f"{job_id}_{rid or 'result'}"
    content_type = _guess_preview_mime(name_guess, rid) if inline else None

    resp = await _get_with_auth(href, headers)
    if resp.status_code == 404 and rid:
        # legacy location
        legacy_url = _rest_url("store_old", job_id, rid)
        resp = await _get_with_auth(legacy_url, headers)

        # special endpoints under service root
        if resp.status_code == 404 and rid.lower() in (
            "stdout",
            "stderr",
            "provjson",
            "provxml",
            "provsvg",
        ):
            special_url = _service_url(job_id, rid.lower())
            resp = await _get_with_auth(special_url, headers)

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    media = content_type or resp.headers.get("content-type") or "application/octet-stream"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=resp.content,
        media_type=media,
        headers={"Content-Disposition": f'{disposition}; filename="{name_guess}"'},
    )
