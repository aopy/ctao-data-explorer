import React, { useEffect, useMemo, useState } from "react";
import { listJobs } from "./opusApi";
import { toast } from "react-toastify";

/**
 * parser for xmltodict-like UWS job listings
 * Supported shapes:
 * - { "uws:jobs": { "uws:job": [ { "uws:jobId": "...", "uws:phase": "...", ... }, ... ] } }
 * - { "uws:jobs": { "uws:job-ref": [ { "@id": "...", "@xlink:href": "...", "@phase": "..." }, ... ] } }
 * - { "jobs": [...] } (future-proofing)
 */
function parseJobs(payload) {
  if (!payload) return [];

  // helper to normalize to array
  const toArray = (v) => (Array.isArray(v) ? v : v ? [v] : []);

  if (Array.isArray(payload.jobs)) {
    return payload.jobs.map((j) => ({
      id: j.id || j.jobId || j["uws:jobId"] || j["@id"] || "",
      phase: j.phase || j["uws:phase"] || j["@phase"] || "",
      creationTime:
        j.creationTime || j["uws:creationTime"] || j["@creationTime"] || "",
      startTime: j.startTime || j["uws:startTime"] || "",
      endTime: j.endTime || j["uws:endTime"] || "",
    }));
  }

  const jobsRoot = payload["uws:jobs"];
  if (!jobsRoot) return [];

  const jobNodes = toArray(jobsRoot["uws:job"]);
  if (jobNodes.length) {
    return jobNodes.map((node) => ({
      id:
        node["uws:jobId"] ||
        node["@id"] ||
        (node["@xlink:href"] ? node["@xlink:href"].split("/").pop() : ""),
      phase: node["uws:phase"] || node["@phase"] || "",
      creationTime: node["uws:creationTime"] || "",
      startTime: node["uws:startTime"] || "",
      endTime: node["uws:endTime"] || "",
    }));
  }

  const jobRefs = toArray(jobsRoot["uws:job-ref"] || jobsRoot["uws:jobRef"]);
  if (jobRefs.length) {
    return jobRefs.map((ref) => ({
      id:
        ref["@id"] ||
        (ref["@xlink:href"] ? ref["@xlink:href"].split("/").pop() : ""),
      phase: ref["@phase"] || "",
      creationTime: ref["@creationTime"] || "",
      startTime: "",
      endTime: "",
    }));
  }

  return [];
}

function loadLocalHistory() {
  try {
    const raw = localStorage.getItem("opusJobHistory");
    const arr = raw ? JSON.parse(raw) : [];
    // Deduplicate, newest first
    const seen = new Set();
    const uniq = [];
    for (const j of arr.reverse()) {
      if (!seen.has(j.id)) {
        uniq.push(j);
        seen.add(j.id);
      }
    }
    return uniq;
  } catch {
    return [];
  }
}

export default function OpusJobsPage({ isActive }) {
  const [serverJobs, setServerJobs] = useState([]);
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const localJobs = useMemo(loadLocalHistory, [isActive]); // reload when user comes back

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
      try {
          const raw = localStorage.getItem("opusJobHistory");
          const arr = raw ? JSON.parse(raw) : [];
        } catch {}
      setLoading(false);
      setFetched(true);
    }
  };

  useEffect(() => {
    if (!isActive) return;
    fetchServer();
  }, [isActive]);

  const rowsToShow =
  serverJobs.length > 0 ? serverJobs :
  localJobs.length  > 0 ? localJobs  : [];

  const usingLocal = serverJobs.length === 0 && localJobs.length > 0;
  const showEmpty  = fetched && !serverError && rowsToShow.length === 0;

  return (
    <div className="mt-3">
      <div className="d-flex align-items-center mb-2">
        <h5 className="me-auto mb-0">My OPUS Jobs</h5>
        <button className="btn btn-sm btn-outline-primary" onClick={fetchServer} disabled={loading}>
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
          Displaying local job history.
        </div>
      )}

      {showEmpty && (
        <p className="text-muted">No jobs yet. Submit a Quick-Look job from your Basket.</p>
      )}

      {rowsToShow.length > 0 && (
        <div className="table-responsive">
          <table className="table table-sm table-hover align-middle">
            <thead>
              <tr>
                <th style={{ width: 160 }}>Job ID</th>
                <th style={{ width: 120 }}>Phase</th>
                <th>Created</th>
                <th>Started</th>
                <th>Ended</th>
                <th style={{ width: 120 }}></th>
              </tr>
            </thead>
            <tbody>
              {rowsToShow.map((j) => {
                const id = j.id || "";
                const phase = j.phase || "";
                return (
                  <tr key={id}>
                    <td><code>{id}</code></td>
                    <td>
                      <span
                        className={
                          "badge " +
                          (phase === "COMPLETED"
                            ? "bg-success"
                            : phase === "ERROR"
                            ? "bg-danger"
                            : phase === "EXECUTING"
                            ? "bg-warning text-dark"
                            : "bg-secondary")
                        }
                      >
                        {phase || "UNKNOWN"}
                      </span>
                    </td>
                    <td>{j.creationTime || ""}</td>
                    <td>{j.startTime || ""}</td>
                    <td>{j.endTime || ""}</td>
                    <td className="text-end">
                      <a
                        className="btn btn-sm btn-outline-primary"
                        href={`#/opus/jobs/${encodeURIComponent(id)}`}
                      >
                        Open
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
