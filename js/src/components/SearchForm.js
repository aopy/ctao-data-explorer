import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults }) {
  const [objectName, setObjectName] = useState('');
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');
  const [searchRadius, setSearchRadius] = useState('5');
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');

  const handleResolve = () => {
    if (!objectName) return;
    axios.post('/api/simbad_resolve', { object_name: objectName })
      .then(response => {
        const res = response.data;
        if (res.results && res.results.length > 0) {
          const first = res.results[0];
          setTargetRAJ2000(first.ra);
          setTargetDEJ2000(first.dec);
        } else {
          alert('No match found for this object name.');
        }
      })
      .catch(error => {
        console.error('Error resolving object:', error);
        alert('Error resolving object name. Check console/logs.');
      });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Make API call to /api/search
    axios.get('/api/search', {
      params: {
        target_raj2000: targetRAJ2000,
        target_dej2000: targetDEJ2000,
        search_radius: searchRadius,
        tap_url: tapUrl,
        obscore_table: obscoreTable,
      },
    })
    .then(response => {
      setResults(response.data);
    })
    .catch(error => {
      console.error('There was an error making the request:', error);
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Optional object name field */}
        <div className="mb-3">
          <label className="form-label">Object Name (optional):</label>
          <div className="input-group">
            <input
              type="text"
              className="form-control"
              value={objectName}
              onChange={(e) => setObjectName(e.target.value)}
              placeholder="e.g. M1"
            />
            <button type="button" className="btn btn-secondary" onClick={handleResolve}>
              Resolve
            </button>
          </div>
        </div>
      <div className="mb-3">
        <label className="form-label">Target RA (J2000) [deg]:</label>
        <input
          type="number"
          className="form-control"
          value={targetRAJ2000}
          onChange={(e) => setTargetRAJ2000(e.target.value)}
          required
          min="0"
          max="360"
          step="any"
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Target Dec (J2000) [deg]:</label>
        <input
          type="number"
          className="form-control"
          value={targetDEJ2000}
          onChange={(e) => setTargetDEJ2000(e.target.value)}
          required
          min="-90"
          max="90"
          step="any"
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Search Radius [deg]:</label>
        <input
          type="number"
          className="form-control"
          value={searchRadius}
          onChange={(e) => setSearchRadius(e.target.value)}
          required
          min="0"
          max="90"
          step="any"
        />
      </div>
      <div className="mb-3">
        <label className="form-label">TAP Server URL:</label>
        <input
          type="text"
          className="form-control"
          value={tapUrl}
          onChange={(e) => setTapUrl(e.target.value)}
          required
        />
      </div>
      <div className="mb-3">
        <label className="form-label">ObsCore Table Name:</label>
        <input
          type="text"
          className="form-control"
          value={obscoreTable}
          onChange={(e) => setObscoreTable(e.target.value)}
          required
        />
      </div>
      <button type="submit" className="btn btn-primary w-100">Search</button>
    </form>
  );
}

export default SearchForm;
