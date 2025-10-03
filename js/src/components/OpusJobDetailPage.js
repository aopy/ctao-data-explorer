import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { jobDetails, jobResults } from "./opusApi";
import { toast } from "react-toastify";

const asArray = (x) => (Array.isArray(x) ? x : x ? [x] : []);
const textify = (v) => (v == null ? "" : String(v));

const TERMINAL = new Set(["COMPLETED", "ABORTED", "ERROR"]);

function errorSummaryToText(e) {
  if (!e) return "";
  if (typeof e === "string" || typeof e === "number") return String(e);
  if (Array.isArray(e)) return e.map(errorSummaryToText).filter(Boolean).join(" ");

  if (typeof e === "object") {
    const type = e["@type"] || e.type;
    const msg = e["uws:message"] || e.message || e["#text"];
    const details = e["uws:details"] || e.details;

    const parts = [];
    if (type) parts.push(`[${type}]`);
    if (msg) parts.push(errorSummaryToText(msg));
    if (details) parts.push(errorSummaryToText(details));

    const out = parts.join(" ").trim();
    return out || "";
  }
  return "";
}

export default function OpusJobDetailPage() {
  const { jobId } = useParams();
  const [jobJson, setJobJson] = useState(null);
  const [resultsJson, setResultsJson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(true);

  // fetchers
  const fetchDetails = useCallback(async () => {
    const j = await jobDetails(jobId);
    setJobJson(j);

    try {
      const id = textify(jobObj["uws:jobId"]) || jobId;
      localStorage.setItem("lastOpusJobId", id);
    } catch {}

    return j;
  }, [jobId]);

  const fetchResults = useCallback(async () => {
    try {
      const r = await jobResults(jobId);
      setResultsJson(r);
    } catch (e) {
    }
  }, [jobId]);

  // polling loop
  useEffect(() => {
    let stop = false;

    const tick = async () => {
      try {
        const j = await fetchDetails();
        const job = j?.["uws:job"] || j || {};
        const ph = (textify(job["uws:phase"]) || "UNKNOWN").toUpperCase();

        // Update results frequently
        await fetchResults();

        if (!TERMINAL.has(ph) && !stop) {
          setTimeout(tick, 2000);
        } else {
          setPolling(false);
        }
      } catch (e) {
        const msg =
          e?.response?.data?.detail ||
          e?.response?.data?.message ||
          e?.message ||
          "Failed to load OPUS job.";
        toast.error(msg);
        setPolling(false);
      } finally {
        setLoading(false);
      }
    };

    tick();
    return () => {
      stop = true;
    };
  }, [fetchDetails, fetchResults]);

  // derived data
  const jobObj = jobJson?.["uws:job"] || jobJson || {};

  const id = textify(jobObj["uws:jobId"]) || jobId;
  const phase = (textify(jobObj["uws:phase"]) || "UNKNOWN").toUpperCase();
  const owner = textify(jobObj["uws:ownerId"]);
  const created = textify(jobObj["uws:creationTime"]);
  const started = textify(jobObj["uws:startTime"]);
  const ended = textify(jobObj["uws:endTime"]);
  const execDur = textify(jobObj["uws:executionDuration"]);
  const destruction = textify(jobObj["uws:destruction"]);
  const errSummary = jobObj["uws:errorSummary"];

  const rawParams = jobObj?.["uws:parameters"]?.["uws:parameter"];
  const params = useMemo(() => {
    return asArray(rawParams).map((p) => ({
      id: p?.["@id"] ?? "",
      value:
        p && typeof p === "object"
          ? Object.prototype.hasOwnProperty.call(p, "#text")
            ? textify(p["#text"])
            : textify(p)
          : textify(p),
    }));
  }, [rawParams]);

  const displayParams = useMemo(() => {
  const filtered = params.filter((p) => String(p.id).toLowerCase() !== "obs_ids");

  const priority = (id) => {
    const idRaw = String(id);
    const idLC = idRaw.toLowerCase();
    if (idRaw === "JOBNAME") return 0;
    if (idLC === "obsids") return 1;
    if (idRaw === "RA") return 2;
    if (idRaw === "Dec") return 3;
    return 10;
  };

  return [...filtered].sort((a, b) => {
    const pa = priority(a.id);
    const pb = priority(b.id);
    if (pa !== pb) return pa - pb;
    return String(a.id).localeCompare(String(b.id), undefined, { sensitivity: "base" });
  });
}, [params]);

  // prefer the dedicated /results payload, fall back to inline
  const inlineResults = jobObj?.["uws:results"]?.["uws:result"];
  const results = useMemo(() => {
    const nodes = resultsJson?.["uws:results"]?.["uws:result"] ?? inlineResults;
    return asArray(nodes).map((x) => ({
      id: x?.["@id"] || "",
      name: x?.["@name"] || "",
      mime: x?.["@mime-type"] || "",
      href: x?.["@xlink:href"] || x?.["@href"] || "",
    }));
  }, [resultsJson, inlineResults]);

  // UI helpers
  const phaseBadgeClass =
    phase === "COMPLETED"
      ? "badge bg-success"
      : phase === "ERROR" || phase === "ABORTED"
      ? "badge bg-danger"
      : "badge bg-warning text-dark";

  return (
    <div className="container mt-3">
      <div className="d-flex align-items-center mb-3">
        <h4 className="mb-0 me-3">OPUS Job #{id}</h4>
        <span className={phaseBadgeClass}>{phase}</span>
        {polling && (
          <span className="ms-2 text-muted small">(updating…)</span>
        )}
        <a className="btn btn-sm btn-outline-secondary ms-auto" href="#/">
          Back to app
        </a>
      </div>

      {/* Summary */}
      <div className="card mb-3">
        <div className="card-header">Summary</div>
        <div className="card-body">
          <div className="row g-2">
            <div className="col-md-4">
              <div><strong>Owner</strong></div>
              <div>{owner || "—"}</div>
            </div>
            <div className="col-md-4">
              <div><strong>Created</strong></div>
              <div>{created || "—"}</div>
            </div>
            <div className="col-md-4">
              <div><strong>Execution (sec)</strong></div>
              <div>{execDur || "—"}</div>
            </div>
            <div className="col-md-4">
              <div className="mt-2"><strong>Started</strong></div>
              <div>{started || "—"}</div>
            </div>
            <div className="col-md-4">
              <div className="mt-2"><strong>Ended</strong></div>
              <div>{ended || "—"}</div>
            </div>
            <div className="col-md-4">
              <div className="mt-2"><strong>Destruction</strong></div>
              <div>{destruction || "—"}</div>
            </div>
          </div>

          {errorSummaryToText(errSummary) && (
            <div className="alert alert-danger mt-3 mb-0">
              <strong>Error summary:</strong>{" "}
              {errorSummaryToText(errSummary)}
            </div>
          )}
        </div>
      </div>

      {/* Parameters */}
      <div className="card mb-3">
        <div className="card-header">Parameters</div>
        <div className="card-body p-0">
          {params.length ? (
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th style={{ width: "30%" }}>Parameter</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {displayParams.map((p, idx) => (
                  <tr key={`${p.id}-${idx}`}>
                    <td><code>{p.id}</code></td>
                    <td>{p.value || "—"}</td>
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
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th style={{ width: "25%" }}>ID</th>
                    <th>Name</th>
                    <th style={{ width: "20%" }}>MIME</th>
                    <th className="text-end text-nowrap" style={{ width: "1%" }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, idx) => (
                    <tr key={`${r.id}-${idx}`}>
                      <td><code>{r.id}</code></td>
                      <td className="text-break">{r.name || "—"}</td>
                      <td><small>{r.mime || "—"}</small></td>
                      <td className="text-end">
                        {r.href ? (
                          <a
                            className="btn btn-sm btn-outline-secondary"
                            href={r.href}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open
                          </a>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-3 text-muted">
              {TERMINAL.has(phase)
                ? "No results were produced."
                : "No results yet — still waiting for the job to complete."}
            </div>
          )}
        </div>
      </div>

      {/* collapsible raw JSON */}
      <div className="card">
        <div className="card-header">Raw job JSON</div>
        <div className="card-body">
          <details>
            <summary className="cursor-pointer">Click to expand</summary>
            <pre className="small bg-light p-2 rounded border mt-2">
              <code>{JSON.stringify(jobJson ?? {}, null, 2)}</code>
            </pre>
          </details>
        </div>
      </div>

      {/* footer back link */}
      <div className="mt-3">
        <Link className="btn btn-outline-secondary" to="/">
          Back to app
        </Link>
      </div>
    </div>
  );
}
