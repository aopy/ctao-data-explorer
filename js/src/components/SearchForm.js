import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults }) {
  const [objectName, setObjectName] = useState('');
  const [warningMessage, setWarningMessage] = useState('');
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');
  const [searchRadius, setSearchRadius] = useState('5');
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');

  const handleResolve = () => {
    if (!objectName) return;
    setWarningMessage(''); // clear any existing warning
    axios.post('/api/simbad_resolve', { object_name: objectName })
      .then(response => {
        const res = response.data;
        if (res.results && res.results.length > 0) {
          const first = res.results[0];
          setTargetRAJ2000(first.ra);
          setTargetDEJ2000(first.dec);
        } else {
          setWarningMessage('No match found for this object name.');
        }
      })
      .catch(error => {
        console.error('Error resolving object:', error);
        setWarningMessage('Error resolving object name. Please try again.');
      });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setWarningMessage(''); // clear warnings on a new search
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
      setWarningMessage('An error occurred while searching. Check console for details.');
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Object name field with Resolve button */}
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
      {/* Display a warning alert if needed */}
        {warningMessage && (
          <div className="alert alert-warning mt-2" role="alert">
            {warningMessage}
          </div>
        )}
      </div>
      {/* RA/Dec fields */}
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
      {/* Search radius, TAP server, and table name fields */}
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
