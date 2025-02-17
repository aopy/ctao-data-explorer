import React, { useState } from 'react';
import axios from 'axios';

const DataLinkDropdown = ({ datalink_url }) => {
  const [services, setServices] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggleDropdown = async () => {
    if (!open && services.length === 0) {
      setLoading(true);
      try {
        const res = await axios.get(datalink_url, { responseType: 'text' });
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(res.data, "application/xml");
        const tabledata = xmlDoc.getElementsByTagName("TABLEDATA")[0];
        let svc = [];
        if (tabledata) {
          const trElements = tabledata.getElementsByTagName("TR");
          for (let i = 0; i < trElements.length; i++) {
            const tdElements = trElements[i].getElementsByTagName("TD");
            // td[0]: ID, td[1]: access_url, td[2]: error_message
            if (tdElements[2] && tdElements[2].textContent.trim() === "") {
              svc.push({
                label: "Download", // For now, always show "Download"
                access_url: tdElements[1].textContent.trim(),
              });
            }
          }
        }
        setServices(svc);
      } catch (error) {
        console.error("Error fetching DataLink services:", error);
      } finally {
        setLoading(false);
      }
    }
    setOpen(!open);
  };

  return (
    <div style={{ position: 'relative' }}>
      <button className="btn btn-sm btn-info" onClick={toggleDropdown}>
        DataLink
      </button>
      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          background: 'white',
          border: '1px solid #ccc',
          zIndex: 1000,
          padding: '5px'
        }}>
          {loading && <div>Loading...</div>}
          {(!loading && services.length === 0) && <div>No services available</div>}
          {services.map((service, index) => (
            <button
              key={index}
              className="btn btn-sm btn-secondary d-block mb-1"
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
