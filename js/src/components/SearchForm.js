import React, { useState, useEffect, useCallback, forwardRef, useImperativeHandle, useRef } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import {
    mjdToDate,
    dateToMjd,
    parseDateTimeStrings,
    formatDateTimeStrings,
    COORD_SYS_EQ_DEG,
    COORD_SYS_EQ_HMS,
    COORD_SYS_GAL
} from './datetimeUtils';
import './styles.css';
import { format } from 'date-fns';
import { formatInTimeZone } from 'date-fns-tz';

const FORM_STATE_SESSION_KEY = 'searchFormStateBeforeLogin';

const defaultFormValues = {
  objectName: '', useSimbad: true, useNed: false,
  coordinateSystem: COORD_SYS_EQ_DEG, coord1: '', coord2: '', searchRadius: '5',
  obsStartDateObj: null, obsStartTime: '', obsStartMJD: '',
  obsEndDateObj: null, obsEndTime: '', obsEndMJD: '',
  tapUrl: 'http://voparis-tap-he.obspm.fr/tap',
  obscoreTable: 'hess_dr.obscore_sdc',
  showAdvanced: false,
  timeScale: 'tt',
  mjdScale: 'tt',
};

const SearchForm = forwardRef(({ setResults, isLoggedIn }, ref) => {

  // Build an ISO string from DatePicker day + HH:MM:SS
  const makeIsoFromDateAndTime = (dateObj, timeStr) => {
    const dayIso = format(dateObj, 'yyyy-MM-dd');
    return `${dayIso}T${timeStr.trim()}`;
  };

  // Calendar to MJD using backend and current scales
  const toMjdViaBackend = async (iso, timeScale, mjdScale) => {
    const resp = await axios.post('/api/convert_time', {
      value: iso,
      input_format: 'isot',
      input_scale: timeScale, // 'utc' | 'tt'
    });
    return (mjdScale === 'tt') ? resp.data.tt_mjd : resp.data.utc_mjd;
  };

  // MJD to ISO (UTC or TT) via backend and current scales
  const toIsoViaBackend = async (mjdStr, mjdScale, timeScale) => {
    const mjdNum = parseFloat(String(mjdStr).replace(',', '.'));
    const resp = await axios.post('/api/convert_time', {
      value: String(mjdNum),
      input_format: 'mjd',
      input_scale: mjdScale, // 'utc' | 'tt'
    });
    return (timeScale === 'tt') ? resp.data.tt_isot : resp.data.utc_isot;
  };

  // Parse "YYYY-MM-DDThh:mm:ss.sss" to DatePicker date + HH:MM:SS
  const applyIsoToDateAndTime = (iso, setDateObj, setTimeStr) => {
    const [d, t] = iso.split('T');
    const [y, m, day] = d.split('-').map(Number);
    setDateObj(new Date(Date.UTC(y, m - 1, day)));
    setTimeStr(t.slice(0, 8));
  };

  const formatMJD = (x, places = 8) =>
    Number.isFinite(+x) ? (+x).toFixed(places) : '';

  // normalize typed MJD (handles commas, spaces, underscores)
  const parseMjdInput = (v) => {
    if (v == null) return NaN;
    const s = String(v).trim().replace(/[ \u00A0_]/g, '').replace(',', '.');
    const n = Number(s);
    return Number.isFinite(n) ? n : NaN;
  };

  // Helper to load state from sessionStorage
  const loadInitialState = () => {
    try {
      const saved = sessionStorage.getItem(FORM_STATE_SESSION_KEY);
      if (saved) {
        sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
        const parsed = JSON.parse(saved);
        // Convert date strings back to Date objects
        if (parsed.obsStartDateObj) parsed.obsStartDateObj = new Date(parsed.obsStartDateObj);
        if (parsed.obsEndDateObj) parsed.obsEndDateObj = new Date(parsed.obsEndDateObj);
        console.log("SearchForm: Loaded state from session storage:", parsed);
        return { ...defaultFormValues, ...parsed };
      }
    } catch (e) {
      console.error("SearchForm: Failed to load state:", e);
      sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
    }
    return { ...defaultFormValues };
  };

  // Initialize state using the helper
  const [initialFormState] = useState(loadInitialState);

  const [objectName, setObjectName] = useState(initialFormState.objectName);
  const [useSimbad, setUseSimbad] = useState(initialFormState.useSimbad);
  const [useNed, setUseNed] = useState(initialFormState.useNed);
  const [coordinateSystem, setCoordinateSystem] = useState(initialFormState.coordinateSystem);
  const [coord1, setCoord1] = useState(initialFormState.coord1);
  const [coord2, setCoord2] = useState(initialFormState.coord2);
  const [searchRadius, setSearchRadius] = useState(initialFormState.searchRadius);
  const [obsStartDateObj, setObsStartDateObj] = useState(initialFormState.obsStartDateObj);
  const [obsStartTime, setObsStartTime] = useState(initialFormState.obsStartTime);
  const [obsStartMJD, setObsStartMJD] = useState(initialFormState.obsStartMJD);
  const [obsEndDateObj, setObsEndDateObj] = useState(initialFormState.obsEndDateObj);
  const [obsEndTime, setObsEndTime] = useState(initialFormState.obsEndTime);
  const [obsEndMJD, setObsEndMJD] = useState(initialFormState.obsEndMJD);
  const [timeScale, setTimeScale] = useState(initialFormState.timeScale ?? defaultFormValues.timeScale);
  const [mjdScale, setMjdScale]   = useState(initialFormState.mjdScale   ?? defaultFormValues.mjdScale);
  const [tapUrl, setTapUrl] = useState(initialFormState.tapUrl);
  const [obscoreTable, setObscoreTable] = useState(initialFormState.obscoreTable);
  const [showAdvanced, setShowAdvanced] = useState(initialFormState.showAdvanced);

  const [lastChangedType, setLastChangedType] = useState(null);
  const [warningMessage, setWarningMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [justSelected, setJustSelected] = useState(false);

  const [timeTouched, setTimeTouched] = useState(false);

  useEffect(() => {
    if (objectName.trim()) {
      lastAccepted.current = objectName.trim();
      setJustSelected(true);
    }
  }, []);

  const latestSeq = useRef(0);
  const lastAccepted = useRef('');

  // Ref for debounce timer
  const timeInputDebounceTimer = useRef(null);
  const MJDInputDebounceTimer = useRef(null);
  const endTimeInputDebounceTimer = useRef(null);
  const endMJDInputDebounceTimer = useRef(null);

  // Function to get current form state
  const getCurrentFormState = useCallback(() => {
    return {
      objectName, useSimbad, useNed,
      coordinateSystem, coord1, coord2, searchRadius,
      obsStartDateObj: obsStartDateObj ? obsStartDateObj.toISOString() : null, // Store as ISO string
      obsStartTime, obsStartMJD,
      obsEndDateObj: obsEndDateObj ? obsEndDateObj.toISOString() : null,
      obsEndTime, obsEndMJD,
      tapUrl, obscoreTable, showAdvanced,
      timeScale, mjdScale,
    };
  }, [
    objectName, useSimbad, useNed, coordinateSystem, coord1, coord2, searchRadius,
    obsStartDateObj, obsStartTime, obsStartMJD, obsEndDateObj, obsEndTime, obsEndMJD,
    tapUrl, obscoreTable, showAdvanced, timeScale, mjdScale
  ]);

    // Expose a saveState method to the parent App.js using useImperativeHandle
  useImperativeHandle(ref, () => ({
    saveState: () => {
      try {
        const stateToSave = getCurrentFormState();
        sessionStorage.setItem(FORM_STATE_SESSION_KEY, JSON.stringify(stateToSave));
        console.log("SearchForm: State explicitly saved to session storage.", stateToSave);
      } catch (e) {
        console.error("SearchForm: Error explicitly saving state to session storage:", e);
      }
    }
  }));

  // State to manage tooltip visibility
  const [showCoord1Tooltip, setShowCoord1Tooltip] = useState(false);
  const [showCoord2Tooltip, setShowCoord2Tooltip] = useState(false);

  const [suggestions, setSuggestions] = useState([]);
  const [highlight, setHighlight] = useState(-1);
  const debounceRef = useRef(null);

  let coord1Label = 'RA (deg)';
  let coord2Label = 'Dec (deg)';
  let coord1Example = "e.g., 83.633";
  let coord2Example = "e.g., 22.014";

  if (coordinateSystem === COORD_SYS_EQ_HMS) {
    coord1Label = 'RA (hms)'; coord2Label = 'Dec (dms)';
    coord1Example = "e.g., 05 34 31.9";
    coord2Example = "e.g., +22 00 52";
  } else if (coordinateSystem === COORD_SYS_GAL) {
    coord1Label = 'l (deg)'; coord2Label = 'b (deg)';
    coord1Example = "e.g., 184.557";
    coord2Example = "e.g., -5.784";
  }

  // Time/MJD synchronization
  // Use useCallback to memoize handlers
  const syncDateTimeToMjd = useCallback((dateObj, timeStr, setMjdState) => {
    const dateWithTime = parseDateTimeStrings(
      dateObj ? format(dateObj, 'dd/MM/yyyy') : '',
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
        setDateObjState(dateObj);
        setTimeState(timeStr);
      } else {
        setDateObjState(null);
        setTimeState('');
      }
    } else {
      setDateObjState(null);
      setTimeState('');
    }
  }, []);

  const [timeWarning, setTimeWarning] = useState(''); // state for time-related warnings

  useEffect(() => {
  let cancelled = false;
  const run = async () => {
    try {
      // START side
      if (lastChangedType === 'start_mjd' && obsStartMJD) {
        const isoOut = await toIsoViaBackend(obsStartMJD, mjdScale, timeScale);
        if (!cancelled) applyIsoToDateAndTime(isoOut, setObsStartDateObj, setObsStartTime);
      } else if (obsStartDateObj && obsStartTime.trim()) {
        const iso = makeIsoFromDateAndTime(obsStartDateObj, obsStartTime);
        const mjdVal = await toMjdViaBackend(iso, timeScale, mjdScale);
        if (!cancelled) setObsStartMJD(formatMJD(mjdVal)); // toFixed(8)
      }

      // END side
      if (lastChangedType === 'end_mjd' && obsEndMJD) {
        const isoOut = await toIsoViaBackend(obsEndMJD, mjdScale, timeScale);
        if (!cancelled) applyIsoToDateAndTime(isoOut, setObsEndDateObj, setObsEndTime);
      } else if (obsEndDateObj && obsEndTime.trim()) {
        const iso = makeIsoFromDateAndTime(obsEndDateObj, obsEndTime);
        const mjdVal = await toMjdViaBackend(iso, timeScale, mjdScale);
        if (!cancelled) setObsEndMJD(formatMJD(mjdVal)); // toFixed(8)
      }
    } catch {
      if (!cancelled) setTimeWarning('Conversion failed after scale change.');
    }
  };
  run();
  return () => { cancelled = true; };
}, [timeScale, mjdScale]);

  // Effects for Synchronization
  useEffect(() => {
    if (lastChangedType === 'start_dt') {
      clearTimeout(timeInputDebounceTimer.current);

      timeInputDebounceTimer.current = setTimeout(async () => {
        setTimeWarning('');
        if (obsStartDateObj && obsStartTime.trim()) {
          // build an ISO-like string using the local calendar day + typed time
          const dayIso = format(obsStartDateObj, 'yyyy-MM-dd');
          const hhmmss = obsStartTime.trim();
          const ok = /^\d{2}:\d{2}:\d{2}$/.test(hhmmss);
          if (!ok) { setTimeWarning('Invalid Start time. Use HH:MM:SS.'); setObsStartMJD(''); return; }
          const iso = makeIsoFromDateAndTime(obsStartDateObj, hhmmss);
          try {
            const mjdVal = await toMjdViaBackend(iso, timeScale, mjdScale);
            setObsStartMJD(formatMJD(mjdVal)); // mjdVal.toFixed(8)
          } catch (e) {
            setTimeWarning('Could not convert Start Date/Time.');
            setObsStartMJD('');
          }
        } else if (!obsStartDateObj && !obsStartTime.trim()) {
          setObsStartMJD('');
        } else {
          setObsStartMJD('');
        }
      }, 750);
    }
    return () => clearTimeout(timeInputDebounceTimer.current);
  }, [obsStartDateObj, obsStartTime, lastChangedType, setObsStartMJD, timeScale, mjdScale]);

  useEffect(() => {
    if (lastChangedType === 'start_mjd') {
      clearTimeout(MJDInputDebounceTimer.current);

      MJDInputDebounceTimer.current = setTimeout(async () => {
        setTimeWarning('');
        const mjdStr = obsStartMJD.trim();
        if (mjdStr === "") {
          setObsStartDateObj(null); setObsStartTime(''); return;
        }
        const mjdNum = parseFloat(mjdStr);
        if (isNaN(mjdNum)) {
          setTimeWarning('Start MJD must be a number.');
          setObsStartDateObj(null); setObsStartTime(''); return;
        }
        try {
          const isoOut = await toIsoViaBackend(mjdNum, mjdScale, timeScale);
          applyIsoToDateAndTime(isoOut, setObsStartDateObj, setObsStartTime);
        } catch (e) {
          setTimeWarning('Start MJD conversion failed.');
          setObsStartDateObj(null); setObsStartTime('');
        }
      }, 750);
    }
    return () => clearTimeout(MJDInputDebounceTimer.current);
  }, [obsStartMJD, lastChangedType, setObsStartDateObj, setObsStartTime, timeScale, mjdScale]);

  useEffect(() => {
    if (lastChangedType === 'end_dt') {
      clearTimeout(endTimeInputDebounceTimer.current);
      endTimeInputDebounceTimer.current = setTimeout(async () => {
        setTimeWarning('');
        if (obsEndDateObj && obsEndTime.trim()) {
          const dayIso = format(obsEndDateObj, 'yyyy-MM-dd');
          const hhmmss = obsEndTime.trim();
          const ok = /^\d{2}:\d{2}:\d{2}$/.test(hhmmss);
          if (!ok) { setTimeWarning('Invalid End time. Use HH:MM:SS.'); setObsEndMJD(''); return; }
          const iso = makeIsoFromDateAndTime(obsEndDateObj, hhmmss);
          try {
            const mjdVal = await toMjdViaBackend(iso, timeScale, mjdScale);
            setObsEndMJD(formatMJD(mjdVal)); // mjdVal.toFixed(8)
          } catch (e) {
            setTimeWarning('Could not convert End Date/Time.');
            setObsEndMJD('');
          }
        } else if (!obsEndDateObj && !obsEndTime.trim()) {
          setObsEndMJD('');
        } else {
          setObsEndMJD('');
        }
      }, 750);
    }
    return () => clearTimeout(endTimeInputDebounceTimer.current);
  }, [obsEndDateObj, obsEndTime, lastChangedType, setObsEndMJD, timeScale, mjdScale]);

  useEffect(() => {
    if (lastChangedType === 'end_mjd') {
      clearTimeout(endMJDInputDebounceTimer.current);
      endMJDInputDebounceTimer.current = setTimeout(async () => {
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
        try {
          const isoOut = await toIsoViaBackend(mjdNum, mjdScale, timeScale);
          applyIsoToDateAndTime(isoOut, setObsEndDateObj, setObsEndTime);
        } catch {
          setTimeWarning('End MJD conversion failed.');
          setObsEndDateObj(null); setObsEndTime('');
        }
      }, 750);
    }
    return () => clearTimeout(endMJDInputDebounceTimer.current);
  }, [obsEndMJD, lastChangedType, setObsEndDateObj, setObsEndTime, timeScale, mjdScale]);

  useEffect(() => {
    const plain = objectName.trim();
    if (justSelected) { setJustSelected(false); return; }
    if (plain.length < 4 && !/^(m\d{1,3}|ngc\d{1,4}|ic\d{1,4})$/i.test(plain)) {
      setSuggestions([]);
    return;
    }

    clearTimeout(debounceRef.current);
    if (plain.trim() === lastAccepted.current) {
      // user hasn’t edited the field since choosing a suggestion
      setSuggestions([]);
    return;
    }
    debounceRef.current = setTimeout(() => {
      axios.get('/api/object_suggest', {
        params: {
          q:          objectName.trim(),
          use_simbad: useSimbad,
          use_ned:    useNed,
          limit:      15
        }
      })
        .then(res => setSuggestions(res.data.results || []))
        .catch(()  => setSuggestions([]));
    }, 300);                       // 300-ms debounce

    return () => clearTimeout(debounceRef.current);
  }, [objectName, useSimbad, useNed]);

  function applySuggestion(name, service) {
    setObjectName(name);
    lastAccepted.current = name.trim();

    handleResolve(name, service);
    setSuggestions([]);
    setHighlight(-1);
  };

  const handleKeyDown = (e) => {
    if (!suggestions.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight(h => (h + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight(h => (h - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter' && highlight >= 0) {
      e.preventDefault();
      const { name, service } = suggestions[highlight];
      applySuggestion(name, service);
    }
  };

  // Event Handlers
  const handleResolve = (arg, overrideService = null) => {
    const target =
      typeof arg === 'string' ? arg.trim() : objectName.trim();

    if (arg && arg.preventDefault) arg.preventDefault();
    if (!target) return;
    setIsSubmitting(true);
    setWarningMessage('');

    const mySeq = ++latestSeq.current;

    axios.post('/api/object_resolve', {
      object_name: target,
      use_simbad: overrideService
                    ? overrideService === 'SIMBAD'
                    : useSimbad,
      use_ned:    overrideService
                    ? overrideService === 'NED'
                    : useNed
    })
    .then(res => {
      if (mySeq !== latestSeq.current) return;

      const first = res.data?.results?.[0];
      if (first?.ra != null && first?.dec != null) {
        setCoordinateSystem(COORD_SYS_EQ_DEG);
        setCoord1(first.ra.toString());
        setCoord2(first.dec.toString());
        setWarningMessage(`Resolved ${target} via ${first.service}`);
      } else {
        setWarningMessage(`Could not resolve "${target}"`);
      }
    })
    .catch(err => {
      if (mySeq !== latestSeq.current) return;
      setWarningMessage(`Error resolving object: ${err.message}`);
    })
    .finally(() => {
      if (mySeq === latestSeq.current) setIsSubmitting(false);
    });
  };

  const handleCoordSystemChange = (e) => {
     setCoordinateSystem(e.target.value);
     // Clear coord inputs when system changes
     setCoord1('');
     setCoord2('');
  };

  // Handlers for Time/MJD inputs that set the 'lastChangedType'
  const handleStartDateChange = (date) => {
    setObsStartDateObj(date);
    setLastChangedType('start_dt');
    setTimeTouched(true);
  };
  const handleStartTimeChange = (e) => {
    setObsStartTime(e.target.value);
    setLastChangedType('start_dt');
    setTimeTouched(true);
  };
  const handleStartMjdChange = (e) => {
    setObsStartMJD(e.target.value);
    setLastChangedType('start_mjd');
    setTimeTouched(true);
  };

const handleEndDateChange = (date) => {
  setObsEndDateObj(date);
  setLastChangedType('end_dt');
  setTimeTouched(true);
};
const handleEndTimeChange = (e) => {
  setObsEndTime(e.target.value);
  setLastChangedType('end_dt');
  setTimeTouched(true);
};
const handleEndMjdChange = (e) => {
  setObsEndMJD(e.target.value);
  setLastChangedType('end_mjd');
  setTimeTouched(true);
};

  // handle clear form
  const handleClearForm = () => {
    setObjectName(defaultFormValues.objectName);
    setUseSimbad(defaultFormValues.useSimbad);
    setUseNed(defaultFormValues.useNed);
    setCoordinateSystem(defaultFormValues.coordinateSystem);
    setCoord1(defaultFormValues.coord1);
    setCoord2(defaultFormValues.coord2);
    setSearchRadius(defaultFormValues.searchRadius);
    setObsStartDateObj(defaultFormValues.obsStartDateObj);
    setObsStartTime(defaultFormValues.obsStartTime);
    setObsStartMJD(defaultFormValues.obsStartMJD);
    setObsEndDateObj(defaultFormValues.obsEndDateObj);
    setObsEndTime(defaultFormValues.obsEndTime);
    setObsEndMJD(defaultFormValues.obsEndMJD);
    // TAP URL and Table Name
    // setTapUrl(defaultFormValues.tapUrl);
    // setObscoreTable(defaultFormValues.obscoreTable);
    // setShowAdvanced(defaultFormValues.showAdvanced); // hide advanced

    setWarningMessage('');
    setLastChangedType(null); // Reset change tracker
    setTimeTouched(false);
    console.log("Search form cleared.");
  };

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

    if (timeTouched && timeWarning) {
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
  //let timeIsValid = false;

  const hasBothMJD  = obsStartMJD.trim() !== '' && obsEndMJD.trim() !== '';
  const hasCalendar = !!(obsStartDateObj && obsStartTime.trim() && obsEndDateObj && obsEndTime.trim());

  if (timeTouched) {
    if (hasBothMJD) {
      const startMjdNum = parseMjdInput(obsStartMJD);
      const endMjdNum   = parseMjdInput(obsEndMJD);
      if (Number.isFinite(startMjdNum) && Number.isFinite(endMjdNum)) {
        if (endMjdNum <= startMjdNum) {
          setWarningMessage("End MJD must be after Start MJD.");
          setIsSubmitting(false);
          return;
        }
        finalReqParams.mjd_start = startMjdNum;
        finalReqParams.mjd_end   = endMjdNum;
        timeIsValid = true;
      }
    } else if (hasCalendar) {
      const startDateTime = parseDateTimeStrings(
        format(obsStartDateObj, 'dd/MM/yyyy'),
        obsStartTime.trim()
      );
      const endDateTime = parseDateTimeStrings(
        format(obsEndDateObj, 'dd/MM/yyyy'),
        obsEndTime.trim()
      );

      if (!startDateTime || !endDateTime) {
        setWarningMessage("Invalid Date/Time format. Use dd/MM/yyyy and HH:mm:ss.");
        setIsSubmitting(false);
        return;
      }
      if (endDateTime <= startDateTime) {
        setWarningMessage("End Date/Time must be after Start Date/Time.");
        setIsSubmitting(false);
        return;
      }

      const mjdStartDerived = dateToMjd(startDateTime);
      const mjdEndDerived   = dateToMjd(endDateTime);
      if (mjdStartDerived != null && mjdEndDerived != null) {
        finalReqParams.mjd_start = mjdStartDerived;
        finalReqParams.mjd_end   = mjdEndDerived;
        timeIsValid = true;
      } else {
        setWarningMessage("Failed to convert valid Date/Time to MJD.");
        setIsSubmitting(false);
        return;
      }
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
                            <div className="position-relative">
                              <input
                                type="text"
                                id="objectNameInput"
                                className="form-control"
                                value={objectName}
                                onChange={e => { setObjectName(e.target.value); }}
                                onKeyDown={handleKeyDown}
                                placeholder="e.g. Crab Nebula"
                                disabled={isSubmitting}
                                autoComplete="off"
                                onBlur={() => setTimeout(() => setSuggestions([]), 150)}
                              />

                              {suggestions.length > 0 && (
                                <ul className="list-group position-absolute top-100 start-0 w-100 shadow"
                                    style={{maxHeight: '16rem', overflowY: 'auto', zIndex: 1030}}>
                                  {suggestions.map((s, idx) => (
                                    <li key={idx}
                                      className={`list-group-item list-group-item-action
                                                ${idx === highlight ? 'active' : ''}`}
                                      onClick={() => applySuggestion(s.name, s.service)}>
                                      {s.name}
                                      <span className="badge bg-secondary ms-1">{s.service}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                            <div className="input-group mt-2">
                              <button type="button" className="btn btn-secondary"
                                      disabled={!objectName || isSubmitting}
                                      onClick={() => handleResolve()}>
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
                                <div className="input-tooltip-container"> {/* Container for input and tooltip */}
                                  <input
                                    type="text"
                                    className="form-control"
                                    id="coord1Input"
                                    value={coord1}
                                    onChange={(e) => setCoord1(e.target.value)}
                                    // placeholder={coord1Placeholder}
                                    onFocus={() => setShowCoord1Tooltip(true)}
                                    onBlur={() => setShowCoord1Tooltip(false)}
                                    disabled={isSubmitting}
                                    aria-label={coord1Label}
                                    aria-describedby="coord1Tooltip" // For accessibility
                                  />
                                  {showCoord1Tooltip && (
                                    <span id="coord1Tooltip" className="input-tooltip-text" role="tooltip">
                                      {coord1Example}
                                    </span>
                                  )}
                               </div>
                            </div>
                            <div className="col-md">
                                 <label htmlFor="coord2Input" className="form-label">{coord2Label}</label>
                                 <div className="input-tooltip-container">
                                   <input
                                     type="text"
                                     className="form-control"
                                     id="coord2Input"
                                     value={coord2}
                                     onChange={(e) => setCoord2(e.target.value)}
                                     // placeholder={coord2Placeholder}
                                     onFocus={() => setShowCoord2Tooltip(true)}
                                     onBlur={() => setShowCoord2Tooltip(false)}
                                     disabled={isSubmitting}
                                     aria-label={coord2Label}
                                     aria-describedby="coord2Tooltip"
                                   />
                                   {showCoord2Tooltip && (
                                     <span id="coord2Tooltip" className="input-tooltip-text" role="tooltip">
                                       {coord2Example}
                                     </span>
                                   )}
                               </div>
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
                         <div className="row g-2 align-items-end mb-2">
                          <div className="col-md-4">
                            <label className="form-label mb-1">Time system (date/time)</label>
                            <select
                              className="form-select form-select-sm w-100"
                              value={timeScale}
                              onChange={(e) => setTimeScale(e.target.value)}
                              disabled={isSubmitting}
                            >
                              <option value="utc">UTC</option>
                              <option value="tt">TT</option>
                              {/* <option value="tai">TAI</option> */}
                            </select>
                          </div>

                          <div className="col-md-3 d-none d-md-block" />

                          <div className="col-md-5">
                            <label className="form-label mb-1">MJD scale</label>
                            <select
                              className="form-select form-select-sm w-100"
                              value={mjdScale}
                              onChange={(e) => setMjdScale(e.target.value)}
                              disabled={isSubmitting}
                            >
                              <option value="tt">TT</option>
                              <option value="utc">UTC</option>
                              {/* <option value="tai">TAI</option> */}
                            </select>
                          </div>
                        </div>
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


                {/* Action Buttons: Search and Clear */}
                <div className="d-flex justify-content-end mb-3">
                    {/* Clear Button */}
                    <button
                        type="button"
                        className="btn btn-outline-secondary me-2"
                        onClick={handleClearForm}
                        disabled={isSubmitting}
                    >
                        Clear Form
                    </button>
                    {/* Search Button */}
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
});

export default SearchForm;
