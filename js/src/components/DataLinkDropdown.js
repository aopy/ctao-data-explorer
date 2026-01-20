import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const DataLinkDropdown = ({ datalink_url, isOpen, onToggle }) => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [openUp, setOpenUp] = useState(false);
  const containerRef = useRef(null);

  // When the dropdown becomes open, fetch the VOTable if not already loaded
  // determine if there is enough space below
  useEffect(() => {
    if (isOpen) {
      if (services.length === 0) {
        setLoading(true);
        axios
          .get(datalink_url, { responseType: 'text' })
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
  }, [isOpen, datalink_url, services.length]);

  return (
    <div style={{ position: 'relative' }} ref={containerRef}>
      <button className="btn btn-ctao-galaxy btn-sm dropdown-toggle" onClick={onToggle}>
        DataLink
      </button>
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: openUp ? 'auto' : '100%',
            bottom: openUp ? '100%' : 'auto',
            left: 0,
            background: 'white',
            border: '1px solid #ccc',
            zIndex: 1000,
            padding: '5px'
          }}
        >
          {loading && <div>Loading...</div>}
          {(!loading && services.length === 0) && <div>No services available</div>}
          {services.map((service, index) => (
            <button
              key={index}
              className="btn btn-sm btn-primary d-block mb-1"
              style={{ whiteSpace: 'nowrap' }}  // Ensures text stays on one line.
              onClick={() => window.open(service.access_url, '_blank')}
            >
              {service.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default DataLinkDropdown;
