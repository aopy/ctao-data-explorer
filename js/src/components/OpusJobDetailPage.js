import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { jobDetails, jobResults } from "./opusApi";
import { toast } from "react-toastify";

const asArray = (x) => (Array.isArray(x) ? x : x ? [x] : []);

function textify(v) {
  if (v == null) return "";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  if (typeof v === "object") {
    if (Object.prototype.hasOwnProperty.call(v, "#text")) return String(v["#text"] ?? "");
    if (Object.prototype.hasOwnProperty.call(v, "_")) return String(v["_"] ?? "");
    if (Object.prototype.hasOwnProperty.call(v, "value")) return String(v.value ?? "");
  }

  return "";
}

const TERMINAL = new Set(["COMPLETED", "ABORTED", "ERROR"]);

function previewKind(res) {
  const name = (res.name || "").toLowerCase();
  const id   = (res.id || "").toLowerCase();
  const href = (res.href || "").toLowerCase();
  const mime = (res.mime || "").toLowerCase();

  // images
  if (
    mime.startsWith("image/") ||
    /\.(png|jpe?g|gif|svg)$/i.test(name || href) ||
    id === "provsvg"
  ) return "image";

  // text-like
  if (
    id === "stdout" || id === "stderr" ||
    mime.startsWith("text/") ||
    /(json|xml|yaml|yml|csv|ecsv)/.test(mime) ||
    /\.(txt|log|json|xml|ya?ml|cfg|csv|ecsv)$/i.test(name || href) ||
    id === "provjson" || id === "provxml"
  ) return "text";

  // unknowns (e.g., FITS) - download only
  return null;
}

function guessDownloadName(jobId, r) {
  if (r.name) return r.name;
  const id = (r.id || "").toLowerCase();
  if (id === "provjson") return `${jobId}_provenance.json`;
  if (id === "provxml")  return `${jobId}_provenance.xml`;
  if (id === "provsvg")  return `${jobId}_provenance.svg`;
  if (id === "stdout")   return `${jobId}_stdout.log`;
  if (id === "stderr")   return `${jobId}_stderr.log`;
  return id || "download.bin";
}

function opusProxy(jobId, href, { inline = false, filename, id } = {}) {
  const q = new URLSearchParams({ href });
  if (inline) q.set("inline", "1");
  if (filename) q.set("filename", filename);
  if (id) q.set("rid", id);
  return `/api/opus/jobs/${encodeURIComponent(jobId)}/fetch?${q.toString()}`;
}

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
  const [openPreview, setOpenPreview] = useState({});

  // fetchers
  const fetchDetails = useCallback(async () => {
    const j = await jobDetails(jobId);
    setJobJson(j);

    try {
      const job = j?.["uws:job"] || j || {};
      const idFromPayload = textify(job["uws:jobId"]) || jobId;
      localStorage.setItem("lastOpusJobId", idFromPayload);
    } catch {}

    return j;
  }, [jobId]);

  const fetchResults = useCallback(async () => {
    try {
      const r = await jobResults(jobId);
      setResultsJson(r);
    } catch {
      // ignore transient errors
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
          "Failed to load job.";
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
        <h4 className="mb-0 me-3">Job #{id}</h4>
        <span className={phaseBadgeClass}>{phase}</span>
        {loading && (
          <span className="ms-2 text-muted small">
            <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
            Loading…
          </span>
        )}
        {!loading && polling && (
          <span className="ms-2 text-muted small">(updating…)</span>
        )}
        <Link className="btn btn-sm btn-outline-secondary ms-auto" to="/opus">
          Back to job list
        </Link>
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
        <div className="card-body">
          {loading ? (
            <p className="text-muted mb-0">Loading results…</p>
          ) : results.length === 0 ? (
            <p className="text-muted mb-0">No results yet.</p>
          ) : (
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th>Result ID</th>
                    <th>Name</th>
                    <th>Mime</th>
                    <th className="text-end text-nowrap" style={{ width: "1%" }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, idx) => {
                    const rid = r.id || `idx-${idx}`;
                    const kind = previewKind(r);
                    const isOpen = !!openPreview[rid];

                    const downloadName = guessDownloadName(jobId, r);
                    const downloadUrl = r.href
                      ? opusProxy(jobId, r.href, { inline: false, filename: downloadName, id: rid })
                      : null;
                    const previewUrl = r.href
                      ? opusProxy(jobId, r.href, { inline: true, filename: downloadName, id: rid })
                      : null;

                    return (
                      <React.Fragment key={rid}>
                        <tr>
                          <td><code>{r.id || "—"}</code></td>
                          <td>{r.name || "—"}</td>
                          <td><small>{r.mime || "—"}</small></td>
                          <td className="text-end text-nowrap py-1">
                            <div className="btn-group btn-group-sm" role="group" aria-label={`${rid} actions`}>
                              {downloadUrl && (
                                <a className="btn btn-outline-secondary" href={downloadUrl} download={downloadName}>
                                  Download
                                </a>
                              )}
                              {kind && previewUrl && (
                                <button
                                  type="button"
                                  className={`btn btn-outline-primary ${isOpen ? "active" : ""}`}
                                  onClick={() => setOpenPreview((s) => ({ ...s, [rid]: !s[rid] }))}
                                >
                                  {isOpen ? "Hide preview" : "Show preview"}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>

                        {isOpen && kind && previewUrl && (
                          <tr className="bg-light">
                            <td colSpan={4}>
                              {kind === "image" ? (
                                <div className="p-2">
                                  <img src={previewUrl} alt={r.name || rid} style={{ maxWidth: "100%", height: "auto" }} />
                                </div>
                              ) : (
                                <div className="p-2">
                                  <iframe
                                    title={`preview-${rid}`}
                                    src={previewUrl}
                                    style={{
                                      width: "100%",
                                      height: 420,
                                      border: "1px solid #ddd",
                                      borderRadius: 6,
                                      background: "#fff",
                                    }}
                                  />
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            )}
        </div>
      </div>
    </div>
  );
}
