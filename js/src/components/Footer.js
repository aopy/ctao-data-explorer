import React from "react";

export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="app-footer mt-auto">
      <div className="container-fluid py-3 d-flex flex-column flex-md-row align-items-center justify-content-between gap-2">
        <div className="app-footer-text small">
          {year} All Rights Reserved
        </div>

        <nav className="d-flex gap-3">
          <a className="app-footer-link" href="#/privacy">Data Privacy</a>
          <a className="app-footer-link" href="#/imprint">Imprint</a>
          <a className="app-footer-link" href="#/support">Support</a>
        </nav>
      </div>
    </footer>
  );
}
