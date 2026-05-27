import React, { useState, useRef, useEffect } from 'react';
import { publicApiClient } from "../apiClients";
import { prepareAndDownloadFile } from "./downloadFileWithToken";

function normalizeDatalinkPath(url) {
  if (!url) return url;
  try {
    const u = new URL(url, window.location.origin);
    const p = u.pathname.startsWith("/api/") ? u.pathname.slice(4) : u.pathname;
    return p + (u.search || "");
  } catch {
    return url.startsWith("/api/") ? url.slice(4) : url;
  }
}

const DataLinkDropdown = ({ datalink_url, isOpen, onToggle, isLoggedIn }) => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [downloadingIndex, setDownloadingIndex] = useState(null);
  const [openUp, setOpenUp] = useState(false);
  const [error, setError] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  const containerRef = useRef(null);
  const url = normalizeDatalinkPath(datalink_url);

  useEffect(() => {
    if (isOpen) {
      if (services.length === 0) {
        setError(false);
        setDownloadError(null);
        setLoading(true);

        publicApiClient
          .get(url, { responseType: 'text' })
          .then((res) => {
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(res.data, "application/xml");
            const tabledata = xmlDoc.getElementsByTagName("TABLEDATA")[0];

            const svc = [];
            if (tabledata) {
              const trElements = tabledata.getElementsByTagName("TR");
              for (let i = 0; i < trElements.length; i++) {
                const tdElements = trElements[i].getElementsByTagName("TD");

                // Expected order:
                // [0] ID, [1] access_url, [2] service_def, [3] error_message
                const errorMessage = tdElements[3]?.textContent?.trim();
                const accessUrl = tdElements[1]?.textContent?.trim();

                if (!errorMessage && accessUrl) {
                  svc.push({
                    label: "Download",
                    access_url: accessUrl,
                  });
                }
              }
            }

            setServices(svc);
          })
          .catch((err) => {
            console.error("Error fetching DataLink services:", err);
            setError(true);
          })
          .finally(() => {
            setLoading(false);
          });
      }

      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        setOpenUp(spaceBelow < 150);
      }
    }
  }, [isOpen, url, services.length]);

  const handleDownload = async (service, index) => {
    if (!isLoggedIn) {
      setDownloadError("Please log in to download this file.");
      return;
    }

    setDownloadError(null);
    setDownloadingIndex(index);

    try {
      await prepareAndDownloadFile(service.access_url);
    } catch (err) {
      console.error("Download failed:", err);
      const message =
        err.response?.data?.detail?.message ||
        err.response?.data?.detail?.error ||
        err.message ||
        "Download failed.";
      setDownloadError(message);
    } finally {
      setDownloadingIndex(null);
    }
  };

  return (
    <div style={{ position: "relative" }} ref={containerRef}>
      <button
        data-testid="datalink-toggle"
        className="btn btn-ctao-galaxy btn-sm dropdown-toggle"
        onClick={onToggle}
        type="button"
      >
        DataLink
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: openUp ? "auto" : "100%",
            bottom: openUp ? "100%" : "auto",
            left: 0,
            background: "white",
            border: "1px solid #ccc",
            zIndex: 1000,
            padding: "5px",
            minWidth: "180px",
          }}
        >
          {loading ? (
            <div>Loading...</div>
          ) : error ? (
            <div>Unable to load services.</div>
          ) : services.length === 0 ? (
            <div data-testid="datalink-no-services">No services available</div>
          ) : (
            services.map((service, index) => (
              <button
                key={`${service.access_url}-${index}`}
                data-testid="datalink-url"
                className="btn btn-sm btn-primary d-block mb-1"
                style={{ whiteSpace: "nowrap", width: "100%" }}
                disabled={downloadingIndex !== null}
                onClick={() => handleDownload(service, index)}
                type="button"
              >
                {downloadingIndex === index ? "Preparing…" : service.label}
              </button>
            ))
          )}

          {downloadError && (
            <div className="text-danger small mt-1" style={{ maxWidth: 260 }}>
              {downloadError}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DataLinkDropdown;
