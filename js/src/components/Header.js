import React, { useEffect } from 'react';
import ctaoLogo from "../assets/ctao-logo.svg";

export default function Header({
  isLoggedIn,
  user,
  lastOpus,
  onLogin,
  onLogout,
  onNavigate,
}) {
  useEffect(() => {
    const headerEl = document.querySelector(".app-header");
    const subnavEl = document.querySelector(".subnav");

    const update = () => {
      const h = headerEl ? Math.ceil(headerEl.getBoundingClientRect().height) : 64;
      document.documentElement.style.setProperty("--app-header-height", `${h}px`);
      const s = subnavEl ? Math.ceil(subnavEl.getBoundingClientRect().height) : 52;
      document.documentElement.style.setProperty("--app-subnav-height", `${s}px`);
    };

    update();

    const ro = headerEl && "ResizeObserver" in window ? new ResizeObserver(update) : null;
    if (ro && headerEl) ro.observe(headerEl);
    if (ro && subnavEl) ro.observe(subnavEl);

    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      if (ro && headerEl) ro.unobserve(headerEl);
      if (ro && subnavEl) ro.unobserve(subnavEl);
    };
  }, []);
  return (
    <nav className="navbar navbar-expand-lg fixed-top shadow-sm app-header">
      <div className="container-fluid">
        {/* Brand: CTAO logo + Data Explorer */}
        <a className="navbar-brand d-flex align-items-center ctao-brand" href="#/">
          <img src={ctaoLogo} alt="CTAO logo" className="ctao-brand-logo" />
          <span className="ctao-brand-title">Data Explorer</span>
        </a>

        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#mainNavbar"
          aria-controls="mainNavbar"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        <div className="collapse navbar-collapse" id="mainNavbar">
          <div className="ms-auto d-flex align-items-center gap-2">
            {isLoggedIn && user ? (
              <>
                <span className="navbar-text small me-2">
                  Welcome{" "}
                  {user.first_name
                    ? `${user.first_name}`
                    : user.email || `User ID: ${user.id}`}
                </span>

                {lastOpus && (
                  <a
                    className="btn btn-outline-primary btn-sm"
                    href={`#/opus/jobs/${encodeURIComponent(lastOpus)}`}
                  >
                    Last Preview Job
                  </a>
                )}

                <button
                  className="btn btn-outline-primary btn-sm"
                  onClick={() => onNavigate("profile")}
                >
                  Profile
                </button>

                <button
                  className="btn btn-outline-primary btn-sm"
                  onClick={onLogout}
                >
                  Logout
                </button>
              </>
            ) : (
              <button
                className="btn btn-primary btn-sm"
                type="button"
                onClick={onLogin}
              >
                Login
              </button>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
