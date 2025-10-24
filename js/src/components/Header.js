import React, { useEffect } from 'react';
import ctaoLogo from "../assets/ctao-logo.png";

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

    const update = () => {
      const h = headerEl ? Math.ceil(headerEl.getBoundingClientRect().height) : 64;
      document.documentElement.style.setProperty("--app-header-height", `${h}px`);
    };

    update();

    const ro = headerEl && "ResizeObserver" in window ? new ResizeObserver(update) : null;
    if (ro && headerEl) ro.observe(headerEl);

    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      if (ro && headerEl) ro.unobserve(headerEl);
    };
  }, []);
  return (
    <nav className="navbar navbar-expand-lg navbar-light bg-white border-bottom fixed-top shadow-sm app-header">
      <div className="container-fluid">
        {/* Brand: CTAO logo + Data Explorer */}
        <a className="navbar-brand d-flex align-items-center" href="#/">
          <img
            src={ctaoLogo}
            alt="CTAO logo"
            className="me-2 app-header-logo"
          />
          <span className="fw-semibold">Data Explorer</span>
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
                <span className="text-success small me-2">
                  Logged in as{" "}
                  {user.first_name
                    ? `${user.first_name}`
                    : user.email || `User ID: ${user.id}`}
                </span>

                {lastOpus && (
                  <a
                    className="btn btn-outline-info btn-sm"
                    href={`#/opus/jobs/${encodeURIComponent(lastOpus)}`}
                  >
                    Last Preview Job
                  </a>
                )}

                <button
                  className="btn btn-outline-secondary btn-sm"
                  onClick={() => onNavigate("profile")}
                >
                  Profile
                </button>

                <button
                  className="btn btn-outline-danger btn-sm"
                  onClick={onLogout}
                >
                  Logout
                </button>
              </>
            ) : (
              <button
                className="btn btn-outline-primary btn-sm"
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
