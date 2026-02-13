import React, { useState, useEffect } from "react";
import { submitQuickLook, getOpusConfig } from "./opusApi";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

export default function QuickLookModal({ isOpen, onClose, obsIds = [], defaultCenter }) {
  const navigate = useNavigate();

  const [service, setService] = useState("");
  useEffect(() => {
    getOpusConfig()
      .then((cfg) => setService(cfg?.OPUS_SERVICE || ""))
      .catch(() => setService(""));
  }, []);

  // OPUS params
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");
  const [nxpix, setNxpix] = useState(100);
  const [nypix, setNypix] = useState(100);
  const [binsz, setBinsz] = useState(0.02);

  const [busy, setBusy] = useState(false);

  if (!isOpen) return null;

  const submit = async () => {
    try {
      setBusy(true);

      // Validate RA/Dec
      const raNum = parseFloat(String(ra).trim());
      const decNum = parseFloat(String(dec).trim());

      if (!Number.isFinite(raNum) || !Number.isFinite(decNum)) {
        toast.error("Please enter both RA and Dec (in degrees).");
        return;
      }
      if (raNum < 0 || raNum >= 360) {
        toast.error("RA must be in [0, 360).");
        return;
      }
      if (decNum < -90 || decNum > 90) {
        toast.error("Dec must be in [-90, 90].");
        return;
      }

      const obsidsStr = (obsIds || []).map(String).join(" ");

      const payload = {
        RA: raNum,
        Dec: decNum,
        nxpix: Number(nxpix),
        nypix: Number(nypix),
        binsz: Number(binsz),
        // keep obs_ids for traceability
        obs_ids: (obsIds || []).map(String),
        obsids: obsidsStr,
      };

      const { job_id } = await submitQuickLook(payload);
      try {
        localStorage.setItem("lastOpusJobId", job_id);
      } catch {}

      try {
        const entry = {
          id: job_id,
          phase: "PENDING",
          creationTime: new Date().toISOString(),
        };
        const raw = localStorage.getItem("opusJobHistory");
        const arr = raw ? JSON.parse(raw) : [];
        const idx = arr.findIndex((j) => j.id === entry.id);
        if (idx >= 0) arr[idx] = { ...arr[idx], ...entry };
        else arr.push(entry);
        localStorage.setItem("opusJobHistory", JSON.stringify(arr));
      } catch {}

      navigate(`/opus/jobs/${encodeURIComponent(job_id)}`);
    } catch (e) {
      const msg =
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e.message ||
        "Failed to submit Preview Job.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="modal-backdrop fade show" style={{ zIndex: 1050 }} />

      {/* Modal */}
      <div className="modal show" role="dialog" aria-modal="true" style={{ display: "block", zIndex: 1055 }}>
        <div className="modal-dialog modal-lg" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                Preview Job
                {service && (
                  <span className="badge bg-info text-dark ms-2">Service: {service}</span>
                )}
              </h5>
              <button type="button" className="btn-close" onClick={onClose} aria-label="Close" />
            </div>

            <div className="modal-body">
              <p className="mb-3">{obsIds.length} observation(s) selected</p>

              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label" htmlFor="ql-ra">RA (deg)</label>
                  <input
                    id="ql-ra"
                    type="number"
                    step="0.001"
                    className="form-control"
                    placeholder="e.g., 83.633"
                    value={ra}
                    onChange={(e) => setRa(e.target.value)}
                    aria-describedby="ql-ra-help"
                  />
                  <div id="ql-ra-help" className="form-text">Example: 83.633</div>
                </div>

                <div className="col-md-6">
                  <label className="form-label" htmlFor="ql-dec">Dec (deg)</label>
                  <input
                    id="ql-dec"
                    type="number"
                    step="0.001"
                    className="form-control"
                    placeholder="e.g., 22.014"
                    value={dec}
                    onChange={(e) => setDec(e.target.value)}
                    aria-describedby="ql-dec-help"
                  />
                  <div id="ql-dec-help" className="form-text">Example: 22.014</div>
                </div>

                <div className="col-md-4">
                  <label className="form-label" htmlFor="ql-nxpix">nxpix</label>
                  <input
                    id="ql-nxpix"
                    type="number"
                    step="1"
                    className="form-control"
                    value={nxpix}
                    onChange={(e) => setNxpix(e.target.value)}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label" htmlFor="ql-nypix">nypix</label>
                  <input
                    id="ql-nypix"
                    type="number"
                    step="1"
                    className="form-control"
                    value={nypix}
                    onChange={(e) => setNypix(e.target.value)}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label" htmlFor="ql-binsz">binsz</label>
                  <input
                    id="ql-binsz"
                    type="number"
                    step="0.001"
                    className="form-control"
                    value={binsz}
                    onChange={(e) => setBinsz(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={submit}
                disabled={busy || !obsIds.length}
                title={!obsIds.length ? "Select at least one observation" : undefined}
              >
                {busy ? "Sending…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
