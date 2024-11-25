import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults }) {
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');
  const [searchRadius, setSearchRadius] = useState('');
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');

  const handleSubmit = (e) => {
    e.preventDefault();

    // Validate inputs here

    // Make API call
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
      {/* Existing form fields */}
      <div>
        <label>Target RA (J2000):</label>
        <input
          type="number"
          value={targetRAJ2000}
          onChange={(e) => setTargetRAJ2000(e.target.value)}
          required
          min="0"
          max="360"
          step="any"
        />
      </div>
      <div>
        <label>Target DEC (J2000):</label>
        <input
          type="number"
          value={targetDEJ2000}
          onChange={(e) => setTargetDEJ2000(e.target.value)}
          required
          min="-90"
          max="90"
          step="any"
        />
      </div>
      <div>
        <label>Search Radius (degrees):</label>
        <input
          type="number"
          value={searchRadius}
          onChange={(e) => setSearchRadius(e.target.value)}
          required
          min="0"
          max="90"
          step="any"
        />
      </div>

      {/* New form fields */}
      <div>
        <label>TAP Server URL:</label>
        <input
          type="text"
          value={tapUrl}
          onChange={(e) => setTapUrl(e.target.value)}
          required
        />
      </div>
      <div>
        <label>ObsCore Table Name:</label>
        <input
          type="text"
          value={obscoreTable}
          onChange={(e) => setObscoreTable(e.target.value)}
          required
        />
      </div>
      <button type="submit">Search</button>
    </form>
  );
}

export default SearchForm;
