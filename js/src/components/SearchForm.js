import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults }) {
  const [objectName, setObjectName] = useState('');
  // SIMBAD checked by default, NED unchecked
  const [useSimbad, setUseSimbad] = useState(true);
  const [useNed, setUseNed] = useState(false);
  const [warningMessage, setWarningMessage] = useState('');
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');
  const [searchRadius, setSearchRadius] = useState('5');
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');

  const handleResolve = () => {
    setWarningMessage(''); // clear any old warning
    if (!objectName) return;

    axios.post('/api/object_resolve', {
      object_name: objectName,
      use_simbad: useSimbad,
      use_ned: useNed
    })
    .then(res => {
      const all = res.data.results;
      if (all && all.length > 0) {
        // If there's at least one result, pick the first for RA/DEC
        const first = all[0];
        setTargetRAJ2000(first.ra);
        setTargetDEJ2000(first.dec);
      } else {
        // Show a warning below the object name field
        setWarningMessage(`No match found for '${objectName}' in the selected service(s).`);
      }
    })
    .catch(err => {
      console.error('Resolve error:', err);
      setWarningMessage('Error resolving object. Check logs.');
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setWarningMessage('');
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
      console.error('Search request error:', error);
      setWarningMessage('Error searching data. See console.');
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Object name + checkboxes + resolve button */}
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

        {/* checkboxes for Simbad & NED */}
        <div className="form-check mt-2">
          <input
            className="form-check-input"
            type="checkbox"
            id="useSimbadCheck"
            checked={useSimbad}
            onChange={() => setUseSimbad(!useSimbad)}
          />
          <label className="form-check-label" htmlFor="useSimbadCheck">
            Use SIMBAD
          </label>
        </div>
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            id="useNedCheck"
            checked={useNed}
            onChange={() => setUseNed(!useNed)}
          />
          <label className="form-check-label" htmlFor="useNedCheck">
            Use NED
          </label>
        </div>

        {/* Bootstrap inline warning if no match */}
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
