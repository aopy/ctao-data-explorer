import React, {
  useState, useEffect, useCallback, forwardRef, useImperativeHandle, useRef
} from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import {
  COORD_SYS_EQ_DEG,
  COORD_SYS_EQ_HMS,
  COORD_SYS_GAL
} from './datetimeUtils';
import './styles.css';

const FORM_STATE_SESSION_KEY = 'searchFormStateBeforeLogin';

const defaultFormValues = {
  objectName: '', useSimbad: true, useNed: false,
  coordinateSystem: COORD_SYS_EQ_DEG, coord1: '', coord2: '', searchRadius: '5',
  obsStartDateObj: null, obsStartTime: '', obsStartMJD: '',
  obsEndDateObj: null,   obsEndTime:   '', obsEndMJD:   '',
  tapUrl: 'http://voparis-tap-he.obspm.fr/tap',
  obscoreTable: 'hess_dr.obscore_sdc',
  showAdvanced: false,
};

const parseMjdInput = (v) => {
  if (v == null) return NaN;
  const s = String(v).trim().replace(/[ \u00A0_]/g, '').replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
};
const formatMJD = (x) =>
  (Number.isFinite(x) ? Number(x).toFixed(8) : '');

const ymdFromDate = (d) => {
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const SearchForm = forwardRef(({ setResults, isLoggedIn }, ref) => {

  const loadInitialState = () => {
    try {
      const saved = sessionStorage.getItem(FORM_STATE_SESSION_KEY);
      if (saved) {
        sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
        const parsed = JSON.parse(saved);
        if (parsed.obsStartDateObj) parsed.obsStartDateObj = new Date(parsed.obsStartDateObj);
        if (parsed.obsEndDateObj)   parsed.obsEndDateObj = new Date(parsed.obsEndDateObj);
        return { ...defaultFormValues, ...parsed };
      }
    } catch {
      sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
    }
    return { ...defaultFormValues };
  };

  const [initialFormState] = useState(loadInitialState);

  // Object resolve / coords
  const [objectName, setObjectName] = useState(initialFormState.objectName);
  const [useSimbad, setUseSimbad] = useState(initialFormState.useSimbad);
  const [useNed, setUseNed] = useState(initialFormState.useNed);
  const [coordinateSystem, setCoordinateSystem] = useState(initialFormState.coordinateSystem);
  const [coord1, setCoord1] = useState(initialFormState.coord1);
  const [coord2, setCoord2] = useState(initialFormState.coord2);
  const [searchRadius, setSearchRadius] = useState(initialFormState.searchRadius);

  // Time system
  const [timeScale, setTimeScale] = useState('tt'); // 'tt' | 'utc'

  // Calendar + MJD
  const [obsStartDateObj, setObsStartDateObj] = useState(initialFormState.obsStartDateObj);
  const [obsStartTime, setObsStartTime] = useState(initialFormState.obsStartTime);
  const [obsStartMJD, setObsStartMJD] = useState(initialFormState.obsStartMJD);
  const [obsEndDateObj, setObsEndDateObj] = useState(initialFormState.obsEndDateObj);
  const [obsEndTime, setObsEndTime] = useState(initialFormState.obsEndTime);
  const [obsEndMJD, setObsEndMJD] = useState(initialFormState.obsEndMJD);

  // TAP + UI
  const [tapUrl, setTapUrl] = useState(initialFormState.tapUrl);
  const [obscoreTable, setObscoreTable] = useState(initialFormState.obscoreTable);
  const [showAdvanced, setShowAdvanced] = useState(initialFormState.showAdvanced);

  const [warningMessage, setWarningMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Track if user interacted with time inputs this session
  const [timeTouched, setTimeTouched] = useState(false);
  const [lastChangedType, setLastChangedType] = useState(null); // 'start_dt' | 'start_mjd' | 'end_dt' | 'end_mjd'
  const [timeWarning, setTimeWarning] = useState('');

  // debouncers
  const startDtDebounce = useRef(null);
  const startMjdDebounce = useRef(null);
  const endDtDebounce = useRef(null);
  const endMjdDebounce = useRef(null);

  // autosuggest
  const [suggestions, setSuggestions] = useState([]);
  const [highlight, setHighlight] = useState(-1);
  const debounceRef = useRef(null);
  const latestSeq = useRef(0);
  const lastAccepted = useRef('');
  const [justSelected, setJustSelected] = useState(false);

  const [isEditingStartTime, setIsEditingStartTime] = useState(false);
  const [isEditingEndTime, setIsEditingEndTime] = useState(false);

  const isFullTime = (s) => /^\d{2}:\d{2}:\d{2}$/.test(s || '');

  // Make a display date pinned to noon UTC for the given yyyy-mm-dd
  function dateFromIsoDatePart(iso) {
    const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)); // 12:00 UTC
  }

  // Local calendar date to "YYYY-MM-DD"
  function ymdFromLocal(date) {
    if (!date) return '';
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  useImperativeHandle(ref, () => ({
    saveState: () => {
      try {
        sessionStorage.setItem(FORM_STATE_SESSION_KEY, JSON.stringify({
          objectName, useSimbad, useNed,
          coordinateSystem, coord1, coord2, searchRadius,
          obsStartDateObj: obsStartDateObj ? obsStartDateObj.toISOString() : null,
          obsStartTime, obsStartMJD,
          obsEndDateObj: obsEndDateObj ? obsEndDateObj.toISOString() : null,
          obsEndTime, obsEndMJD,
          tapUrl, obscoreTable, showAdvanced
        }));
      } catch { /* ignore */ }
    }
  }));

  // Labels
  let coord1Label = 'RA (deg)';
  let coord2Label = 'Dec (deg)';
  let coord1Example = "e.g., 83.633";
  let coord2Example = "e.g., 22.014";
  if (coordinateSystem === COORD_SYS_EQ_HMS) {
    coord1Label = 'RA (hms)'; coord2Label = 'Dec (dms)';
    coord1Example = "e.g., 05 34 31.9"; coord2Example = "e.g., +22 00 52";
  } else if (coordinateSystem === COORD_SYS_GAL) {
    coord1Label = 'l (deg)'; coord2Label = 'b (deg)';
    coord1Example = "e.g., 184.557"; coord2Example = "e.g., -5.784";
  }


  async function convertIsoToScaleMjd(iso, scale) {
    // iso like "YYYY-MM-DDThh:mm:ss"
    const { data } = await axios.post('/api/convert_time', {
      value: iso, input_format: 'isot', input_scale: scale
    });
    return {
      mjd:  scale === 'tt' ? data.tt_mjd  : data.utc_mjd,
      isot: scale === 'tt' ? data.tt_isot : data.utc_isot,
    };
  }
  async function convertMjdToScaleIso(mjd, scale) {
    const { data } = await axios.post('/api/convert_time', {
      value: String(mjd), input_format: 'mjd', input_scale: scale
    });
    return {
      mjd:  scale === 'tt' ? data.tt_mjd  : data.utc_mjd,
      isot: scale === 'tt' ? data.tt_isot : data.utc_isot,
    };
  }


  // Pick fields from /api/convert_time response for a given target scale
  const pickOut = (data, scale /* 'tt' | 'utc' */) => ({
    mjd:  scale === 'tt'  ? data.tt_mjd  : data.utc_mjd,
    isot: scale === 'tt'  ? data.tt_isot : data.utc_isot,
  });

  // Calendar -> MJD/ISO
  const syncFromCalendar = useCallback(
    async (which, srcDate, srcTime, inputScale, targetScale) => {
      try {
        if (!srcDate) return;
        const dayIso = ymdFromLocal(srcDate);  // YYYY-MM-DD (local), no TZ shift
        const iso    = `${dayIso}T${(srcTime || '00:00:00')}`;

        const { data } = await axios.post('/api/convert_time', {
          value: iso, input_format: 'isot', input_scale: inputScale
        });

        const out = pickOut(data, targetScale);
        console.log('timeConv', { which, inputScale, targetScale, outMjd: out.mjd, outIsot: out.isot });
        const newMjd = formatMJD(out.mjd);
        const t = out.isot.slice(11, 19); // HH:MM:SS
        const dateObj = dateFromIsoDatePart(out.isot);  // store as UTC date

        if (which === 'start') {
          setObsStartMJD(v => (v !== newMjd ? newMjd : v));
          setObsStartDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsStartTime(s => (s !== t ? t : s));
        } else {
          setObsEndMJD(v => (v !== newMjd ? newMjd : v));
          setObsEndDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsEndTime(s => (s !== t ? t : s));
        }
        setTimeWarning('');
      } catch {
        setTimeWarning('Could not convert calendar date/time.');
      }
    },
    []
  );

  // MJD -> MJD/ISO
  const syncFromMjd = useCallback(
    async (which, rawMjd, inputScale, targetScale) => {
      try {
        const mjdNum = parseMjdInput(rawMjd);
        if (!Number.isFinite(mjdNum)) {
          setTimeWarning(which === 'start' ? 'Start MJD must be a number.' : 'End MJD must be a number.');
          return;
        }

        const { data } = await axios.post('/api/convert_time', {
          value: String(mjdNum), input_format: 'mjd', input_scale: inputScale
        });

        const out = pickOut(data, targetScale);
        console.log('timeConv', { which, inputScale, targetScale, outMjd: out.mjd, outIsot: out.isot });
        const newMjd = formatMJD(out.mjd);
        const t = out.isot.slice(11, 19);
        const dateObj = dateFromIsoDatePart(out.isot);

        if (which === 'start') {
          setObsStartMJD(v => (v !== newMjd ? newMjd : v));
          setObsStartDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsStartTime(s => (s !== t ? t : s));
        } else {
          setObsEndMJD(v => (v !== newMjd ? newMjd : v));
          setObsEndDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsEndTime(s => (s !== t ? t : s));
        }
        setTimeWarning('');
      } catch {
        setTimeWarning('Could not convert MJD.');
      }
    },
    []
  );

  // When user edits fields, interpret and output in the current scale
  const onStartDateOrTime = () => {
    setTimeTouched(true);
    setLastChangedType('start_dt');
    clearTimeout(startDtDebounce.current);
    startDtDebounce.current = setTimeout(() => {
      // inputScale = targetScale = timeScale
      syncFromCalendar('start', obsStartDateObj, obsStartTime, timeScale, timeScale);
      setLastChangedType(null);
    }, 500);
  };

  const onStartMjd = (val) => {
    setObsStartMJD(val);
    setTimeTouched(true);
    setLastChangedType('start_mjd');
    clearTimeout(startMjdDebounce.current);
    startMjdDebounce.current = setTimeout(() => {
      syncFromMjd('start', val, timeScale, timeScale);
      setLastChangedType(null);
    }, 500);
  };

  const onEndDateOrTime = () => {
    setTimeTouched(true);
    setLastChangedType('end_dt');
    clearTimeout(endDtDebounce.current);
    endDtDebounce.current = setTimeout(() => {
      // inputScale = targetScale = timeScale
      syncFromCalendar('end', obsEndDateObj, obsEndTime, timeScale, timeScale);
      setLastChangedType(null);
    }, 500);
  };

  const onEndMjd = (val) => {
    setObsEndMJD(val);
    setTimeTouched(true);
    setLastChangedType('end_mjd');
    clearTimeout(endMjdDebounce.current);
    endMjdDebounce.current = setTimeout(() => {
      syncFromMjd('end', val, timeScale, timeScale);
      setLastChangedType(null);
    }, 500);
  };



  useEffect(() => {
    if (lastChangedType === 'start_dt') {
      if (!obsStartDateObj || !isFullTime(obsStartTime) || isEditingStartTime) return;
      clearTimeout(startDtDebounce.current);
      startDtDebounce.current = setTimeout(() => {
        syncFromCalendar('start', obsStartDateObj, obsStartTime, timeScale, timeScale);
        setLastChangedType(null);
      }, 300);
      return () => clearTimeout(startDtDebounce.current);
    }
  }, [lastChangedType, obsStartDateObj, obsStartTime, isEditingStartTime, timeScale, syncFromCalendar]);

  useEffect(() => {
    if (lastChangedType === 'start_mjd') {
      clearTimeout(startMjdDebounce.current);
      startMjdDebounce.current = setTimeout(() => {
        setTimeTouched(true);
        syncFromMjd('start', obsStartMJD, timeScale, timeScale);
        setLastChangedType(null);
      }, 500);
      return () => clearTimeout(startMjdDebounce.current);
    }
  }, [lastChangedType, obsStartMJD, syncFromMjd]);

  useEffect(() => {
    if (lastChangedType === 'end_dt') {
      if (!obsEndDateObj || !isFullTime(obsEndTime) || isEditingEndTime) return;
      clearTimeout(endDtDebounce.current);
      endDtDebounce.current = setTimeout(() => {
        syncFromCalendar('end', obsEndDateObj, obsEndTime, timeScale, timeScale);
        setLastChangedType(null);
      }, 300);
      return () => clearTimeout(endDtDebounce.current);
    }
  }, [lastChangedType, obsEndDateObj, obsEndTime, isEditingEndTime, timeScale, syncFromCalendar]);

  useEffect(() => {
    if (lastChangedType === 'end_mjd') {
      clearTimeout(endMjdDebounce.current);
      endMjdDebounce.current = setTimeout(() => {
        setTimeTouched(true);
        syncFromMjd('end', obsEndMJD, timeScale, timeScale);
        setLastChangedType(null);
      }, 500);
      return () => clearTimeout(endMjdDebounce.current);
    }
  }, [lastChangedType, obsEndMJD, syncFromMjd]);

  // When time system changes, re-express current values in the new scale
  const handleTimeScaleChange = async (e) => {
    const prev = timeScale;
    const next = e.target.value;
    setTimeScale(next);

    if (obsStartMJD) {
      await syncFromMjd('start', obsStartMJD, prev, next);
    } else if (obsStartDateObj && obsStartTime) {
      await syncFromCalendar('start', obsStartDateObj, obsStartTime, prev, next);
    }

    if (obsEndMJD) {
      await syncFromMjd('end', obsEndMJD, prev, next);
    } else if (obsEndDateObj && obsEndTime) {
      await syncFromCalendar('end', obsEndDateObj, obsEndTime, prev, next);
    }
  };

  useEffect(() => {
    if (objectName.trim()) {
      lastAccepted.current = objectName.trim();
      setJustSelected(true);
    }
  }, []);

  useEffect(() => {
    const plain = objectName.trim();
    if (justSelected) { setJustSelected(false); return; }
    if (plain.length < 4 && !/^(m\d{1,3}|ngc\d{1,4}|ic\d{1,4})$/i.test(plain)) {
      setSuggestions([]); return;
    }
    clearTimeout(debounceRef.current);
    if (plain === lastAccepted.current) { setSuggestions([]); return; }
    debounceRef.current = setTimeout(() => {
      axios.get('/api/object_suggest', {
        params: { q: objectName.trim(), use_simbad: useSimbad, use_ned: useNed, limit: 15 }
      })
        .then(res => setSuggestions(res.data.results || []))
        .catch(()  => setSuggestions([]));
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [objectName, useSimbad, useNed, justSelected]);

  function applySuggestion(name, service) {
    setObjectName(name);
    lastAccepted.current = name.trim();
    handleResolve(name, service);
    setSuggestions([]); setHighlight(-1);
  }
  const handleKeyDown = (e) => {
    if (!suggestions.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(h => (h + 1) % suggestions.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(h => (h - 1 + suggestions.length) % suggestions.length); }
    else if (e.key === 'Enter' && highlight >= 0) { e.preventDefault(); const { name, service } = suggestions[highlight]; applySuggestion(name, service); }
  };

  const handleResolve = (arg, overrideService = null) => {
    const target = typeof arg === 'string' ? arg.trim() : objectName.trim();
    if (arg && arg.preventDefault) arg.preventDefault();
    if (!target) return;
    setIsSubmitting(true); setWarningMessage('');
    const mySeq = ++latestSeq.current;
    axios.post('/api/object_resolve', {
      object_name: target,
      use_simbad: overrideService ? (overrideService === 'SIMBAD') : useSimbad,
      use_ned:    overrideService ? (overrideService === 'NED')    : useNed
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
      .catch(err => { if (mySeq !== latestSeq.current) return; setWarningMessage(`Error resolving object: ${err.message}`); })
      .finally(() => { if (mySeq === latestSeq.current) setIsSubmitting(false); });
  };

  const handleCoordSystemChange = (e) => {
    setCoordinateSystem(e.target.value);
    setCoord1(''); setCoord2('');
  };

  const handleStartDateChange = (date) => {
    setObsStartDateObj(date);
    if (!obsStartTime) setObsStartTime('00:00:00');
    setTimeTouched(true);
  };

  const handleStartTimeChange = (e) => {
  const t = e.target.value;
  setObsStartTime(t);
  setTimeTouched(true);
  if (obsStartDateObj && t.trim()) {
    setTimeout(() => {
      syncFromCalendar('start', obsStartDateObj, t, timeScale, timeScale);
    }, 0);
  }
};

// Start: MJD edit
const handleStartMjdChange = (e) => {
  const v = e.target.value;
  setObsStartMJD(v);
  setTimeTouched(true);
  if (v.trim() !== '') {
    setTimeout(() => {
      syncFromMjd('start', v, timeScale, timeScale);
    }, 0);
  }
};

// End: Calendar edits
const handleEndDateChange = (date) => {
  setObsEndDateObj(date);
  if (!obsEndTime) setObsEndTime('00:00:00');
  setTimeTouched(true);

};

const handleEndTimeChange = (e) => {
  const t = e.target.value;
  setObsEndTime(t);
  setTimeTouched(true);
  if (obsEndDateObj && t.trim()) {
    setTimeout(() => {
      syncFromCalendar('end', obsEndDateObj, t, timeScale, timeScale);
    }, 0);
  }
};

// End: MJD edit
const handleEndMjdChange = (e) => {
  const v = e.target.value;
  setObsEndMJD(v);
  setTimeTouched(true);
  if (v.trim() !== '') {
    setTimeout(() => {
      syncFromMjd('end', v, timeScale, timeScale);
    }, 0);
  }
};

  const handleClearForm = () => {
    Object.assign(
      {},
      setObjectName(defaultFormValues.objectName),
      setUseSimbad(defaultFormValues.useSimbad),
      setUseNed(defaultFormValues.useNed),
      setCoordinateSystem(defaultFormValues.coordinateSystem),
      setCoord1(defaultFormValues.coord1),
      setCoord2(defaultFormValues.coord2),
      setSearchRadius(defaultFormValues.searchRadius),
      setObsStartDateObj(defaultFormValues.obsStartDateObj),
      setObsStartTime(defaultFormValues.obsStartTime),
      setObsStartMJD(defaultFormValues.obsStartMJD),
      setObsEndDateObj(defaultFormValues.obsEndDateObj),
      setObsEndTime(defaultFormValues.obsEndTime),
      setObsEndMJD(defaultFormValues.obsEndMJD),
      setTapUrl(initialFormState.tapUrl),
      setObscoreTable(initialFormState.obscoreTable),
      setShowAdvanced(initialFormState.showAdvanced)
    );
    setWarningMessage(''); setLastChangedType(null); setTimeTouched(false); setTimeWarning('');
  };


  const handleSubmit = async (e) => {
    e.preventDefault();
    setWarningMessage(''); setIsSubmitting(true); setLastChangedType(null);

    const baseReqParams = {
      tap_url: tapUrl,
      obscore_table: obscoreTable,
      search_radius: parseFloat(searchRadius) || 5.0,
    };
    const finalReqParams = { ...baseReqParams };
    let coordsAreValid = false;
    let timeIsValid = false;

    if (timeTouched && timeWarning) {
      setWarningMessage(timeWarning); setIsSubmitting(false); return;
    }

    // coords
    const coord1Input = coord1.trim();
    const coord2Input = coord2.trim();
    if (coord1Input && coord2Input) {
      try {
        const systemForBackend =
          (coordinateSystem === COORD_SYS_EQ_HMS) ? 'hmsdms' :
          (coordinateSystem === COORD_SYS_GAL)    ? 'gal'    : 'deg';
        const parseResponse = await axios.post('/api/parse_coords', {
          coord1: coord1Input, coord2: coord2Input, system: systemForBackend
        });
        if (parseResponse.data.error) throw new Error(parseResponse.data.error);

        const { ra_deg, dec_deg, l_deg, b_deg } = parseResponse.data;
        if (coordinateSystem === COORD_SYS_GAL) {
          if (l_deg != null && b_deg != null) {
            finalReqParams.coordinate_system = COORD_SYS_GAL;
            finalReqParams.l = l_deg; finalReqParams.b = b_deg; coordsAreValid = true;
          } else throw new Error("Galactic parsing succeeded but did not return l/b degrees.");
        } else {
          if (ra_deg != null && dec_deg != null) {
            finalReqParams.coordinate_system = coordinateSystem;
            finalReqParams.ra = ra_deg; finalReqParams.dec = dec_deg; coordsAreValid = true;
          } else throw new Error("Equatorial parsing succeeded but did not return RA/Dec degrees.");
        }
      } catch (err) {
        setWarningMessage(`Coordinate Error: ${err.message || 'Parsing failed.'}`);
        setIsSubmitting(false); return;
      }
    }

    // time
    const hasBothMJD  = obsStartMJD.trim() !== '' && obsEndMJD.trim() !== '';
    const hasCalendar = !!(obsStartDateObj && obsStartTime.trim() && obsEndDateObj && obsEndTime.trim());

    if (timeTouched) {
      if (hasBothMJD) {
        const startMjdNum = parseMjdInput(obsStartMJD);
        const endMjdNum   = parseMjdInput(obsEndMJD);
        if (!Number.isFinite(startMjdNum) || !Number.isFinite(endMjdNum)) {
          setWarningMessage('MJD inputs must be numeric.'); setIsSubmitting(false); return;
        }
        if (endMjdNum <= startMjdNum) {
          setWarningMessage('End MJD must be after Start MJD.'); setIsSubmitting(false); return;
        }
        finalReqParams.mjd_start = startMjdNum;
        finalReqParams.mjd_end   = endMjdNum;
        finalReqParams.time_scale = timeScale; // inform backend which scale the MJD is in
        timeIsValid = true;
      } else if (hasCalendar) {
        try {
          const startIso = `${ymdFromDate(obsStartDateObj)}T${obsStartTime.trim()}`;
          const endIso   = `${ymdFromDate(obsEndDateObj)}T${obsEndTime.trim()}`;
          const startConv = await convertIsoToScaleMjd(startIso, timeScale);
          const endConv   = await convertIsoToScaleMjd(endIso,   timeScale);
          if (!(Number.isFinite(startConv.mjd) && Number.isFinite(endConv.mjd))) {
            throw new Error('Failed converting Date/Time to MJD.');
          }
          if (endConv.mjd <= startConv.mjd) {
            setWarningMessage('End Date/Time must be after Start Date/Time.'); setIsSubmitting(false); return;
          }
          finalReqParams.mjd_start = Number(startConv.mjd);
          finalReqParams.mjd_end   = Number(endConv.mjd);
          finalReqParams.time_scale = timeScale;
          timeIsValid = true;
        } catch (err) {
          setWarningMessage(err.message || 'Failed to convert calendar Date/Time to MJD.');
          setIsSubmitting(false); return;
        }
      }
    }

    if (!coordsAreValid && !timeIsValid) {
      setWarningMessage('Please provide valid coordinates or a complete time interval (Date+Time or MJD).');
      setIsSubmitting(false); return;
    }

    // call API
    axios.get('/api/search_coords', { params: finalReqParams })
      .then(response => setResults(response.data))
      .catch(error => {
        const errorDetail = error.response?.data?.detail || error.message || 'Unknown search error.';
        setWarningMessage(`Search failed: ${errorDetail}`);
      })
      .finally(() => { setIsSubmitting(false); setLastChangedType(null); });
  };

  return (
    <div className="row">
      <div className="col-lg-7 col-md-8">
        <form onSubmit={handleSubmit}>
          {warningMessage && (
            <div className="alert alert-warning" role="alert">{warningMessage}</div>
          )}

          {/* Cone Search */}
          <div className="card mb-3">
            <div className="card-header">Cone Search</div>
            <div className="card-body">

              {/* Object Resolve + Suggestions */}
              <div className="mb-3">
                <label htmlFor="objectNameInput" className="form-label">Source Name (optional)</label>
                <div className="position-relative">
                  <input
                    type="text"
                    id="objectNameInput"
                    className="form-control"
                    value={objectName}
                    onChange={e => setObjectName(e.target.value)}
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
                            className={`list-group-item list-group-item-action ${idx === highlight ? 'active' : ''}`}
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
                          onClick={(e) => handleResolve(e)}>
                    Resolve
                  </button>
                  <div className="form-check form-check-inline ms-3">
                    <input className="form-check-input" type="checkbox" id="useSimbadCheck"
                           checked={useSimbad} onChange={() => setUseSimbad(!useSimbad)} disabled={isSubmitting}/>
                    <label className="form-check-label" htmlFor="useSimbadCheck">SIMBAD</label>
                  </div>
                  <div className="form-check form-check-inline">
                    <input className="form-check-input" type="checkbox" id="useNedCheck"
                           checked={useNed} onChange={() => setUseNed(!useNed)} disabled={isSubmitting}/>
                    <label className="form-check-label" htmlFor="useNedCheck">NED</label>
                  </div>
                </div>
              </div>

              {/* Coords */}
              <div className="mb-3">
                <label htmlFor="coordSysSelect" className="form-label">Coordinate System</label>
                <select id="coordSysSelect" className="form-select"
                        value={coordinateSystem} onChange={handleCoordSystemChange} disabled={isSubmitting}>
                  <option value={COORD_SYS_EQ_DEG}>Equatorial (deg)</option>
                  <option value={COORD_SYS_EQ_HMS}>Equatorial (hms/dms)</option>
                  <option value={COORD_SYS_GAL}>Galactic (l/b deg)</option>
                </select>
              </div>
              <div className="row g-2 mb-3">
                <div className="col-md">
                  <label htmlFor="coord1Input" className="form-label">{coord1Label}</label>
                  <input type="text" className="form-control" id="coord1Input" value={coord1}
                         onChange={(e) => setCoord1(e.target.value)} disabled={isSubmitting}
                         aria-label={coord1Label}/>
                  <small className="text-muted">{coord1Example}</small>
                </div>
                <div className="col-md">
                  <label htmlFor="coord2Input" className="form-label">{coord2Label}</label>
                  <input type="text" className="form-control" id="coord2Input" value={coord2}
                         onChange={(e) => setCoord2(e.target.value)} disabled={isSubmitting}
                         aria-label={coord2Label}/>
                  <small className="text-muted">{coord2Example}</small>
                </div>
              </div>

              {/* Radius */}
              <div className="mb-3">
                <label htmlFor="radiusInput" className="form-label">Radius (deg)</label>
                <input type="number" className="form-control" id="radiusInput"
                       value={searchRadius} onChange={(e) => setSearchRadius(e.target.value)}
                       min="0" max="90" step="any" disabled={isSubmitting}/>
              </div>
            </div>
          </div>

          {/* Time warnings */}
          {timeWarning && (
            <div className="alert alert-sm alert-warning mt-1 mb-2 p-1" role="alert">
              {timeWarning}
            </div>
          )}

          {/* Time Search */}
          <div className="card mb-3">
            <div className="card-header">Time Search</div>
            <div className="card-body">

              {/* Single time system selector */}
              <div className="d-flex align-items-center mb-2">
                <label className="form-label me-2 mb-0">Time system:</label>
                <select
                  className="form-select form-select-sm"
                  style={{ width: 140 }}
                  value={timeScale}
                  onChange={handleTimeScaleChange}
                  disabled={isSubmitting}
                >
                  <option value="tt">TT</option>
                  <option value="utc">UTC</option>
                  {/* <option value="met">MET</option> */}
                </select>
              </div>

              {/* Start */}
              <label className="form-label">Observation Start</label>
              <div className="row g-2 mb-2">
                <div className="col-md-4">
                  <DatePicker
                    selected={obsStartDateObj}
                    onChange={handleStartDateChange}
                    dateFormat="yyyy-MM-dd"
                    placeholderText="YYYY-MM-DD"
                    className="form-control form-control-sm"
                    wrapperClassName="w-100"
                    disabled={isSubmitting}
                    showMonthDropdown
                    showYearDropdown
                    dropdownMode="select"
                  />
                </div>
                <div className="col-md-3">
                  <input
                    type="time"
                    step="1"
                    className="form-control form-control-sm"
                    value={obsStartTime}
                    onChange={(e) => {
                      const v = e.target.value;
                      const parts = v.split(':');
                      const hh = parts[0] ?? '00';
                      const mm = parts[1] ?? '00';
                      const ss = parts[2] ?? '00';
                      const norm = `${hh.padStart(2,'0')}:${mm.padStart(2,'0')}:${ss.padStart(2,'0')}`;
                      setObsStartTime(norm);
                      setTimeTouched(true);
                      setLastChangedType('start_dt');
                    }}
                    onFocus={() => setIsEditingStartTime(true)}
                    onBlur={() => { setIsEditingStartTime(false); setLastChangedType('start_dt'); }}
                    aria-label="Start time"
                    disabled={isSubmitting}
                  />
                </div>
                <div className="col-md-5">
                  <div className="input-group input-group-sm">
                    <input
                      type="text"
                      inputMode="decimal"
                      className="form-control"
                      placeholder={`Start MJD (${timeScale.toUpperCase()})`}
                      aria-label={`Start MJD in ${timeScale.toUpperCase()}`}
                      value={obsStartMJD}
                      onChange={handleStartMjdChange}
                      disabled={isSubmitting}
                    />
                    <span className="input-group-text">
                      MJD ({timeScale.toUpperCase()})
                    </span>
                  </div>
                </div>
              </div>

              {/* End */}
              <label className="form-label">Observation End</label>
              <div className="row g-2 mb-3">
                <div className="col-md-4">
                  <DatePicker
                    selected={obsEndDateObj}
                    onChange={handleEndDateChange}
                    dateFormat="yyyy-MM-dd"
                    placeholderText="YYYY-MM-DD"
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
                  <input
                    type="time"
                    step="1"
                    className="form-control form-control-sm"
                    value={obsEndTime}
                    onChange={(e) => {
                      const v = e.target.value;
                      const parts = v.split(':');
                      const hh = parts[0] ?? '00';
                      const mm = parts[1] ?? '00';
                      const ss = parts[2] ?? '00';
                      const norm = `${hh.padStart(2,'0')}:${mm.padStart(2,'0')}:${ss.padStart(2,'0')}`;
                      setObsEndTime(norm);
                      setTimeTouched(true);
                      setLastChangedType('end_dt');
                    }}
                    onFocus={() => setIsEditingEndTime(true)}
                    onBlur={() => { setIsEditingEndTime(false); setLastChangedType('end_dt'); }}
                    aria-label="End time"
                    disabled={isSubmitting}
                  />
                </div>
                <div className="col-md-5">
                  <div className="input-group input-group-sm">
                    <input
                      type="text"
                      inputMode="decimal"
                      className="form-control"
                      placeholder={`End MJD (${timeScale.toUpperCase()})`}
                      aria-label={`End MJD in ${timeScale.toUpperCase()}`}
                      value={obsEndMJD}
                      onChange={handleEndMjdChange}
                      disabled={isSubmitting}
                    />
                    <span className="input-group-text">
                      MJD ({timeScale.toUpperCase()})
                    </span>
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* Advanced */}
          <div className="mb-3">
            <button className="btn btn-link btn-sm p-0" type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)} aria-expanded={showAdvanced}>
              {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
            </button>
            {showAdvanced && (
              <div className="card card-body mt-2">
                <div className="mb-3">
                  <label htmlFor="tapUrlInput" className="form-label">TAP Server URL</label>
                  <input type="text" className="form-control" id="tapUrlInput"
                         value={tapUrl} onChange={(e) => setTapUrl(e.target.value)} disabled={isSubmitting}/>
                </div>
                <div>
                  <label htmlFor="obsCoreTableInput" className="form-label">ObsCore Table Name</label>
                  <input type="text" className="form-control" id="obsCoreTableInput"
                         value={obscoreTable} onChange={(e) => setObscoreTable(e.target.value)} disabled={isSubmitting}/>
                </div>
              </div>
            )}
          </div>

          {/* Buttons */}
          <div className="d-flex justify-content-end mb-3">
            <button type="button" className="btn btn-outline-secondary me-2"
                    onClick={handleClearForm} disabled={isSubmitting}>
              Clear Form
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? (<><span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...</>) : ('Search')}
            </button>
          </div>

        </form>
      </div>
      <div className="col-lg-5 col-md-4">
        <div className="p-3 text-center text-muted">{/* placeholder */}</div>
      </div>
    </div>
  );
});

export default SearchForm;
