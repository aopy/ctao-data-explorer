// src/components/SearchForm.js

import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults }) {
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');
  const [searchRadius, setSearchRadius] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();

    // Validate inputs here if necessary

    // Make API call
    axios.get('http://127.0.0.1:8000/api/search', {
      params: {
        target_raj2000: targetRAJ2000,
        target_dej2000: targetDEJ2000,
        search_radius: searchRadius,
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
      <button type="submit">Search</button>
    </form>
  );
}

export default SearchForm;
