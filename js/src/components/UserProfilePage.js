import React, { useEffect } from 'react';
import axios from 'axios';
import { API_PREFIX } from '../index';

function UserProfilePage({ user }) {
   useEffect(() => {
    axios.get(`${API_PREFIX}/users/me_from_session`);
   }, []);

    if (!user) {
        return <div className="alert alert-info">Loading user profile or not logged in...</div>;
    }

    return (
        <div className="card">
            <div className="card-header bg-info text-white">
                User Profile
            </div>
            <div className="card-body">
                {user.first_name && user.last_name && (
                    <p>
                        <strong>Name:</strong> {user.first_name} {user.last_name}
                    </p>
                )}
                {user.email && (
                    <p>
                        <strong>Email:</strong> {user.email}
                    </p>
                )}
                <p>
                    <strong>Application User ID:</strong> {user.id}
                </p>
                {user.iam_subject_id && (
                     <p>
                        <strong>IAM Subject ID:</strong> {user.iam_subject_id}
                    </p>
                )}
                {/* is_active, is_superuser from UserRead */}
            </div>
        </div>
    );
}

export default UserProfilePage;
