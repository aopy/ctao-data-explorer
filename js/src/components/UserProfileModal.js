import React, { useState, useEffect } from 'react';
import axios from 'axios';

// truncate long strings
const truncate = (str, maxLength = 50) => {
  if (!str) return '';
  return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
};

const UserProfileModal = ({ show, onClose, authToken }) => {
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (authToken && show) {
      axios
        .get('/users/me')
        .then(res => setProfile(res.data))
        .catch(err => console.error("Error fetching user profile", err));

      axios
        .get('/query-history')
        .then(res => setHistory(res.data))
        .catch(err => console.error("Error fetching query history", err));
    }
  }, [authToken, show]);

  if (!show) return null;

  return (
    <div className="modal show" style={{ display: 'block' }} role="dialog">
      <div className="modal-dialog modal-lg" role="document">
        <div className="modal-content">
          <div className="modal-header bg-info text-white">
            <h5 className="modal-title">User Profile</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            {profile && (
              <div>
                <p>
                  <strong>Full Name:</strong> {profile.first_name} {profile.last_name}
                </p>
                <p>
                  <strong>Email:</strong> {profile.email}
                </p>
                <p>
                  <strong>First Login:</strong>{" "}
                  {profile.first_login_at
                    ? new Date(profile.first_login_at).toLocaleString()
                    : 'N/A'}
                </p>
              </div>
            )}
            <h6>Search History</h6>
            {history.length > 0 ? (
              <div className="accordion" id="historyAccordion">
                {history.map(item => (
                  <div className="accordion-item" key={item.id}>
                    <h2 className="accordion-header" id={`heading${item.id}`}>
                      <button
                        className="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target={`#collapse${item.id}`}
                        aria-expanded="false"
                        aria-controls={`collapse${item.id}`}
                      >
                        {new Date(item.query_date).toLocaleString()} | Params:{" "}
                        {truncate(JSON.stringify(item.query_params))} | Results:{" "}
                        {truncate(JSON.stringify(item.results))}
                      </button>
                    </h2>
                    <div
                      id={`collapse${item.id}`}
                      className="accordion-collapse collapse"
                      aria-labelledby={`heading${item.id}`}
                      data-bs-parent="#historyAccordion"
                    >
                      <div className="accordion-body">
                        <strong>Parameters:</strong>
                        <pre>{JSON.stringify(item.query_params, null, 2)}</pre>
                        <strong>Results:</strong>
                        <pre>{JSON.stringify(item.results, null, 2)}</pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p>No search history available.</p>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfileModal;
