import React, { useState } from "react";
import { submitQuickLook } from "./opusApi";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

export default function QuickLookModal({ isOpen, onClose, obsIds = [], defaultCenter }) {
  const navigate = useNavigate();
  const [jobName, setJobName] = useState("gammapy_maps");

  // OPUS gammapy_maps params
  const [ra, setRa] = useState(defaultCenter?.lon ?? 83.633);
  const [dec, setDec] = useState(defaultCenter?.lat ?? 22.014);
  const [nxpix, setNxpix] = useState(400);
  const [nypix, setNypix] = useState(400);
  const [binsz, setBinsz] = useState(0.02);

  const [busy, setBusy] = useState(false);

  if (!isOpen) return null;

  const submit = async () => {
  try {
    setBusy(true);

   const obsidsStr = (obsIds || []).map(String).join(" ");

    const payload = {
      job_name: jobName,
      RA: Number(ra),
      Dec: Number(dec),
      nxpix: Number(nxpix),
      nypix: Number(nypix),
      binsz: Number(binsz),
      // keep obs_ids for traceability
      obs_ids: (obsIds || []).map(String),
      obsids: obsidsStr
    };

    const { job_id } = await submitQuickLook(payload);
    localStorage.setItem("lastOpusJobId", job_id);
    navigate(`/opus/jobs/${encodeURIComponent(job_id)}`);
  } catch (e) {
    const msg =
      e?.response?.data?.detail ||
      e?.response?.data?.message ||
      e.message ||
      "Failed to submit Quick-Look job.";
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
      <div
        className="modal show"
        role="dialog"
        aria-modal="true"
        style={{ display: "block", zIndex: 1055 }}
      >
        <div className="modal-dialog modal-lg" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Quick-Look Analysis (gammapy_maps)</h5>
              <button type="button" className="btn-close" onClick={onClose} aria-label="Close" />
            </div>

            <div className="modal-body">
              <p className="mb-3">{obsIds.length} observation(s) selected</p>

              <div className="mb-3">
                <label className="form-label">Job label</label>
                <input
                  className="form-control"
                  value={jobName}
                  onChange={e => setJobName(e.target.value)}
                />
              </div>

              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">RA (deg)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="form-control"
                    value={ra}
                    onChange={e => setRa(e.target.value)}
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label">Dec (deg)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="form-control"
                    value={dec}
                    onChange={e => setDec(e.target.value)}
                  />
                </div>

                <div className="col-md-4">
                  <label className="form-label">nxpix</label>
                  <input
                    type="number"
                    step="1"
                    className="form-control"
                    value={nxpix}
                    onChange={e => setNxpix(e.target.value)}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">nypix</label>
                  <input
                    type="number"
                    step="1"
                    className="form-control"
                    value={nypix}
                    onChange={e => setNypix(e.target.value)}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label">binsz (deg/pixel)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="form-control"
                    value={binsz}
                    onChange={e => setBinsz(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={submit} disabled={busy || !obsIds.length}>
                {busy ? "Sending…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
