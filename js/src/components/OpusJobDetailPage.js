import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { jobDetails, jobResults } from "./opusApi";
import { toast } from "react-toastify";

function textify(v) {
  if (v == null) return "";
  const t = typeof v;
  if (t === "string" || t === "number" || t === "boolean") return String(v);
  if (Array.isArray(v)) return v.map(textify).join(", ");
  // xmltodict-style markers
  if (v && typeof v === "object") {
    if (Object.prototype.hasOwnProperty.call(v, "#text")) return textify(v["#text"]);
    if (Object.prototype.hasOwnProperty.call(v, "@xsi:nil")) return "";
    try { return JSON.stringify(v); } catch { return String(v); }
  }
  return String(v);
}

function asArray(x) {
  return Array.isArray(x) ? x : x ? [x] : [];
}

export default function OpusJobDetailPage() {
  const { jobId } = useParams();
  const [jobJson, setJobJson] = useState(null);
  const [resJson, setResJson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  // Keep a quick link to last job
  useEffect(() => {
    if (jobId) localStorage.setItem("lastOpusJobId", jobId);
  }, [jobId]);

  async function loadAll(silent = false) {
    try {
      if (!silent) setLoading(true);
      const [j, r] = await Promise.all([jobDetails(jobId), jobResults(jobId)]);
      setJobJson(j);
      setResJson(r);
    } catch (e) {
      const msg = e?.message || "Failed to load OPUS job.";
      toast.error(msg);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => { loadAll(); /* on mount / jobId change */ }, [jobId]);

  // Extract commonly used parts
  const jobObj = jobJson?.["uws:job"] || jobJson || {};
  const phase = (textify(jobObj["uws:phase"]) || "UNKNOWN").toUpperCase();
  const owner = textify(jobObj["uws:ownerId"]);
  const created = textify(jobObj["uws:creationTime"]);
  const started = textify(jobObj["uws:startTime"]);
  const ended = textify(jobObj["uws:endTime"]);
  const execDur = textify(jobObj["uws:executionDuration"]);
  const destruction = textify(jobObj["uws:destruction"]);

  useEffect(() => {
      if (!jobJson) return;
      try {
        const job = jobJson["uws:job"] || jobJson.job || {};
        const id =
          job["uws:jobId"] || job.jobId || job["@id"] || jobId; // fallback to route param
        const phaseText = (job["uws:phase"] || job.phase || "UNKNOWN").toString();
        const creationTime = (job["uws:creationTime"] || job.creationTime || "").toString();
        const startTime = (job["uws:startTime"] || job.startTime || "").toString();
        const endTime = (job["uws:endTime"] || job.endTime || "").toString();

        const raw = localStorage.getItem("opusJobHistory");
        const arr = raw ? JSON.parse(raw) : [];
        const idx = arr.findIndex((j) => j.id === id);
        const entry = { id, phase: phaseText, creationTime, startTime, endTime };

        if (idx >= 0) arr[idx] = { ...arr[idx], ...entry };
        else arr.push(entry);

        localStorage.setItem("opusJobHistory", JSON.stringify(arr));
        localStorage.setItem("lastOpusJobId", id);
      } catch {
        // ignore localStorage errors
      }
    }, [jobJson, jobId]);

  const rawParams = jobObj?.["uws:parameters"]?.["uws:parameter"];
  const params = useMemo(() => {
    return asArray(rawParams).map((p) => ({
      id: p?.["@id"] ?? "",
      byRef: p?.["@byReference"],
      value:
        p && typeof p === "object"
          ? (Object.prototype.hasOwnProperty.call(p, "#text") ? textify(p["#text"]) : textify(p))
          : textify(p),
    }));
  }, [rawParams]);

  // Results can be absent until job runs/completes
  const rawResults = (jobObj?.["uws:results"] || resJson)?.["uws:result"];
  const results = useMemo(() => {
    return asArray(rawResults).map((r) => ({
      id: r?.["@id"] ?? "",
      href: r?.["@xlink:href"] ?? "",
      mime: r?.["@mime-type"] ?? "",
      name: r?.["@name"] ?? "",
      hash: r?.["@hash"] ?? "",
    }));
  }, [rawResults]);

  useEffect(() => {
    const terminal = new Set(["COMPLETED", "ERROR", "ABORTED"]);
    if (!terminal.has(phase)) {
      setPolling(true);
      const t = setInterval(() => loadAll(true), 4000);
      return () => {
        clearInterval(t);
        setPolling(false);
      };
    } else {
      setPolling(false);
    }
  }, [phase]);

  if (loading && !jobJson) {
    return (
      <div className="container py-4">
        <h4>OPUS Job #{jobId}</h4>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="container py-4">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h4 className="mb-0">OPUS Job #{jobId}</h4>
        <div>
          <Link to="/" className="btn btn-sm btn-outline-secondary me-2">Back to app</Link>
          <button className="btn btn-sm btn-outline-primary" onClick={() => loadAll()}>
            Refresh
            {polling ? " (auto)" : ""}
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="card mb-3">
        <div className="card-header">Summary</div>
        <div className="card-body">
          <dl className="row mb-0">
            <dt className="col-sm-3">Phase</dt>
            <dd className="col-sm-9">
              <span className={
                "badge " +
                (phase === "COMPLETED" ? "bg-success" :
                 phase === "ERROR" ? "bg-danger" :
                 phase === "ABORTED" ? "bg-warning text-dark" :
                 "bg-secondary")
              }>
                {phase}
              </span>
            </dd>

            <dt className="col-sm-3">Owner</dt>
            <dd className="col-sm-9">{owner || "—"}</dd>

            <dt className="col-sm-3">Created</dt>
            <dd className="col-sm-9">{created || "—"}</dd>

            <dt className="col-sm-3">Started</dt>
            <dd className="col-sm-9">{started || "—"}</dd>

            <dt className="col-sm-3">Ended</dt>
            <dd className="col-sm-9">{ended || "—"}</dd>

            <dt className="col-sm-3">Exec. Duration (s)</dt>
            <dd className="col-sm-9">{execDur || "—"}</dd>

            <dt className="col-sm-3">Destruction</dt>
            <dd className="col-sm-9">{destruction || "—"}</dd>
          </dl>
        </div>
      </div>

      {/* Parameters */}
      <div className="card mb-3">
        <div className="card-header">Parameters</div>
        <div className="card-body p-0">
          {params.length ? (
            <div className="table-responsive">
              <table className="table table-sm mb-0">
                <thead>
                  <tr>
                    <th style={{width: 240}}>Name</th>
                    <th>Value</th>
                    <th style={{width: 120}}>byReference</th>
                  </tr>
                </thead>
                <tbody>
                  {params.map((p, idx) => (
                    <tr key={`${p.id}-${idx}`}>
                      <td><code>{p.id || "(unnamed)"}</code></td>
                      <td style={{whiteSpace: "pre-wrap"}}>{p.value || "—"}</td>
                      <td>{p.byRef ?? "0"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-3 text-muted">No structured parameters available.</div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="card mb-3">
        <div className="card-header">Results</div>
        <div className="card-body p-0">
          {results.length ? (
            <div className="table-responsive">
              <table className="table table-sm">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>MIME</th>
                      <th className="text-end text-nowrap" style={{ width: '1%' }}>Actions</th>
                    </tr>
                  </thead>

                  <tbody>
                    {results.map((r, idx) => (
                      <tr key={`${r.id}-${idx}`}>
                        <td><code>{r.id}</code></td>
                        <td>{r.name || "—"}</td>
                        <td><small>{r.mime || "—"}</small></td>
                        <td className="text-end text-nowrap" style={{ width: '1%' }}>
                          {r.href ? (
                            <a
                              className="btn btn-sm btn-outline-secondary"
                              href={r.href}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open
                            </a>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          ) : (
            <div className="p-3 text-muted">
              {phase === "COMPLETED"
                ? "No results were published by OPUS."
                : "No results yet — still waiting for the job to complete."}
            </div>
          )}
        </div>
      </div>

      {/* Raw JSON (for debugging) */}
      <div className="card">
        <div className="card-header">Raw job JSON</div>
        <div className="card-body">
          <pre className="mb-0" style={{whiteSpace: "pre-wrap"}}>
            {JSON.stringify(jobJson, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
