import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_PREFIX } from '../index';


const UserProfileModal = ({ show, onClose, isLoggedIn }) => {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isLoggedIn && show) {
      setIsLoading(true);
      setError(null);
      axios.get('/api/users/me_from_session')
        .then(res => {
            setProfile(res.data);
        })
        .catch(err => {
            console.error("Error fetching user profile", err);
            setError("Could not load profile data.");
            setProfile(null);
        })
        .finally(() => setIsLoading(false));
    } else if (!show) {
      setProfile(null); setError(null);
    }
  }, [isLoggedIn, show]);

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
                <p><strong>User ID (App):</strong> {profile.id}</p>
                <p><strong>Email:</strong> {profile.email}</p>
              </div>
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
