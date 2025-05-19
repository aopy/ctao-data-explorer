import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import { format, parse, isValid } from 'date-fns';
import {
    mjdToDate,
    dateToMjd,
    parseDateTimeStrings,
    formatDateTimeStrings,
    COORD_SYS_EQ_DEG,
    COORD_SYS_EQ_HMS,
    COORD_SYS_GAL
} from './datetimeUtils';

function SearchForm({ setResults, isLoggedIn }) {
  // Object Resolve
  const [objectName, setObjectName] = useState('');
  const [useSimbad, setUseSimbad] = useState(true);
  const [useNed, setUseNed] = useState(false);

  // Coordinates
  const [coordinateSystem, setCoordinateSystem] = useState(COORD_SYS_EQ_DEG);
  const [coord1, setCoord1] = useState('');
  const [coord2, setCoord2] = useState('');
  const [searchRadius, setSearchRadius] = useState('5');

  // Time/MJD
  // Store Date objects for DatePicker, strings for MJD/Time input
  const [obsStartDateObj, setObsStartDateObj] = useState(null);
  const [obsStartTime, setObsStartTime] = useState('');
  const [obsStartMJD, setObsStartMJD] = useState('');   // MJD string

  const [obsEndDateObj, setObsEndDateObj] = useState(null);
  const [obsEndTime, setObsEndTime] = useState('');
  const [obsEndMJD, setObsEndMJD] = useState('');

  // Tracks which field type initiated the last change
  const [lastChangedType, setLastChangedType] = useState(null); // 'start_dt', 'start_mjd', 'end_dt', 'end_mjd'

  // Advanced
  const [tapUrl, setTapUrl] = useState('http://voparis-tap-he.obspm.fr/tap');
  const [obscoreTable, setObscoreTable] = useState('hess_dr.obscore_sdc');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // UI Feedback
  const [warningMessage, setWarningMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  let coord1Placeholder = "e.g., 83.633";
    let coord2Placeholder = "e.g., 22.014";

    if (coordinateSystem === COORD_SYS_EQ_HMS) {
        coord1Placeholder = "e.g., 05 34 31.9";
        coord2Placeholder = "e.g., +22 00 52";
    } else if (coordinateSystem === COORD_SYS_GAL) {
        coord1Placeholder = "e.g., 184.557";
        coord2Placeholder = "e.g., -5.784";
    }

  // Coordinate System Labels
  let coord1Label = 'RA (deg)';
  let coord2Label = 'Dec (deg)';
  if (coordinateSystem === COORD_SYS_EQ_HMS) {
    coord1Label = 'RA (hms)';
    coord2Label = 'Dec (dms)';
  } else if (coordinateSystem === COORD_SYS_GAL) {
    coord1Label = 'l (deg)';
    coord2Label = 'b (deg)';
  }

  // Time/MJD synchronization
  // Use useCallback to memoize handlers
  const syncDateTimeToMjd = useCallback((dateObj, timeStr, setMjdState) => {
    const dateWithTime = parseDateTimeStrings(
        dateObj ? format(dateObj, 'dd/MM/yyyy') : '', // Get dd/MM/yyyy from date obj
        timeStr
    );
    if (dateWithTime) {
      const mjd = dateToMjd(dateWithTime);
      setMjdState(mjd !== null ? mjd.toString() : '');
    } else {
      setMjdState('');
    }
  }, []);

  const syncMjdToDateTime = useCallback((mjdStr, setDateObjState, setTimeState) => {
    const mjdNum = parseFloat(mjdStr);
    if (!isNaN(mjdNum)) {
      const dateObj = mjdToDate(mjdNum);
      if (dateObj) {
        const { timeStr } = formatDateTimeStrings(dateObj);
        setDateObjState(dateObj); // Set date object state
        setTimeState(timeStr);    // Set time string state
      } else {
         setDateObjState(null); setTimeState('');
      }
    } else {
       setDateObjState(null); setTimeState('');
    }
  }, []);

  const [timeWarning, setTimeWarning] = useState(''); // state for time-related warnings

  // Effects for Synchronization
  useEffect(() => {
    if (lastChangedType === 'start_dt') {
      setTimeWarning('');
      if (obsStartDateObj && obsStartTime.trim()) {
        const dateStrForParsing = format(obsStartDateObj, 'dd/MM/yyyy');
        const dateTimeObj = parseDateTimeStrings(dateStrForParsing, obsStartTime.trim());

        if (dateTimeObj) {
          // valid date and time, convert to MJD
          const mjd = dateToMjd(dateTimeObj);
          setObsStartMJD(mjd !== null ? mjd.toString() : '');
          if (mjd === null) {
            setTimeWarning('Could not convert Start Date/Time to MJD.');
          }
        } else {
          // Date and/or Time format is invalid
          setTimeWarning('Invalid Start Date/Time format. Use dd/MM/yyyy and HH:MM:SS.');
          setObsStartMJD('');
        }
      } else if (!obsStartDateObj && !obsStartTime.trim()) {
        // Both are empty, clear MJD
        setObsStartMJD('');
      } else {
        // One is filled, one is not - MJD cannot be fully determined
        setObsStartMJD('');
      }
    }
  }, [obsStartDateObj, obsStartTime, lastChangedType, setObsStartMJD]);

  useEffect(() => {
    if (lastChangedType === 'start_mjd') {
      setTimeWarning('');
      const mjdStr = obsStartMJD.trim();

      if (mjdStr === "") {
        setObsStartDateObj(null);
        setObsStartTime('');
        return;
      }

      const mjdNum = parseFloat(mjdStr);
      if (isNaN(mjdNum)) {
        setTimeWarning('Start MJD must be a number.');
        setObsStartDateObj(null);
        setObsStartTime('');
        return;
      }

      // Attempt to convert MJD to Date object
      const dateObjFromMjd = mjdToDate(mjdNum);

      if (dateObjFromMjd) {
        // Conversion successful
        const { timeStr } = formatDateTimeStrings(dateObjFromMjd);
        setObsStartDateObj(dateObjFromMjd);
        setObsStartTime(timeStr);
      } else {
        // Conversion failed
        setTimeWarning('Start MJD resulted in an out-of-range or invalid date.');
        setObsStartDateObj(null);
        setObsStartTime('');
      }
    }
  }, [obsStartMJD, lastChangedType, setObsStartDateObj, setObsStartTime]);

  useEffect(() => {
    if (lastChangedType === 'end_dt') {
      setTimeWarning('');
      if (obsEndDateObj && obsEndTime.trim()) {
        const dateStrForParsing = format(obsEndDateObj, 'dd/MM/yyyy');
        const dateTimeObj = parseDateTimeStrings(dateStrForParsing, obsEndTime.trim());
        if (dateTimeObj) {
          const mjd = dateToMjd(dateTimeObj);
          setObsEndMJD(mjd !== null ? mjd.toString() : '');
          if (mjd === null) {
            setTimeWarning('Could not convert End Date/Time to MJD.');
          }
        } else {
          setTimeWarning('Invalid End Date/Time format. Use dd/MM/yyyy and HH:MM:SS.');
          setObsEndMJD('');
        }
      } else if (!obsEndDateObj && !obsEndTime.trim()) {
        setObsEndMJD('');
      } else {
        setObsEndMJD('');
      }
    }
  }, [obsEndDateObj, obsEndTime, lastChangedType, setObsEndMJD]);

  useEffect(() => {
    if (lastChangedType === 'end_mjd') {
      setTimeWarning('');
      const mjdStr = obsEndMJD.trim();
      if (mjdStr === "") {
        setObsEndDateObj(null);
        setObsEndTime('');
        return;
      }
      const mjdNum = parseFloat(mjdStr);
      if (isNaN(mjdNum)) {
        setTimeWarning('End MJD must be a number.');
        setObsEndDateObj(null);
        setObsEndTime('');
        return;
      }
      const dateObjFromMjd = mjdToDate(mjdNum);
      if (dateObjFromMjd) {
        const { timeStr } = formatDateTimeStrings(dateObjFromMjd);
        setObsEndDateObj(dateObjFromMjd);
        setObsEndTime(timeStr);
      } else {
        setTimeWarning('End MJD resulted in an out-of-range or invalid date.');
        setObsEndDateObj(null);
        setObsEndTime('');
      }
    }
  }, [obsEndMJD, lastChangedType, setObsEndDateObj, setObsEndTime]);

  // Event Handlers
  const handleResolve = () => {
    setWarningMessage('');
    if (!objectName) return;
    setIsSubmitting(true);
    axios.post('/api/object_resolve', {
      object_name: objectName, use_simbad: useSimbad, use_ned: useNed
    })
    .then(res => {
      const firstMatch = res.data?.results?.[0];
      if (firstMatch?.ra != null && firstMatch?.dec != null) {
        // Always populate Equ J2000 decimal degrees after resolve
        setCoordinateSystem(COORD_SYS_EQ_DEG);
        setCoord1(firstMatch.ra.toString());
        setCoord2(firstMatch.dec.toString());
        setWarningMessage(`Resolved ${objectName} via ${firstMatch.service}`);
      } else {
        setWarningMessage(`Could not resolve "${objectName}"`);
      }
    })
    .catch(err => {
      console.error('Resolve error:', err);
      setWarningMessage(`Error resolving object: ${err.message}`);
    })
    .finally(() => setIsSubmitting(false));
  };

  const handleCoordSystemChange = (e) => {
     setCoordinateSystem(e.target.value);
     // Clear coord inputs when system changes
     setCoord1('');
     setCoord2('');
  };

  // Handlers for Time/MJD inputs that set the 'lastChangedType'
  const handleStartDateChange = (date) => { setObsStartDateObj(date); setLastChangedType('start_dt'); };
  const handleStartTimeChange = (e) => { setObsStartTime(e.target.value); setLastChangedType('start_dt'); };
  const handleStartMjdChange = (e) => { setObsStartMJD(e.target.value); setLastChangedType('start_mjd'); };
  const handleEndDateChange = (date) => { setObsEndDateObj(date); setLastChangedType('end_dt'); };
  const handleEndTimeChange = (e) => { setObsEndTime(e.target.value); setLastChangedType('end_dt'); };
  const handleEndMjdChange = (e) => { setObsEndMJD(e.target.value); setLastChangedType('end_mjd'); };

  // Submit Handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setWarningMessage('');
    setIsSubmitting(true);
    setLastChangedType(null);

    // Base Request Parameters
    const baseReqParams = {
      tap_url: tapUrl,
      obscore_table: obscoreTable,
      search_radius: parseFloat(searchRadius) || 5.0,
    };

    let finalReqParams = { ...baseReqParams };
    let coordsAreValid = false;
    let timeIsValid = false;

    // Coordinate Processing
    const coord1Input = coord1.trim();
    const coord2Input = coord2.trim();

    if (timeWarning) {
        setWarningMessage(timeWarning);
        setIsSubmitting(false);
        return;
    }

    if (coord1Input && coord2Input) {
        let systemForBackend = '';
        let raDeg = null;
        let decDeg = null;
        let lDeg = null;
        let bDeg = null;

        try {
            // Determine system string for backend parser
            if (coordinateSystem === COORD_SYS_EQ_HMS) systemForBackend = 'hmsdms';
            else if (coordinateSystem === COORD_SYS_GAL) systemForBackend = 'gal';
            else systemForBackend = 'deg'; // Default to decimal degrees

            console.log(`Calling /api/parse_coords with:`, { coord1: coord1Input, coord2: coord2Input, system: systemForBackend });
            // Call Backend Parser
            const parseResponse = await axios.post('/api/parse_coords', {
                coord1: coord1Input,
                coord2: coord2Input,
                system: systemForBackend
            });
            console.log("Parse response:", parseResponse.data);

            if (parseResponse.data.error) {
                throw new Error(parseResponse.data.error);
            }

            // Extract results from successful parse
            raDeg = parseResponse.data.ra_deg;
            decDeg = parseResponse.data.dec_deg;
            lDeg = parseResponse.data.l_deg; // Will be null if not galactic
            bDeg = parseResponse.data.b_deg; // Will be null if not galactic

            // add the correct parameters for the search endpoint
            if (coordinateSystem === COORD_SYS_GAL) {
                // Send l/b if system was galactic and parsing succeeded
                 if (lDeg !== null && bDeg !== null) {
                    finalReqParams.coordinate_system = COORD_SYS_GAL;
                    finalReqParams.l = lDeg;
                    finalReqParams.b = bDeg;
                    coordsAreValid = true;
                } else {
                     throw new Error("Galactic parsing succeeded but did not return l/b degrees.");
                }
            } else if (coordinateSystem === COORD_SYS_EQ_DEG) {
                if (raDeg !== null && decDeg !== null) {
                    finalReqParams.coordinate_system = COORD_SYS_EQ_DEG;
                    finalReqParams.ra = raDeg;
                    finalReqParams.dec = decDeg;
                    coordsAreValid = true;
                } else {
                     throw new Error("Equatorial parsing succeeded but did not return RA/Dec degrees.");
                }
            } else if (coordinateSystem === COORD_SYS_EQ_HMS) {
             if (raDeg !== null && decDeg !== null) {
                finalReqParams.coordinate_system = COORD_SYS_EQ_HMS;
                finalReqParams.ra = raDeg;
                finalReqParams.dec = decDeg;
                coordsAreValid = true;
            } else {
                     throw new Error("Equatorial parsing succeeded but did not return hms/dms.");
                }
            }

        } catch (parseError) {
            console.error("Coordinate Parsing API call failed:", parseError);
            const errorMsg = parseError.response?.data?.error || parseError.message || "Coordinate parsing failed.";
            setWarningMessage(`Coordinate Error: ${errorMsg}`);
            setIsSubmitting(false);
            return;
        }
    }

    // Time Processing - Prioritize MJD if both are potentially valid
    const startMjdNum = parseFloat(obsStartMJD);
    const endMjdNum = parseFloat(obsEndMJD);
    if (!isNaN(startMjdNum) && !isNaN(endMjdNum)) {
        if (endMjdNum <= startMjdNum) {
            setWarningMessage("End MJD must be after Start MJD."); setIsSubmitting(false); return;
        }
        finalReqParams.mjd_start = startMjdNum;
         finalReqParams.mjd_end = endMjdNum;
         timeIsValid = true;
    }
    // Fallback to Date/Time strings only if MJD wasn't provided/valid
    else if (obsStartDateObj && obsStartTime.trim() && obsEndDateObj && obsEndTime.trim()) {
        const startDateTime = parseDateTimeStrings(format(obsStartDateObj, 'dd/MM/yyyy'), obsStartTime.trim());
         const endDateTime = parseDateTimeStrings(format(obsEndDateObj, 'dd/MM/yyyy'), obsEndTime.trim());

        if (!startDateTime || !endDateTime || endDateTime <= startDateTime) {
            setWarningMessage("Invalid Date/Time format. Use dd/MM/yyyy and HH:mm:ss."); setIsSubmitting(false); return;
        }
        if (endDateTime <= startDateTime) {
            setWarningMessage("End Date/Time must be after Start Date/Time."); setIsSubmitting(false); return;
        }
        // Convert valid Date/Time back to MJD for backend
        const mjdStartDerived = dateToMjd(startDateTime);
        const mjdEndDerived = dateToMjd(endDateTime);
        if (mjdStartDerived !== null && mjdEndDerived !== null) {
            finalReqParams.mjd_start = mjdStartDerived;
             finalReqParams.mjd_end = mjdEndDerived;
             timeIsValid = true;
        } else {
            setWarningMessage("Failed to convert valid Date/Time to MJD."); setIsSubmitting(false); return;
        }
    }


    if (!coordsAreValid && !timeIsValid) {
       setWarningMessage("Please provide valid coordinates or a complete time interval (Date+Time or MJD).");
       setIsSubmitting(false);
       return;
    }

    // make search API call
    console.log("Submitting search request with params:", finalReqParams);
    axios.get('/api/search_coords', { params: finalReqParams })
      .then(response => {
        setResults(response.data);
      })
      .catch(error => {
        console.error('Search error:', error);
        const errorDetail = error.response?.data?.detail || error.message || 'Unknown search error.';
        setWarningMessage(`Search failed: ${errorDetail}`);
      })
      .finally(() => {
         setIsSubmitting(false);
         setLastChangedType(null);
      });
  };

  return (
    // Use Bootstrap grid for layout
    <div className="row">
        <div className="col-lg-7 col-md-8"> {/* Adjust column size for form width */}
            <form onSubmit={handleSubmit}>
                 {warningMessage && (
                    <div className="alert alert-warning" role="alert">
                      {warningMessage}
                    </div>
                  )}

                {/* Cone Search Section */}
                <div className="card mb-3">
                    <div className="card-header">Cone Search</div>
                    <div className="card-body">
                        {/* Object Resolve */}
                        <div className="mb-3">
                            <label htmlFor="objectNameInput" className="form-label">Source Name (optional)</label>
                            <div className="input-group">
                            <input
                                type="text"
                                className="form-control"
                                id="objectNameInput"
                                value={objectName}
                                onChange={(e) => setObjectName(e.target.value)}
                                placeholder="e.g., M1, Crab Nebula"
                                disabled={isSubmitting}
                            />
                            <button type="button" className="btn btn-secondary" onClick={handleResolve} disabled={!objectName || isSubmitting}>
                                Resolve
                            </button>
                            </div>
                            <div className="mt-2">
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="checkbox" id="useSimbadCheck" checked={useSimbad} onChange={() => setUseSimbad(!useSimbad)} disabled={isSubmitting}/>
                                    <label className="form-check-label" htmlFor="useSimbadCheck">SIMBAD</label>
                                </div>
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="checkbox" id="useNedCheck" checked={useNed} onChange={() => setUseNed(!useNed)} disabled={isSubmitting}/>
                                    <label className="form-check-label" htmlFor="useNedCheck">NED</label>
                                </div>
                            </div>
                        </div>

                        {/* Coordinates */}
                        <div className="mb-3">
                             <label htmlFor="coordSysSelect" className="form-label">Coordinate System</label>
                             <select id="coordSysSelect" className="form-select" value={coordinateSystem} onChange={handleCoordSystemChange} disabled={isSubmitting}>
                                 <option value={COORD_SYS_EQ_DEG}>Equatorial (deg)</option>
                                 <option value={COORD_SYS_EQ_HMS}>Equatorial (hms/dms)</option>
                                 <option value={COORD_SYS_GAL}>Galactic (l/b deg)</option>
                             </select>
                        </div>
                        <div className="row g-2 mb-3">
                            <div className="col-md">
                                <label htmlFor="coord1Input" className="form-label">{coord1Label}</label>
                                <input
                                    type="text"
                                    className="form-control"
                                    id="coord1Input"
                                    value={coord1}
                                    onChange={(e) => setCoord1(e.target.value)}
                                    placeholder={coord1Placeholder}
                                    disabled={isSubmitting}
                                    aria-label={coord1Label}
                                />
                            </div>
                            <div className="col-md">
                                 <label htmlFor="coord2Input" className="form-label">{coord2Label}</label>
                                 <input
                                    type="text"
                                    className="form-control"
                                    id="coord2Input"
                                    value={coord2}
                                    onChange={(e) => setCoord2(e.target.value)}
                                    placeholder={coord2Placeholder}
                                    disabled={isSubmitting}
                                    aria-label={coord2Label}
                                />
                            </div>
                        </div>

                         {/* Radius */}
                         <div className="mb-3">
                            <label htmlFor="radiusInput" className="form-label">Radius (deg)</label>
                            <input
                                type="number"
                                className="form-control"
                                id="radiusInput"
                                value={searchRadius}
                                onChange={(e) => setSearchRadius(e.target.value)}
                                min="0"
                                max="90"
                                step="any"
                                disabled={isSubmitting}
                            />
                        </div>
                    </div>
                </div>

                {timeWarning && (
                  <div className="alert alert-sm alert-warning mt-1 mb-2 p-1" role="alert">
                    {timeWarning}
                  </div>
                )}

                {/* Time Search Section */}
                <div className="card mb-3">
                     <div className="card-header">Time Search</div>
                     <div className="card-body">
                         {/* Start Time Inputs */}
                         <label className="form-label">Observation Start</label>
                         <div className="row g-2 mb-2">
                             <div className="col-md-4">
                                 <DatePicker
                                     selected={obsStartDateObj}
                                     onChange={handleStartDateChange}
                                     dateFormat="dd/MM/yyyy"
                                     placeholderText="dd/mm/yyyy"
                                     className="form-control form-control-sm"
                                     wrapperClassName="w-100"
                                     disabled={isSubmitting}
                                     showMonthDropdown
                                     showYearDropdown
                                     dropdownMode="select"
                                 />
                             </div>

                             <div className="col-md-3">
                                 <input type="text" className="form-control form-control-sm" placeholder="HH:MM:SS" aria-label="Start time" value={obsStartTime} onChange={handleStartTimeChange} disabled={isSubmitting}/>
                                  {/* TODO: Add Clock Picker */}
                             </div>
                             <div className="col-md-5">
                                  <div className="input-group input-group-sm">
                                     <input type="number" step="any" className="form-control" placeholder="Start MJD" aria-label="Start MJD" value={obsStartMJD} onChange={handleStartMjdChange} disabled={isSubmitting}/>
                                      <span className="input-group-text">MJD</span>
                                  </div>
                             </div>
                         </div>
                          {/* End Time Inputs */}
                         <label className="form-label">Observation End</label>
                         <div className="row g-2 mb-3">
                              <div className="col-md-4">
                                 {/* DatePicker */}
                                 <DatePicker
                                     selected={obsEndDateObj}
                                     onChange={handleEndDateChange}
                                     dateFormat="dd/MM/yyyy"
                                     placeholderText="dd/mm/yyyy"
                                     className="form-control form-control-sm"
                                     wrapperClassName="w-100"
                                     disabled={isSubmitting}
                                     showMonthDropdown
                                     showYearDropdown
                                     dropdownMode="select"
                                     minDate={obsStartDateObj || null}
                                 />
                             </div>
                             <div className="col-md-3">
                                 <input type="text" className="form-control form-control-sm" placeholder="HH:MM:SS" aria-label="End time" value={obsEndTime} onChange={handleEndTimeChange} disabled={isSubmitting}/>
                             </div>
                             <div className="col-md-5">
                                  <div className="input-group input-group-sm">
                                     <input type="number" step="any" className="form-control" placeholder="End MJD" aria-label="End MJD" value={obsEndMJD} onChange={handleEndMjdChange} disabled={isSubmitting}/>
                                      <span className="input-group-text">MJD</span>
                                  </div>
                             </div>
                         </div>
                     </div>
                </div>

                 {/* Advanced Settings Section */}
                 <div className="mb-3">
                     <button
                        className="btn btn-link btn-sm p-0"
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        aria-expanded={showAdvanced}
                     >
                         {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
                     </button>
                     {showAdvanced && (
                        <div className="card card-body mt-2">
                             <div className="mb-3">
                                <label htmlFor="tapUrlInput" className="form-label">TAP Server URL</label>
                                <input type="text" className="form-control" id="tapUrlInput" value={tapUrl} onChange={(e) => setTapUrl(e.target.value)} disabled={isSubmitting}/>
                             </div>
                             <div>
                                <label htmlFor="obsCoreTableInput" className="form-label">ObsCore Table Name</label>
                                <input type="text" className="form-control" id="obsCoreTableInput" value={obscoreTable} onChange={(e) => setObscoreTable(e.target.value)} disabled={isSubmitting}/>
                             </div>
                        </div>
                     )}
                 </div>


                {/* Search Button */}
                <div className="d-flex justify-content-end mb-3">
                    <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                         {isSubmitting ? (
                            <><span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...</>
                         ) : (
                            'Search'
                         )}
                    </button>
                </div>

            </form>
        </div>
        <div className="col-lg-5 col-md-4">
            {/* placeholder for images */}
            <div className="p-3 text-center text-muted">
                 {/* <img src="/path/to/image1.jpg" alt="Description" className="img-fluid mb-2"/> */}
                 {/* <img src="/path/to/image2.jpg" alt="Description" className="img-fluid"/> */}
            </div>
        </div>
    </div>
  );
}

export default SearchForm;
