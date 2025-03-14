import React, { useState } from 'react';
import axios from 'axios';

function SearchForm({ setResults, authToken }) {
  // Object name resolution states
  const [objectName, setObjectName] = useState('');
  const [useSimbad, setUseSimbad] = useState(true);  // SIMBAD checked by default
  const [useNed, setUseNed] = useState(false);

  // Show a Bootstrap inline alert if something goes wrong or no matches found
  const [warningMessage, setWarningMessage] = useState('');

  // Coordinate system (default = Equatorial)
  const [coordinateSystem, setCoordinateSystem] = useState('equatorial');

  // Equatorial fields (J2000)
  const [targetRAJ2000, setTargetRAJ2000] = useState('');
  const [targetDEJ2000, setTargetDEJ2000] = useState('');

  // Galactic fields
  const [galacticL, setGalacticL] = useState('');
  const [galacticB, setGalacticB] = useState('');

  const [searchRadius, setSearchRadius] = useState('5');
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');

  // States for observation start and end date-times
  const [obsStart, setObsStart] = useState('');  // expected format: dd/mm/yyyy HH:MM:SS
  const [obsEnd, setObsEnd] = useState('');      // expected format: dd/mm/yyyy HH:MM:SS

  const handleResolve = () => {
    setWarningMessage('');
    if (!objectName) return;

    axios.post('/api/object_resolve', {
      object_name: objectName,
      use_simbad: useSimbad,
      use_ned: useNed
    })
    .then(res => {
      const allResults = res.data.results;
      if (allResults && allResults.length > 0) {
        // Pick the first match
        const first = allResults[0];
        const resolvedRa = first.ra;
        const resolvedDec = first.dec;

        console.log(`Resolved => RA=${resolvedRa}, Dec=${resolvedDec}, from ${first.service}`);

        // Always fill equatorial fields
        setCoordinateSystem('equatorial');
        setTargetRAJ2000(resolvedRa);
        setTargetDEJ2000(resolvedDec);
      } else {
        setWarningMessage(`No match found for "${objectName}" in the selected service(s).`);
      }
    })
    .catch(err => {
      console.error('Resolve error:', err);
      setWarningMessage('Error resolving object name. Check console logs.');
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setWarningMessage('');

    const reqParams = {
      coordinate_system: coordinateSystem,
      search_radius: searchRadius,
      tap_url: tapUrl,
      obscore_table: obscoreTable
    };

    // Only include coordinate parameters if they are non-empty
    if (coordinateSystem === 'equatorial') {
      if (String(targetRAJ2000).trim() !== '' && String(targetDEJ2000).trim() !== '') {
        reqParams.ra = targetRAJ2000;
        reqParams.dec = targetDEJ2000;
      }
    } else if (coordinateSystem === 'galactic') {
      if (String(galacticL).trim() !== '' && String(galacticB).trim() !== '') {
        reqParams.l = galacticL;
        reqParams.b = galacticB;
      }
    }

    // Include observation time interval parameters if provided
    if (obsStart.trim() !== '' && obsEnd.trim() !== '') {
      reqParams.obs_start = obsStart;
      reqParams.obs_end = obsEnd;
    }

    axios.get('/api/search_coords', { params: reqParams })
      .then(response => {
        setResults(response.data);

      if (authToken) {
        axios.post('/query-history', {
          query_params: reqParams,
          results: response.data,
        }, {
          headers: { Authorization: `Bearer ${authToken}` }
        })
        .catch(error => {
          console.error("Error recording search history:", error.response ? error.response.data : error.message);
        });
        }
      })
      .catch(error => {
        console.error('Search error:', error);
        setWarningMessage('Search error. Check console logs.');
      });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Object Resolve Section */}
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

        {/* Simbad, NED checkboxes */}
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
      </div>

      {/* Coordinate System (Equatorial default) */}
      <div className="mb-3">
        <label className="form-label">Coordinate System</label>
        <select
          className="form-select"
          value={coordinateSystem}
          onChange={(e) => setCoordinateSystem(e.target.value)}
        >
          <option value="equatorial">Equatorial (J2000)</option>
          <option value="galactic">Galactic</option>
        </select>
      </div>

      {/* Equatorial fields (RA/Dec) */}
      {coordinateSystem === 'equatorial' && (
        <>
          <div className="mb-3">
            <label className="form-label">RA (J2000) [deg]:</label>
            <input
              type="number"
              className="form-control"
              value={targetRAJ2000}
              onChange={(e) => setTargetRAJ2000(e.target.value)}
              min="0"
              max="360"
              step="any"
            />
          </div>
          <div className="mb-3">
            <label className="form-label">Dec (J2000) [deg]:</label>
            <input
              type="number"
              className="form-control"
              value={targetDEJ2000}
              onChange={(e) => setTargetDEJ2000(e.target.value)}
              min="-90"
              max="90"
              step="any"
            />
          </div>
        </>
      )}

      {/* Galactic fields (l,b) */}
      {coordinateSystem === 'galactic' && (
        <>
          <div className="mb-3">
            <label className="form-label">l [deg]:</label>
            <input
              type="number"
              className="form-control"
              value={galacticL}
              onChange={(e) => setGalacticL(e.target.value)}
              min="0"
              max="360"
              step="any"
            />
          </div>
          <div className="mb-3">
            <label className="form-label">b [deg]:</label>
            <input
              type="number"
              className="form-control"
              value={galacticB}
              onChange={(e) => setGalacticB(e.target.value)}
              min="-90"
              max="90"
              step="any"
            />
          </div>
        </>
      )}

      {/* Observation Time Interval Inputs */}
      <div className="mb-3">
        <label className="form-label">Observation Start (dd/mm/yyyy HH:MM:SS):</label>
        <input
          type="text"
          className="form-control"
          value={obsStart}
          onChange={(e) => setObsStart(e.target.value)}
          placeholder="dd/mm/yyyy HH:MM:SS"
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Observation End (dd/mm/yyyy HH:MM:SS):</label>
        <input
          type="text"
          className="form-control"
          value={obsEnd}
          onChange={(e) => setObsEnd(e.target.value)}
          placeholder="dd/mm/yyyy HH:MM:SS"
        />
      </div>
      {/* Search radius, TAP URL, ObsCore Table */}
      <div className="mb-3">
        <label className="form-label">Search Radius [deg]:</label>
        <input
          type="number"
          className="form-control"
          value={searchRadius}
          onChange={(e) => setSearchRadius(e.target.value)}
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
        />
      </div>
      <div className="mb-3">
        <label className="form-label">ObsCore Table Name:</label>
        <input
          type="text"
          className="form-control"
          value={obscoreTable}
          onChange={(e) => setObscoreTable(e.target.value)}
        />
      </div>

      {/* Inline warning message */}
      {warningMessage && (
        <div className="alert alert-warning" role="alert">
          {warningMessage}
        </div>
      )}

      {/* Search button */}
      <button type="submit" className="btn btn-primary w-100">
        Search
      </button>
    </form>
  );
}

export default SearchForm;
