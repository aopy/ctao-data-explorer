import React, { useEffect, useMemo, useState } from "react";
import { listJobs } from "./opusApi";

// helpers
function asArray(x) {
  return Array.isArray(x) ? x : x ? [x] : [];
}
function val(x) {
  if (!x) return "";
  if (typeof x === "string") return x;
  if (typeof x === "object" && Object.prototype.hasOwnProperty.call(x, "#text")) {
    return String(x["#text"]);
  }
  return String(x);
}
function badgeClassForPhase(phase) {
  const p = String(phase || "").toUpperCase();
  switch (p) {
    case "COMPLETED": return "bg-success";
    case "ERROR": return "bg-danger";
    case "ABORTED": return "bg-dark";
    case "EXECUTING": return "bg-primary";
    case "QUEUED": return "bg-warning text-dark";
    case "PENDING": return "bg-secondary";
    default: return "bg-secondary";
  }
}

// parse server response into rows: { id, phase, creationTime }
function parseJobs(data) {
  const root = data?.["uws:jobs"] || data?.jobs || data || {};
  let items =
    root["uws:jobref"] ??
    root.jobref ??
    root["uws:job"] ??
    root.job;

  items = asArray(items);

  const rows = items
    .map((it) => {
      const id =
        it?.["@id"] ||
        it?.id ||
        it?.["uws:jobId"] ||
        it?.jobId ||
        "";
      const phase = (val(it?.["uws:phase"] ?? it?.phase ?? "UNKNOWN")).toUpperCase();
      const creationTime = val(it?.["uws:creationTime"] ?? it?.creationTime ?? "");
      return id ? { id: String(id), phase, creationTime } : null;
    })
    .filter(Boolean);

  rows.sort((a, b) => (Date.parse(b.creationTime || 0) || 0) - (Date.parse(a.creationTime || 0) || 0));
  return rows;
}

export default function OpusJobsPage({ isActive }) {
  const [serverJobs, setServerJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [fetched, setFetched] = useState(false);

  // Local fallback (read-only)
  const localJobs = useMemo(() => {
    try {
      const raw = localStorage.getItem("opusJobHistory");
      const arr = raw ? JSON.parse(raw) : [];
      return arr
        .map((j) => ({
          id: j.id,
          phase: (j.phase || "UNKNOWN").toUpperCase(),
          creationTime: j.creationTime || "",
        }))
        .filter((x) => x && x.id);
    } catch {
      return [];
    }
  }, []);

  // prefer server - fallback to local only if server list is empty
  const usingLocal = serverJobs.length === 0 && localJobs.length > 0;
  const rowsToShow = serverJobs.length > 0 ? serverJobs : localJobs;

  const fetchServer = async () => {
    setLoading(true);
    setServerError(null);
    try {
      const data = await listJobs();
      const rows = parseJobs(data);
      setServerJobs(rows);
    } catch (e) {
      const msg =
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e?.message ||
        "Failed to list OPUS jobs.";
      setServerError(msg);
    } finally {
      setLoading(false);
      setFetched(true);
    }
  };

  useEffect(() => {
    if (!isActive) return;
    fetchServer();
  }, [isActive]);

  return (
    <div className="mt-3">
      <div className="d-flex align-items-center mb-2">
        <h5 className="me-auto mb-0">My OPUS Jobs</h5>
        <button
          className="btn btn-sm btn-outline-primary"
          onClick={fetchServer}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {serverError && (
        <div className="alert alert-warning">
          Couldn’t fetch jobs from server: {serverError}
          <br />
          Showing local job history from this browser (if any).
        </div>
      )}

      {usingLocal && (
        <div className="alert alert-secondary py-2">
          Displaying local job history (fallback).
        </div>
      )}

      {!rowsToShow.length && fetched && (
        <div className="alert alert-info">
          No jobs to show yet. Submit a Quick-Look job from your Basket.
        </div>
      )}

      {!!rowsToShow.length && (
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Phase</th>
                <th>Created</th>
                <th className="text-end text-nowrap" style={{ width: "1%" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {rowsToShow.map((row) => (
                <tr key={row.id}>
                  <td><code>{row.id}</code></td>
                  <td>
                    <span className={`badge rounded-pill ${badgeClassForPhase(row.phase)}`}>
                      {row.phase}
                    </span>
                  </td>
                  <td><small>{row.creationTime || "—"}</small></td>
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
