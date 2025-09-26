import React, { useState } from "react";
import { saveOpusSettings } from "./opusApi";
import { toast } from "react-toastify";

export default function OpusSettingsModal({ buttonClassName = "btn btn-sm btn-outline-secondary ms-2" }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await saveOpusSettings(email.trim(), token.trim());
      toast.success("OPUS credentials saved.");
      setOpen(false);
      setEmail("");
      setToken("");
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        "Failed to save OPUS credentials.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button className={buttonClassName} onClick={() => setOpen(true)}>
        OPUS Settings
      </button>

      {open && (
        <div className="modal show" style={{ display: "block" }} role="dialog" aria-modal="true">
          <div className="modal-dialog" role="document">
            <div className="modal-content">
              <form onSubmit={onSubmit}>
                <div className="modal-header">
                  <h5 className="modal-title">OPUS Settings</h5>
                  <button
                    type="button"
                    className="btn-close"
                    aria-label="Close"
                    onClick={() => setOpen(false)}
                    disabled={busy}
                  />
                </div>

                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Email</label>
                    <input
                      type="email"
                      className="form-control"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                    />
                  </div>

                  <div className="mb-3">
                    <label className="form-label">Token</label>
                    <input
                      type="text"
                      className="form-control"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="xxxxxxxx-xxxx-...."
                      autoComplete="off"
                      required
                    />
                    <div className="form-text">
                      Your token will be stored encrypted on the server.
                    </div>
                  </div>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)} disabled={busy}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={busy || !email || !token}>
                    {busy ? "Saving…" : "Save"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
