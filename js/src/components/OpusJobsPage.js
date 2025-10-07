import React, { useEffect, useState } from "react";
import { listJobs } from "./opusApi";

// badges for phases
function badgeClassForPhase(phase) {
  switch (String(phase || "").toUpperCase()) {
    case "COMPLETED": return "bg-success";
    case "ERROR":     return "bg-danger";
    case "ABORTED":   return "bg-dark";
    case "EXECUTING": return "bg-primary";
    case "QUEUED":    return "bg-warning text-dark";
    case "PENDING":   return "bg-secondary";
    default:          return "bg-secondary";
  }
}

// helpers
function textify(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object" && Object.prototype.hasOwnProperty.call(v, "#text")) {
    return String(v["#text"]);
  }
  return String(v);
}
function asArray(x) { return Array.isArray(x) ? x : x ? [x] : []; }
function pickLocal(obj, localName) {
  if (!obj || typeof obj !== "object") return undefined;
  for (const k of Object.keys(obj)) {
    const base = k.includes(":") ? k.split(":").pop() : k;
    if (base === localName) return obj[k];
  }
  return undefined;
}

// parse the UWS jobs list (<uws:jobs><uws:jobref .../>...</uws:jobs>)
function parseJobs(doc) {
  const root = doc?.["uws:jobs"] || doc?.jobs || doc || {};
  const items = asArray(root["uws:jobref"] || root.jobref || root["uws:job"] || root.job);

  const rows = items.map((it) => {
    const id =
      it?.["@id"] ||
      pickLocal(it, "id") ||
      it?.["uws:jobId"] ||
      it?.jobId ||
      "";

    const phase = textify(
      pickLocal(it, "phase") || it?.["uws:phase"] || it?.phase || "UNKNOWN"
    ).toUpperCase();

    const created = textify(
      pickLocal(it, "creationTime") || it?.["uws:creationTime"] || it?.creationTime || ""
    );

    return { id: String(id), phase, created };
  }).filter(r => r.id);

  rows.sort((a, b) => Date.parse(b.created || 0) - Date.parse(a.created || 0));
  return rows;
}

export default function OpusJobsPage({ isActive }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [fetched, setFetched] = useState(false);

  const fetchServer = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await listJobs();         // api/opus/jobs?LAST=10
      setJobs(parseJobs(data));
    } catch (e) {
      setErrorMsg(
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e?.message ||
        "Failed to list OPUS jobs."
      );
      setJobs([]); // show empty state on failure
    } finally {
      setLoading(false);
      setFetched(true);
    }
  };

  useEffect(() => {
    if (!isActive) return;
    fetchServer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive]);

  return (
    <div className="mt-3">
      <div className="d-flex align-items-center mb-2">
        <button className="btn btn-sm btn-outline-primary" onClick={fetchServer} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {errorMsg && (
        <div className="alert alert-warning">
          Couldn’t fetch jobs from server: {errorMsg}
        </div>
      )}

      {fetched && jobs.length === 0 && !errorMsg && (
        <div className="alert alert-info">No jobs found.</div>
      )}

      {jobs.length > 0 && (
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Phase</th>
                <th>Created</th>
                <th className="text-end text-nowrap" style={{ width: "1%" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((row) => (
                <tr key={row.id}>
                  <td><code>{row.id}</code></td>
                  <td>
                    <span className={`badge rounded-pill ${badgeClassForPhase(row.phase)}`}>
                      {row.phase}
                    </span>
                  </td>
                  <td><small>{row.created || "—"}</small></td>
                  <td className="text-end">
                    <a
                      className="btn btn-sm btn-outline-secondary"
                      href={`#/opus/jobs/${encodeURIComponent(row.id)}`}
                    >
                      Open
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
