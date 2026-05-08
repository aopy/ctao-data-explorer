import React, { useState, useRef, useEffect } from 'react';
import { publicApiClient } from "../apiClients";


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

const DataLinkDropdown = ({ datalink_url, isOpen, onToggle }) => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [openUp, setOpenUp] = useState(false);
  const containerRef = useRef(null);
  const url = normalizeDatalinkPath(datalink_url);
  const [error, setError] = useState(false);

  // When the dropdown becomes open, fetch the VOTable if not already loaded
  // determine if there is enough space below
  useEffect(() => {
    if (isOpen) {
      if (services.length === 0) {
        setError(false);
        setLoading(true);
        publicApiClient
          .get(url, { responseType: 'text' })
          .then((res) => {
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(res.data, "application/xml");
            const tabledata = xmlDoc.getElementsByTagName("TABLEDATA")[0];
            let svc = [];
            if (tabledata) {
              const trElements = tabledata.getElementsByTagName("TR");
              for (let i = 0; i < trElements.length; i++) {
                const tdElements = trElements[i].getElementsByTagName("TD");
                // Expected order: [0]: ID, [1]: access_url, [2]: service_def, [3]: error_message
                if (tdElements[3] && tdElements[3].textContent.trim() === "") {
                  svc.push({
                    label: "Download",
                    access_url: tdElements[1].textContent.trim(),
                  });
                }
              }
            }
            setServices(svc);
          })
          .catch((error) => {
            console.error("Error fetching DataLink services:", error);
            setError(true);
          })
          .finally(() => {
            setLoading(false);
          });
      }
      // Check available space below the dropdown button
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        // If less than 150px, open upward
        setOpenUp(spaceBelow < 150);
      }
    }
  }, [isOpen, url, services.length]);

return (
  <div style={{ position: "relative" }} ref={containerRef}>
    <button
      data-testid="datalink-toggle"
      className="btn btn-ctao-galaxy btn-sm dropdown-toggle"
      onClick={onToggle}
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
              key={index}
              data-testid="datalink-url"
              className="btn btn-sm btn-primary d-block mb-1"
              style={{ whiteSpace: "nowrap" }}
              onClick={() => window.open(service.access_url, "_blank")}
            >
              {service.label}
            </button>
          ))
        )}
      </div>
    )}
  </div>
);
};

export default DataLinkDropdown;
