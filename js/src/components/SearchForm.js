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
import { offset, flip, shift } from '@floating-ui/dom';

const FORM_STATE_SESSION_KEY = 'searchFormStateBeforeLogin';
const FORM_STATE_PERSIST_KEY = 'searchFormStatePersist';

const defaultFormValues = {
  objectName: '', useSimbad: true, useNed: false,
  coordinateSystem: COORD_SYS_EQ_DEG, coord1: '', coord2: '', searchRadius: '5',
  timeScale: 'tt',
  obsStartDateObj: null, obsStartTime: '', obsStartMJD: '',
  obsEndDateObj: null, obsEndTime: '', obsEndMJD: '',
  metStartSeconds: '',
  metEndSeconds: '',
  tapUrl: 'http://voparis-tap-he.obspm.fr/tap',
  obscoreTable: 'hess_dr.obscore_sdc',
  showAdvanced: false,

  energyMin: '',
  energyMax: '',

  trackingMode: '',
  pointingMode: '',
  obsMode: '',

  proposalId: '',
  proposalTitle: '',
  proposalContact: '',
  proposalType: '',

  moonLevel: 'Dark',
  skyBrightness: 'Dark',

  // "use" flags
  useConeSearch: true,
  useTimeSearch: true,
  useEnergySearch: false,
  useObsConfig: false,
  useObsProgram: false,
  useObsConditions: false,

  // "open" flags
  openEnergySearch: false,
  openObsConfig: false,
  openObsProgram: false,
  openObsConditions: false,
};

function safeJsonParse(str) {
  try { return JSON.parse(str); } catch { return null; }
}

function reviveDates(parsed) {
  if (!parsed || typeof parsed !== "object") return parsed;

  const out = { ...parsed };

  // restore DatePicker fields
  if (out.obsStartDateObj) out.obsStartDateObj = new Date(out.obsStartDateObj);
  if (out.obsEndDateObj) out.obsEndDateObj = new Date(out.obsEndDateObj);

  return out;
}

function serializeForStorage(state) {
  return JSON.stringify({
    ...state,
    obsStartDateObj: state.obsStartDateObj ? state.obsStartDateObj.toISOString() : null,
    obsEndDateObj: state.obsEndDateObj ? state.obsEndDateObj.toISOString() : null,
  });
}

const MJDREFI = 51910;
const MJDREFF = 7.42870370370241e-4;
const TT_MJDREF = MJDREFI + MJDREFF;
const SECS_PER_DAY = 86400;

const MET_EPOCH_ISO_UTC = "2001-01-01T00:00:00";
const MET_EPOCH_SCALE = "utc";

const formatMJD  = (x) => (Number.isFinite(x) ? Number(x).toFixed(8) : "");
const formatSecs = (x) => (Number.isFinite(x) ? Number(x).toFixed(3) : "");

const parseMjdInput = (v) => {
  if (v == null) return NaN;
  const s = String(v).trim().replace(/[ \u00A0_]/g, '').replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
};

const ymdFromDate = (d) => {
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const SearchForm = forwardRef(({ setResults, isLoggedIn }, ref) => {

  const loadInitialState = () => {
    // one-shot restore used for OIDC login flow
    try {
      const saved = sessionStorage.getItem(FORM_STATE_SESSION_KEY);
      if (saved) {
        sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
        const parsed = reviveDates(safeJsonParse(saved));
        if (parsed) return { ...defaultFormValues, ...parsed };
      }
    } catch {
      sessionStorage.removeItem(FORM_STATE_SESSION_KEY);
    }

    // persistent restore
    try {
      const savedPersist = sessionStorage.getItem(FORM_STATE_PERSIST_KEY);
      if (savedPersist) {
        const parsed = reviveDates(safeJsonParse(savedPersist));
        if (parsed) return { ...defaultFormValues, ...parsed };
      }
    } catch {
      // ignore
    }

    // default
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
  const [timeScale, setTimeScale] = useState(initialFormState.timeScale || 'tt');

  // Calendar + MJD
  const [obsStartDateObj, setObsStartDateObj] = useState(initialFormState.obsStartDateObj);
  const [obsStartTime, setObsStartTime] = useState(initialFormState.obsStartTime);
  const [obsStartMJD, setObsStartMJD] = useState(initialFormState.obsStartMJD);
  const [obsEndDateObj, setObsEndDateObj] = useState(initialFormState.obsEndDateObj);
  const [obsEndTime, setObsEndTime] = useState(initialFormState.obsEndTime);
  const [obsEndMJD, setObsEndMJD] = useState(initialFormState.obsEndMJD);

  const [metStartSeconds, setMetStartSeconds] = useState(initialFormState.metStartSeconds || '');
  const [metEndSeconds, setMetEndSeconds] = useState(initialFormState.metEndSeconds || '');

  const [energyMin, setEnergyMin] = useState(initialFormState.energyMin);
  const [energyMax, setEnergyMax] = useState(initialFormState.energyMax);

  const [trackingMode, setTrackingMode] = useState(initialFormState.trackingMode);
  const [pointingMode, setPointingMode] = useState(initialFormState.pointingMode);
  const [obsMode, setObsMode] = useState(initialFormState.obsMode);

  const [proposalId, setProposalId] = useState(initialFormState.proposalId);
  const [proposalTitle, setProposalTitle] = useState(initialFormState.proposalTitle);
  const [proposalContact, setProposalContact] = useState(initialFormState.proposalContact);
  const [proposalType, setProposalType] = useState(initialFormState.proposalType);

  const [moonLevel, setMoonLevel] = useState(initialFormState.moonLevel);
  const [skyBrightness, setSkyBrightness] = useState(initialFormState.skyBrightness);

  const [useConeSearch, setUseConeSearch] = useState(initialFormState.useConeSearch ?? true);
  const [useTimeSearch, setUseTimeSearch] = useState(initialFormState.useTimeSearch ?? true);
  const [useEnergySearch, setUseEnergySearch] = useState(initialFormState.useEnergySearch ?? false);
  const [useObsConfig, setUseObsConfig] = useState(initialFormState.useObsConfig ?? false);
  const [useObsProgram, setUseObsProgram] = useState(initialFormState.useObsProgram ?? false);
  const [useObsConditions, setUseObsConditions] = useState(initialFormState.useObsConditions ?? false);

  const [openEnergySearch, setOpenEnergySearch] = useState(initialFormState.openEnergySearch ?? false);
  const [openObsConfig, setOpenObsConfig] = useState(initialFormState.openObsConfig ?? false);
  const [openObsProgram, setOpenObsProgram] = useState(initialFormState.openObsProgram ?? false);
  const [openObsConditions, setOpenObsConditions] = useState(initialFormState.openObsConditions ?? false);

  const energyHasAny = (String(energyMin || '').trim() !== '') || (String(energyMax || '').trim() !== '');
  const obsConfigHasAny = !!(trackingMode || pointingMode || obsMode);
  const obsProgramHasAny = !!(String(proposalId || '').trim() || String(proposalTitle || '').trim() || String(proposalContact || '').trim() || proposalType);

  // Only consider conditions "filled" if user changed away from defaults
  const obsConditionsHasAny =
    (moonLevel !== defaultFormValues.moonLevel) ||
    (skyBrightness !== defaultFormValues.skyBrightness);

  const energyUsed = useEnergySearch;
  const obsConfigActive = useObsConfig || obsConfigHasAny;
  const obsProgramActive = useObsProgram || obsProgramHasAny;
  const obsConditionsActive = useObsConditions || obsConditionsHasAny;

  // TAP + UI
  const [tapUrl, setTapUrl] = useState(initialFormState.tapUrl);
  const [obscoreTable, setObscoreTable] = useState(initialFormState.obscoreTable);
  const [showAdvanced, setShowAdvanced] = useState(initialFormState.showAdvanced);

  const persistDebounceRef = useRef(null);
  const didHydrateRef = useRef(false);

  const persistNow = useCallback(() => {
    try {
      const snapshot = {
        objectName, useSimbad, useNed,
        coordinateSystem, coord1, coord2, searchRadius,
        timeScale,
        obsStartDateObj: obsStartDateObj ? obsStartDateObj : null,
        obsStartTime, obsStartMJD,
        obsEndDateObj: obsEndDateObj ? obsEndDateObj : null,
        obsEndTime, obsEndMJD,
        metStartSeconds, metEndSeconds,
        tapUrl, obscoreTable, showAdvanced,
        energyMin, energyMax,
        trackingMode, pointingMode, obsMode,
        proposalId, proposalTitle, proposalContact, proposalType,
        moonLevel, skyBrightness,
        useConeSearch, useTimeSearch,
        useEnergySearch, useObsConfig, useObsProgram, useObsConditions,
        openEnergySearch, openObsConfig, openObsProgram, openObsConditions,
      };
      sessionStorage.setItem(FORM_STATE_PERSIST_KEY, serializeForStorage(snapshot));
    } catch {
      // ignore
    }
  }, [
    objectName, useSimbad, useNed,
    coordinateSystem, coord1, coord2, searchRadius,
    timeScale,
    obsStartDateObj, obsStartTime, obsStartMJD,
    obsEndDateObj, obsEndTime, obsEndMJD,
    metStartSeconds, metEndSeconds,
    tapUrl, obscoreTable, showAdvanced,
    energyMin, energyMax,
    trackingMode, pointingMode, obsMode,
    proposalId, proposalTitle, proposalContact, proposalType,
    moonLevel, skyBrightness,
    useConeSearch, useTimeSearch,
    useEnergySearch, useObsConfig, useObsProgram, useObsConditions,
    openEnergySearch, openObsConfig, openObsProgram, openObsConditions,
  ]);

  // mark hydrated on first render
  useEffect(() => {
    didHydrateRef.current = true;
  }, []);

  useEffect(() => {
    if (!didHydrateRef.current) return;

    // debounce writes to avoid constant sessionStorage updates
    if (persistDebounceRef.current) clearTimeout(persistDebounceRef.current);

    persistDebounceRef.current = setTimeout(() => {
      persistNow();
    }, 250);

    return () => {
      if (persistDebounceRef.current) clearTimeout(persistDebounceRef.current);
    };
  }, [
    objectName, useSimbad, useNed,
    coordinateSystem, coord1, coord2, searchRadius,
    timeScale,
    obsStartDateObj, obsStartTime, obsStartMJD,
    obsEndDateObj, obsEndTime, obsEndMJD,
    metStartSeconds, metEndSeconds,
    tapUrl, obscoreTable, showAdvanced,
    energyMin, energyMax,
    trackingMode, pointingMode, obsMode,
    proposalId, proposalTitle, proposalContact, proposalType,
    moonLevel, skyBrightness,
    useConeSearch, useTimeSearch,
    useEnergySearch, useObsConfig, useObsProgram, useObsConditions,
    openEnergySearch, openObsConfig, openObsProgram, openObsConditions,
  ]);

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

  // const [metEpochIso, setMetEpochIso] = useState(initialFormState.metEpochIso);

  const [isEditingStartMjd, setIsEditingStartMjd] = useState(false);
  const [isEditingEndMjd,   setIsEditingEndMjd]   = useState(false);

  const isFullTime = (s) => /^\d{2}:\d{2}:\d{2}$/.test(s || '');

  function ttMjdToMetSeconds(ttMjd) {
    return (Number(ttMjd) - TT_MJDREF) * SECS_PER_DAY;
  }
  function metSecondsToTtMjd(sec) {
    return TT_MJDREF + (Number(sec) || 0) / SECS_PER_DAY;
  }

  const timeModeRef = useRef('auto'); // 'auto' | 'calendar' | 'mjd' | 'met'
  const setTimeMode = (mode) => { timeModeRef.current = mode; };

  // for using enter
  const startTimeRef = useRef(null);
  const endTimeRef = useRef(null);
  const formRef = useRef(null);
  const objectNameInputRef = useRef(null)

  const handleFormKeyDownCapture = (e) => {
    if (e.key !== 'Enter') return;
    if (isSubmitting) {
      e.preventDefault();
      return;
    }
    // if Enter pressed in Advanced Settings input, don't submit immediately
    if (target?.id === 'obsCoreTableInput' || target?.id === 'tapUrlInput') {
      e.preventDefault();
      target.blur();
      submitViaEnter(); // after blur, state will be updated
      return;
    }
    const target = e.target;

    if (target === objectNameInputRef.current) {
      if (suggestions.length > 0 && highlight >= 0) return;
      e.preventDefault();
      e.stopPropagation();
      handleResolve(objectName, null);
      return;
    }

    // if we're inside Time Search, do not submit
    // let the field's own onKeyDown handler run
    if (target?.closest?.('[data-enter-scope="time"]')) {
      // if a calendar popup is open, let DatePicker handle Enter normally
      if (startCalOpen || endCalOpen) return;

      // prevent native submit, but don't stop propagation
      e.preventDefault();
      return;
    }

    // everywhere else: Enter = Search
    e.preventDefault();
    e.stopPropagation();
    submitViaEnter();
  };


  const submitViaEnter = () => {
    const formEl = formRef.current;
    if (!formEl) return;
    if (typeof formEl.requestSubmit === "function") formEl.requestSubmit();
    else formEl.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  };

  const flushTimeDebounces = () => {
    // cancel pending timers so they don’t run after submit
    [startDtDebounce, startMjdDebounce, endDtDebounce, endMjdDebounce].forEach((r) => {
      if (r.current) {
        clearTimeout(r.current);
        r.current = null;
      }
    });
  };

  const forceCalendarSyncNow = async (which) => {
    const dateObj = which === 'start' ? obsStartDateObj : obsEndDateObj;
    const t = (which === 'start' ? obsStartTime : obsEndTime) || '00:00:00';

    if (!dateObj || !isFullTime(t)) return;
    await syncFromCalendar(which, dateObj, t, timeScale, timeScale);
  };

  const forceMjdSyncNow = async (which) => {
    const mjd = which === 'start' ? obsStartMJD : obsEndMJD;
    if (!String(mjd || '').trim()) return;
    await syncFromMjd(which, mjd, timeScale, timeScale);
  };

  const forceMetSyncNow = async (which) => {
    const sec = which === 'start' ? metStartSeconds : metEndSeconds;
    if (!String(sec || '').trim()) return;

    // Use existing convertMetTo()
    const conv = await convertMetTo(timeScale, Number(sec));
    if (which === 'start') {
      setObsStartMJD(formatMJD(conv.mjd));
      setObsStartDateObj(dateFromIsoDatePart(conv.isot));
      setObsStartTime(conv.isot.slice(11, 19));
    } else {
      setObsEndMJD(formatMJD(conv.mjd));
      setObsEndDateObj(dateFromIsoDatePart(conv.isot));
      setObsEndTime(conv.isot.slice(11, 19));
    }
    setTimeWarning('');
  };

  const [startCalOpen, setStartCalOpen] = useState(false);
  const [endCalOpen, setEndCalOpen] = useState(false);

  const handleEnterSearchFromTimeField = (e, which) => {
    if (e.key !== "Enter") return;
    if (isSubmitting) {
      e.preventDefault();
      return;
    }

    if (which === "startDate" && startCalOpen) return;
    if (which === "endDate" && endCalOpen) return;

    e.preventDefault();
    e.stopPropagation();

    // force blur so editing flags / onBlur logic settle
    e.currentTarget?.blur?.();

    // cancel pending conversions
    flushTimeDebounces();

    // force an immediate conversion depending on where Enter happened
    (async () => {
      try {
        if (which === "startTime" || which === "startDate") await forceCalendarSyncNow('start');
        if (which === "endTime"   || which === "endDate")   await forceCalendarSyncNow('end');

        if (which === "startMjd") await forceMjdSyncNow('start');
        if (which === "endMjd")   await forceMjdSyncNow('end');

        if (which === "startMet") await forceMetSyncNow('start');
        if (which === "endMet")   await forceMetSyncNow('end');
      } catch {
        // don't block submit, handleSubmit will validate and show a message if needed
      } finally {
        // submit after the forced conversion completes
      submitViaEnter();
    }
    })();
  };

  // helper: calendar -> MJD/MET in the current scale (tt/utc)
  const applyCalendarChange = async (which, dateObj, currentTime) => {
    if (!dateObj) return;

    // Normalize time: default to 00:00:00
    const t = /^\d{2}:\d{2}:\d{2}$/.test(currentTime || '') ? currentTime : '00:00:00';

    if (which === 'start') {
      setObsStartDateObj(dateObj);
      setObsStartTime(t);
    } else {
      setObsEndDateObj(dateObj);
      setObsEndTime(t);
    }

    setTimeTouched(true);
    setTimeWarning('');

    // immediately convert
    try {
      await syncFromCalendar(which, dateObj, t, timeScale, timeScale);
    } catch {
      setTimeWarning('Could not convert calendar date/time.');
      }
    };

  const handleStartDateChange = (date) => { setTimeMode('calendar'); applyCalendarChange('start', date, obsStartTime); };
  const handleEndDateChange = (date) => { setTimeMode('calendar'); applyCalendarChange('end', date, obsEndTime); };


  async function convertMetTo(targetScale, seconds) {
  const { data } = await axios.post('/api/convert_time', {
    value: String(seconds),
    input_format: 'met',
    input_scale: 'utc',
    met_epoch_isot: MET_EPOCH_ISO_UTC,
    met_epoch_scale: MET_EPOCH_SCALE
  });

  return {
    isot: targetScale === 'tt' ? data.tt_isot  : data.utc_isot,
    mjd:  targetScale === 'tt' ? data.tt_mjd   : data.utc_mjd,
    tt_mjd: data.tt_mjd,
    };
  }

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
          timeScale,
          obsStartDateObj: obsStartDateObj ? obsStartDateObj.toISOString() : null,
          obsStartTime, obsStartMJD,
          obsEndDateObj: obsEndDateObj ? obsEndDateObj.toISOString() : null,
          obsEndTime, obsEndMJD,
          metStartSeconds, metEndSeconds,
          tapUrl, obscoreTable, showAdvanced,
          energyMin, energyMax,
          trackingMode, pointingMode, obsMode,
          proposalId, proposalTitle, proposalContact, proposalType,
          moonLevel, skyBrightness,
          useConeSearch, useTimeSearch,
          useEnergySearch, useObsConfig, useObsProgram, useObsConditions,
          openEnergySearch, openObsConfig, openObsProgram, openObsConditions,
        }));
      } catch { /* ignore */ }
    }
  }));

  // Labels
  let coord1Label = 'RA (deg)';
  let coord2Label = 'Dec (deg)';
  let coord1Example = "e.g., 83.6324";
  let coord2Example = "e.g., 22.0174";
  if (coordinateSystem === COORD_SYS_EQ_HMS) {
    coord1Label = 'RA (hms)'; coord2Label = 'Dec (dms)';
    coord1Example = "e.g., 05 34 31.8"; coord2Example = "e.g., +22 01 03";
  } else if (coordinateSystem === COORD_SYS_GAL) {
    coord1Label = 'l (deg)'; coord2Label = 'b (deg)';
    coord1Example = "e.g., 184.55462"; coord2Example = "e.g., -5.783208";
  }

  const systemForBackend = (sys) =>
  (sys === COORD_SYS_EQ_HMS) ? 'hmsdms' :
  (sys === COORD_SYS_GAL) ? 'gal' : 'deg';

  const fmtDeg = (x, digits = 6) =>
    (Number.isFinite(Number(x)) ? Number(x).toFixed(digits) : '');

  const applyConvertedToTarget = (conv, targetSystem) => {
    if (targetSystem === COORD_SYS_EQ_DEG) {
      setCoord1(fmtDeg(conv.ra_deg, 6));
      setCoord2(fmtDeg(conv.dec_deg, 6));
    } else if (targetSystem === COORD_SYS_EQ_HMS) {
      setCoord1(conv.ra_hms || '');
      setCoord2(conv.dec_dms || '');
    } else if (targetSystem === COORD_SYS_GAL) {
      setCoord1(fmtDeg(conv.l_deg, 6));
      setCoord2(fmtDeg(conv.b_deg, 6));
    }
  };

  const switchCoordinateSystem = async (targetSystem) => {
  if (targetSystem === coordinateSystem) return;

  const c1 = (coord1 || '').trim();
  const c2 = (coord2 || '').trim();

  // if nothing to convert, switch labels/system and keep empty inputs
  if (!c1 || !c2) {
    setCoordinateSystem(targetSystem);
    return;
  }

  try {
    // Convert from current system to all representations
    const { data } = await axios.post('/api/convert_coords', {
      coord1: c1,
      coord2: c2,
      system: systemForBackend(coordinateSystem),
    });

    if (data?.error) throw new Error(data.error);

    // Switch and fill
    setCoordinateSystem(targetSystem);
    applyConvertedToTarget(data, targetSystem);
    setWarningMessage('');
    } catch (err) {
      setWarningMessage(`Coordinate Error: ${err?.message || 'Could not convert coordinates.'}`);
      // optional: do not switch if conversion failed
    }
  };

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

  const syncFromCalendar = useCallback(
    async (which, srcDate, srcTime, inputScale, targetScale) => {
      try {
        if (!srcDate) return;
        const y = srcDate.getFullYear();
        const m = String(srcDate.getMonth() + 1).padStart(2, '0');
        const d = String(srcDate.getDate()).padStart(2, '0');
        const iso = `${y}-${m}-${d}T${(srcTime || '00:00:00')}`;

        const { data } = await axios.post('/api/convert_time', {
          value: iso, input_format: 'isot', input_scale: inputScale
        });

        const ttMjd = data.tt_mjd;

        const outMjd  = targetScale === 'tt' ? data.tt_mjd  : data.utc_mjd;
        const outIsot = targetScale === 'tt' ? data.tt_isot : data.utc_isot;

        const out = pickOut(data, targetScale);
        const newMjd = formatMJD(out.mjd);
        const t = out.isot.slice(11, 19);
        const dateObj = dateFromIsoDatePart(out.isot);

        // compute MET seconds from TT MJD
        const metSec = ttMjdToMetSeconds(data.tt_mjd);

        if (which === 'start') {
          setObsStartMJD(v => (v !== newMjd ? newMjd : v));
          setObsStartDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsStartTime(s => (s !== t ? t : s));
          setMetStartSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
        } else {
          setObsEndMJD(v => (v !== newMjd ? newMjd : v));
          setObsEndDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsEndTime(s => (s !== t ? t : s));
          setMetEndSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
      }
        setTimeWarning('');
      } catch {
        setTimeWarning('Could not convert calendar date/time.');
      }
    },
    []
  );

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

        // pick the visible scale for calendar display
        const out = pickOut(data, targetScale);
        const tIso = out.isot;
        const dateObj = dateFromIsoDatePart(tIso);

        // TT MJD for MET computation
        const ttMjd = data.tt_mjd;
        const met = formatSecs(ttMjdToMetSeconds(ttMjd));

        if (which === 'start') {
          setObsStartDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsStartTime(s => (s !== tIso.slice(11, 19) ? tIso.slice(11, 19) : s));
          setMetStartSeconds(met);
        } else {
          setObsEndDateObj(d => (!d || d.getTime() !== dateObj.getTime() ? dateObj : d));
          setObsEndTime(s => (s !== tIso.slice(11, 19) ? tIso.slice(11, 19) : s));
          setMetEndSeconds(met);
        }
        setTimeWarning('');
      } catch {
        setTimeWarning('Could not convert MJD.');
      }
    },
    []
  );

  const handleMetStartChange = async (e) => {
    setTimeMode('met');
    const v = e.target.value;
    setMetStartSeconds(v);
    if (!v.trim()) return;
    setTimeTouched(true);
    try {
      const conv = await convertMetTo(timeScale, Number(v));
      setObsStartMJD(formatMJD(conv.mjd));
      setObsStartDateObj(dateFromIsoDatePart(conv.isot));
      setObsStartTime(conv.isot.slice(11,19));
    } catch {
      setTimeWarning('Could not convert MET start.');
    }
  };

  const handleMetEndChange = async (e) => {
    setTimeMode('met');
    const v = e.target.value;
    setMetEndSeconds(v);
    if (!v.trim()) return;
    setTimeTouched(true);
    try {
      const conv = await convertMetTo(timeScale, Number(v));
      setObsEndMJD(formatMJD(conv.mjd));
      setObsEndDateObj(dateFromIsoDatePart(conv.isot));
      setObsEndTime(conv.isot.slice(11,19));
    } catch {
      setTimeWarning('Could not convert MET end.');
    }
  };

  async function syncFromMet(rawSec, epochIso, targetScale='tt') {
    const { data } = await axios.post('/api/convert_time', {
      value: String(rawSec),
      input_format: 'met',
      input_scale: 'utc',
      met_epoch_isot: epochIso,
      met_epoch_scale: 'tt'
    });
    const out = pickOut(data, targetScale);
    return { mjd: out.mjd, isot: out.isot };
  }

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

    // convert current start fields
    if (obsStartMJD) {
      const { data } = await axios.post('/api/convert_time', {
        value: String(parseMjdInput(obsStartMJD)),
        input_format: 'mjd',
        input_scale: prev
      });
      const outMjd  = next === 'tt' ? data.tt_mjd  : data.utc_mjd;
      const outIsot = next === 'tt' ? data.tt_isot : data.utc_isot;

      setObsStartMJD(formatMJD(outMjd));
      setObsStartDateObj(dateFromIsoDatePart(outIsot));
      setObsStartTime(outIsot.slice(11,19));

      // keep MET synced from TT MJD
      setMetStartSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
    } else if (obsStartDateObj && obsStartTime) {
      await syncFromCalendar('start', obsStartDateObj, obsStartTime, prev, next);
      // syncFromCalendar writes MJD in the target scale
      const { data } = await axios.post('/api/convert_time', {
        value: `${ymdFromDate(obsStartDateObj)}T${obsStartTime}`,
        input_format: 'isot',
        input_scale: next
      });
      setMetStartSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
    }

    // convert current END fields
    if (obsEndMJD) {
      const { data } = await axios.post('/api/convert_time', {
        value: String(parseMjdInput(obsEndMJD)),
        input_format: 'mjd',
        input_scale: prev
      });
      const outMjd  = next === 'tt' ? data.tt_mjd  : data.utc_mjd;
      const outIsot = next === 'tt' ? data.tt_isot : data.utc_isot;

      setObsEndMJD(formatMJD(outMjd));
      setObsEndDateObj(dateFromIsoDatePart(outIsot));
      setObsEndTime(outIsot.slice(11,19));

      // keep MET (seconds) synced from TT MJD
      setMetEndSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
    } else if (obsEndDateObj && obsEndTime) {
      await syncFromCalendar('end', obsEndDateObj, obsEndTime, prev, next);
      const { data } = await axios.post('/api/convert_time', {
        value: `${ymdFromDate(obsEndDateObj)}T${obsEndTime}`,
        input_format: 'isot',
        input_scale: next
      });
      setMetEndSeconds(formatSecs(ttMjdToMetSeconds(data.tt_mjd)));
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

  const handleResolve = async (arg, overrideService = null) => {
  const target = typeof arg === 'string' ? arg.trim() : objectName.trim();
  if (arg && arg.preventDefault) arg.preventDefault();
  if (!target) return;

  // prevent suggestions reopening after a successful resolve
  clearTimeout(debounceRef.current);
  setSuggestions([]);
  setHighlight(-1);
  lastAccepted.current = target;

  setIsSubmitting(true);
  setWarningMessage('');

  const mySeq = ++latestSeq.current;

  try {
    const res = await axios.post('/api/object_resolve', {
      object_name: target,
      use_simbad: overrideService ? (overrideService === 'SIMBAD') : useSimbad,
      use_ned: overrideService ? (overrideService === 'NED') : useNed
    });

    if (mySeq !== latestSeq.current) return;

    const first = res.data?.results?.[0];
    if (first?.ra != null && first?.dec != null) {
      try {
        const convRes = await axios.post('/api/convert_coords', {
          coord1: String(first.ra),
          coord2: String(first.dec),
          system: 'deg',
        });

        if (mySeq !== latestSeq.current) return;

        if (convRes.data?.error) throw new Error(convRes.data.error);

        applyConvertedToTarget(convRes.data, coordinateSystem);
      } catch {
        // fallback: just put degrees
        setCoordinateSystem(COORD_SYS_EQ_DEG);
        setCoord1(String(first.ra));
        setCoord2(String(first.dec));
      }

      setWarningMessage(`Resolved ${target} via ${first.service}`);
    } else {
      setWarningMessage(`Could not resolve "${target}"`);
    }
    } catch (err) {
      if (mySeq !== latestSeq.current) return;
      setWarningMessage(`Error resolving object: ${err?.message || 'Unknown error'}`);
    } finally {
      if (mySeq === latestSeq.current) setIsSubmitting(false);
    }
  };

  const handleCoordSystemChange = (e) => {
    setCoordinateSystem(e.target.value);
    setCoord1(''); setCoord2('');
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

// MJD edit
const handleStartMjdChange = (e) => {
  setTimeMode('mjd');
  const v = e.target.value;
  setObsStartMJD(v);
  setTimeTouched(true);
  clearTimeout(startMjdDebounce.current);
  startMjdDebounce.current = setTimeout(() => {
    syncFromMjd('start', v, timeScale, timeScale); // update calendar+MET only
  }, 500);
};

const handleStartMjdBlur = async () => {
  const mjdNum = parseMjdInput(obsStartMJD);
  if (!Number.isFinite(mjdNum)) return;
  const { data } = await axios.post('/api/convert_time', {
    value: String(mjdNum), input_format: 'mjd', input_scale: timeScale
  });
  const out = pickOut(data, timeScale);
  setObsStartMJD(formatMJD(out.mjd));
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

const handleEndMjdChange = (e) => {
  setTimeMode('mjd');
  const v = e.target.value;
  setObsEndMJD(v);
  setTimeTouched(true);
  clearTimeout(endMjdDebounce.current);
  endMjdDebounce.current = setTimeout(() => {
    syncFromMjd('end', v, timeScale, timeScale);
  }, 500);
};

const handleEndMjdBlur = async () => {
  const mjdNum = parseMjdInput(obsEndMJD);
  if (!Number.isFinite(mjdNum)) return;
  const { data } = await axios.post('/api/convert_time', {
    value: String(mjdNum), input_format: 'mjd', input_scale: timeScale
  });
  const out = pickOut(data, timeScale);
  setObsEndMJD(formatMJD(out.mjd));
};


const handleClearForm = () => {
  // core fields
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

  setTapUrl(defaultFormValues.tapUrl);
  setObscoreTable(defaultFormValues.obscoreTable);
  setShowAdvanced(defaultFormValues.showAdvanced);

  // optional fields
  setEnergyMin(defaultFormValues.energyMin);
  setEnergyMax(defaultFormValues.energyMax);

  setTrackingMode(defaultFormValues.trackingMode);
  setPointingMode(defaultFormValues.pointingMode);
  setObsMode(defaultFormValues.obsMode);

  setProposalId(defaultFormValues.proposalId);
  setProposalTitle(defaultFormValues.proposalTitle);
  setProposalContact(defaultFormValues.proposalContact);
  setProposalType(defaultFormValues.proposalType);

  setMoonLevel(defaultFormValues.moonLevel);
  setSkyBrightness(defaultFormValues.skyBrightness);

  // use flags
  setUseConeSearch(defaultFormValues.useConeSearch);
  setUseTimeSearch(defaultFormValues.useTimeSearch);
  setUseEnergySearch(defaultFormValues.useEnergySearch);
  setUseObsConfig(defaultFormValues.useObsConfig);
  setUseObsProgram(defaultFormValues.useObsProgram);
  setUseObsConditions(defaultFormValues.useObsConditions);

  // open flags
  setOpenEnergySearch(defaultFormValues.openEnergySearch);
  setOpenObsConfig(defaultFormValues.openObsConfig);
  setOpenObsProgram(defaultFormValues.openObsProgram);
  setOpenObsConditions(defaultFormValues.openObsConditions);

  // time-mode + met + warnings
  setTimeMode('auto');
  setMetStartSeconds('');
  setMetEndSeconds('');
  setWarningMessage('');
  setLastChangedType(null);
  setTimeTouched(false);
  setTimeWarning('');

  try { sessionStorage.removeItem(FORM_STATE_PERSIST_KEY); } catch {}
};


  const handleSubmit = async (e) => {
    e.preventDefault();

    persistNow();
    setWarningMessage('');
    setIsSubmitting(true);
    setLastChangedType(null);

    const baseReqParams = {
      tap_url: tapUrl,
      obscore_table: obscoreTable,
      search_radius: parseFloat(searchRadius) || 5.0,
    };
    const finalReqParams = { ...baseReqParams };
    let coordsAreValid = false;
    let timeIsValid = false;

    if (timeWarning) {
      setWarningMessage(timeWarning);
      setIsSubmitting(false);
      return;
    }

    if (useConeSearch) {
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
    }

    // time
    if (useTimeSearch) {
    const hasBothMJD  = obsStartMJD.trim() !== '' && obsEndMJD.trim() !== '';
    const hasCalendar = !!(obsStartDateObj && obsStartTime.trim() && obsEndDateObj && obsEndTime.trim());
    const hasBothMET  = metStartSeconds.trim() !== '' && metEndSeconds.trim() !== '';

    let mode = timeModeRef.current;

    // fallback if auto or if the chosen mode isn't actually complete
    if (mode === 'auto') {
      if (hasCalendar) mode = 'calendar';
      else if (hasBothMJD) mode = 'mjd';
      else if (hasBothMET) mode = 'met';
    } else {
      if (mode === 'calendar' && !hasCalendar) mode = hasBothMJD ? 'mjd' : (hasBothMET ? 'met' : 'auto');
      if (mode === 'mjd' && !hasBothMJD)  mode = hasCalendar ? 'calendar' : (hasBothMET ? 'met' : 'auto');
      if (mode === 'met' && !hasBothMET)  mode = hasCalendar ? 'calendar' : (hasBothMJD ? 'mjd' : 'auto');
    }


    // time: choose branch by mode (calendar/mjd/met)
    try {
      if (mode === 'calendar') {
        if (!hasCalendar) {
          throw new Error('Please provide a complete calendar time interval (Start+End Date/Time).');
        }

        const startIso = `${ymdFromDate(obsStartDateObj)}T${obsStartTime.trim()}`;
        const endIso = `${ymdFromDate(obsEndDateObj)}T${obsEndTime.trim()}`;

        const startConv = await convertIsoToScaleMjd(startIso, timeScale);
        const endConv = await convertIsoToScaleMjd(endIso, timeScale);

        const startMjd = Number(startConv.mjd);
        const endMjd = Number(endConv.mjd);

        if (!Number.isFinite(startMjd) || !Number.isFinite(endMjd)) {
          throw new Error('Failed converting Date/Time to MJD.');
        }
        if (endMjd <= startMjd) {
          throw new Error('End Date/Time must be after Start Date/Time.');
        }

        finalReqParams.mjd_start = startMjd;
        finalReqParams.mjd_end = endMjd;
        finalReqParams.time_scale = timeScale;
        timeIsValid = true;

      } else if (mode === 'mjd') {
        if (!hasBothMJD) {
          throw new Error('Please provide both Start and End MJD.');
        }

        const startMjdNum = parseMjdInput(obsStartMJD);
        const endMjdNum = parseMjdInput(obsEndMJD);

        if (!Number.isFinite(startMjdNum) || !Number.isFinite(endMjdNum)) {
          throw new Error('MJD inputs must be numeric.');
        }
        if (endMjdNum <= startMjdNum) {
          throw new Error('End MJD must be after Start MJD.');
        }

        finalReqParams.mjd_start  = startMjdNum;
        finalReqParams.mjd_end    = endMjdNum;
        finalReqParams.time_scale = timeScale;
        timeIsValid = true;

      } else if (mode === 'met') {
        if (!hasBothMET) {
          throw new Error('Please provide both Start and End MET seconds.');
        }

        // Convert MET → TT MJD (query is in TT)
        const startConv = await axios.post('/api/convert_time', {
          value: metStartSeconds,
          input_format: 'met',
          input_scale: 'utc',
          met_epoch_isot: MET_EPOCH_ISO_UTC,
          met_epoch_scale: MET_EPOCH_SCALE,
        });

        const endConv = await axios.post('/api/convert_time', {
          value: metEndSeconds,
          input_format: 'met',
          input_scale: 'utc',
          met_epoch_isot: MET_EPOCH_ISO_UTC,
          met_epoch_scale: MET_EPOCH_SCALE,
        });

        const startTtMjd = Number(startConv.data.tt_mjd);
        const endTtMjd = Number(endConv.data.tt_mjd);

        if (!Number.isFinite(startTtMjd) || !Number.isFinite(endTtMjd)) {
          throw new Error('Failed converting MET to TT MJD.');
        }
        if (endTtMjd <= startTtMjd) {
          throw new Error('End MET must be after Start MET.');
        }

        finalReqParams.mjd_start = startTtMjd;
        finalReqParams.mjd_end = endTtMjd;
        finalReqParams.time_scale = 'tt';
        timeIsValid = true;

        } else {
          // mode === 'auto' and nothing complete
          timeIsValid = false;
        }
    } catch (err) {
      setWarningMessage(err?.message || 'Invalid time interval.');
      setIsSubmitting(false);
      return;
    }
    }

    const energyHasAny =
      (String(energyMin || '').trim() !== '') ||
      (String(energyMax || '').trim() !== '');

    const energyProvided = useEnergySearch && energyHasAny;

    const obsConfigProvided =
      obsConfigActive && (trackingMode || pointingMode || obsMode);

    const obsProgramProvided =
      obsProgramActive &&
      (String(proposalId || '').trim() ||
       String(proposalTitle || '').trim() ||
       String(proposalContact || '').trim() ||
       proposalType);

    const obsConditionsProvided = obsConditionsActive;

    const hasAnyCriteria =
      (useConeSearch && coordsAreValid) ||
      (useTimeSearch && timeIsValid) ||
      energyProvided ||
      obsConfigProvided ||
      obsProgramProvided ||
      obsConditionsProvided;


    if (!hasAnyCriteria) {
      setWarningMessage('Please provide at least one search criterion (Cone, Time, Energy, Program, Config, or Conditions).');
      setIsSubmitting(false);
      return;
    }

    // Optional filters (only if section is active)
    if (useEnergySearch) {
      if (energyMin.trim() !== '') finalReqParams.energy_min = Number(energyMin);
      if (energyMax.trim() !== '') finalReqParams.energy_max = Number(energyMax);
    }

    if (obsConfigActive) {
      if (trackingMode) finalReqParams.tracking_mode = trackingMode;
      if (pointingMode) finalReqParams.pointing_mode = pointingMode;
      if (obsMode) finalReqParams.obs_mode = obsMode;
    }

    if (obsProgramActive) {
      if (proposalId.trim()) finalReqParams.proposal_id = proposalId.trim();
      if (proposalTitle.trim()) finalReqParams.proposal_title = proposalTitle.trim();
      if (proposalContact.trim()) finalReqParams.proposal_contact = proposalContact.trim();
      if (proposalType) finalReqParams.proposal_type = proposalType;
    }

    if (obsConditionsActive) {
      finalReqParams.moon_level = moonLevel;
      finalReqParams.sky_brightness = skyBrightness;
    }

    // call API
    try {
      const response = await axios.get('/api/search_coords', { params: finalReqParams });
      const payload = response.data;
      const nRows = Array.isArray(payload?.data) ? payload.data.length : 0;
      if (nRows === 0) {
        setWarningMessage('No results were found for the given search criteria.');
      } else {
        setResults(payload);
      }
    } catch (error) {
      const errorDetail = error.response?.data?.detail || error.message || 'Unknown search error.';
      setWarningMessage(`Search failed: ${errorDetail}`);
    } finally {
      setIsSubmitting(false);
      setLastChangedType(null);
    }
  };

  return (
    <div className="row">
      <div className="col-lg-7 col-md-8">
        <form ref={formRef} onSubmit={handleSubmit} onKeyDownCapture={handleFormKeyDownCapture}>
          {warningMessage && (
            <div className="alert alert-warning" role="alert">{warningMessage}</div>
          )}

          {/* Cone Search */}
          <div className="card mb-3">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span>Cone Search</span>
              <div className="form-check form-switch m-0">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="useConeSearchSwitch"
                  checked={useConeSearch}
                  onChange={(e) => setUseConeSearch(e.target.checked)}
                  disabled={isSubmitting}
                />
                <label className="form-check-label" htmlFor="useConeSearchSwitch">Use</label>
              </div>
            </div>
            <div className="card-body">

              {/* Object Resolve + Suggestions */}
              <div className="mb-3">
                <label htmlFor="objectNameInput" className="form-label">Source Name</label>
                <div className="position-relative">
                  <input
                    ref={objectNameInputRef}
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
                  <button
                    type="button"
                    className="btn btn-ctao-galaxy"
                    disabled={!objectName || isSubmitting}
                    onClick={(e) => handleResolve(e)}
                  >
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
                <label className="form-label me-2"><strong>Coordinate system:</strong></label>
                <div className="btn-group" role="group" aria-label="Coordinate system">
                  {[
                    { value: COORD_SYS_EQ_DEG, label: <>Equatorial (deg) <span className="badge bg-secondary ms-1">J2000</span></> },
                    { value: COORD_SYS_EQ_HMS, label: <>Equatorial (hms/dms) <span className="badge bg-secondary ms-1">J2000</span></> },
                    { value: COORD_SYS_GAL,    label: 'Galactic (l/b deg)' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`btn btn-sm ${
                        coordinateSystem === opt.value ? 'btn-primary' : 'btn-outline-primary'
                      }`}
                      onClick={() => switchCoordinateSystem(opt.value)}
                      disabled={isSubmitting}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
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
          <div className="card mb-3" data-enter-scope="time">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span>Time Search</span>
              <div className="form-check form-switch m-0">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="useTimeSearchSwitch"
                  checked={useTimeSearch}
                  onChange={(e) => setUseTimeSearch(e.target.checked)}
                  disabled={isSubmitting}
                />
                <label className="form-check-label" htmlFor="useTimeSearchSwitch">Use</label>
              </div>
            </div>
          <div className="card-body">

        {/* Time system selector (Bootstrap button group) */}
        <div className="d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center">
            <label className="form-label me-2 mb-0"><strong>Time System:</strong></label>
            <div className="btn-group" role="group" aria-label="Time system">
              {['tt','utc'].map((opt) => (
                <button
                  key={opt}
                  type="button"
                  className={`btn btn-sm ${timeScale === opt ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => handleTimeScaleChange({ target: { value: opt } })}
                  disabled={isSubmitting}
                >
                  {opt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* epoch note under the section header */}
        <p className="text-muted small mb-2">
          Epoch for MET seconds: 2001-01-01 00:00:00 TT
        </p>

        {/* Start */}
        <label className="form-label fw-semibold">Observation Start</label>
        <div className="row g-2 align-items-end form-row-tight mb-2">
          {/* Date */}
          <div className="col-6 col-md-2">
            <div className="compact-date">
              <DatePicker
                selected={obsStartDateObj}
                onChange={handleStartDateChange}
                onCalendarOpen={() => setStartCalOpen(true)}
                onCalendarClose={() => setStartCalOpen(false)}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "startDate")}
                dateFormat="yyyy-MM-dd"
                placeholderText="YYYY-MM-DD"
                className="form-control form-control-sm"
                wrapperClassName="w-100"
                disabled={isSubmitting}
                showMonthDropdown
                showYearDropdown
                dropdownMode="select"
                popperPlacement="bottom-start"
                popperProps={{
                  strategy: 'fixed',
                  middleware: [
                    offset(8),
                    flip({ fallbackPlacements: ['bottom-end', 'top-start', 'top-end'] }),
                    shift({ padding: 8 }),
                  ],
                }}
              />
            </div>
          </div>

          {/* Time */}
          <div className="col-6 col-md-3">
            <input
              ref={startTimeRef}
              type="time"
              step="1"
              className="form-control form-control-sm input-monospace"
              value={obsStartTime}
              onChange={(e) => {
                setTimeMode('calendar');
                const v = e.target.value;
                const [hh='00', mm='00', ss='00'] = v.split(':');
                const norm = `${hh.padStart(2,'0')}:${mm.padStart(2,'0')}:${ss.padStart(2,'0')}`;
                setObsStartTime(norm);
                setTimeTouched(true);
                setLastChangedType('start_dt');
              }}
              onFocus={() => setIsEditingStartTime(true)}
              onBlur={() => { setIsEditingStartTime(false); setLastChangedType('start_dt'); }}
              aria-label="Start time"
              disabled={isSubmitting}
              onKeyDown={(e) => handleEnterSearchFromTimeField(e, "startTime")}
            />
          </div>

          {/* MJD */}
          <div className="col-12 col-md-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text">MJD</span>
              <input
                type="text"
                inputMode="decimal"
                className="form-control input-monospace"
                placeholder="Start"
                aria-label="Start MJD"
                value={obsStartMJD}
                onChange={handleStartMjdChange}
                disabled={isSubmitting}
                title={obsStartMJD}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "startMjd")}
              />
            </div>
          </div>

          {/* MET */}
          <div className="col-12 col-md-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text">MET</span>
              <input
                type="number"
                className="form-control input-monospace"
                placeholder="Start"
                value={metStartSeconds}
                onChange={handleMetStartChange}
                disabled={isSubmitting}
                title={String(metStartSeconds || '')}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "startMet")}
              />
            </div>
          </div>
        </div>

        {/* End */}
        <label className="form-label fw-semibold">Observation End</label>
        <div className="row g-2 align-items-end form-row-tight mb-2">
          {/* Date */}
          <div className="col-6 col-md-2">
            <div className="compact-date">
              <DatePicker
                selected={obsEndDateObj}
                onChange={handleEndDateChange}
                onCalendarOpen={() => setEndCalOpen(true)}
                onCalendarClose={() => setEndCalOpen(false)}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "endDate")}
                dateFormat="yyyy-MM-dd"
                placeholderText="YYYY-MM-DD"
                className="form-control form-control-sm"
                wrapperClassName="w-100"
                disabled={isSubmitting}
                showMonthDropdown
                showYearDropdown
                dropdownMode="select"
                popperPlacement="bottom-start"
                popperProps={{
                  strategy: 'fixed',
                  middleware: [
                    offset(8),
                    flip({ fallbackPlacements: ['bottom-end', 'top-start', 'top-end'] }),
                    shift({ padding: 8 }),
                  ],
                }}
              />
            </div>
          </div>

          {/* Time */}
          <div className="col-6 col-md-3">
            <input
              ref={endTimeRef}
              type="time"
              step="1"
              className="form-control form-control-sm input-monospace"
              value={obsEndTime}
              onChange={(e) => {
                setTimeMode('calendar');
                const v = e.target.value;
                const [hh='00', mm='00', ss='00'] = v.split(':');
                const norm = `${hh.padStart(2,'0')}:${mm.padStart(2,'0')}:${ss.padStart(2,'0')}`;
                setObsEndTime(norm);
                setTimeTouched(true);
                setLastChangedType('end_dt');
              }}
              onFocus={() => setIsEditingEndTime(true)}
              onBlur={() => { setIsEditingEndTime(false); setLastChangedType('end_dt'); }}
              aria-label="End time"
              disabled={isSubmitting}
              onKeyDown={(e) => handleEnterSearchFromTimeField(e, "endTime")}
            />
          </div>

          {/* MJD */}
          <div className="col-12 col-md-4">
            <div className="input-group input-group-sm">
              <span className="input-group-text">MJD</span>
              <input
                type="text"
                inputMode="decimal"
                className="form-control input-monospace"
                placeholder="End"
                aria-label="End MJD"
                value={obsEndMJD}
                onChange={handleEndMjdChange}
                disabled={isSubmitting}
                title={obsEndMJD}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "endMjd")}
              />
            </div>
          </div>

          {/* MET */}
          <div className="col-12 col-md-3">
            <div className="input-group input-group-sm">
              <span className="input-group-text">MET</span>
              <input
                type="number"
                className="form-control input-monospace"
                placeholder="End"
                value={metEndSeconds}
                onChange={handleMetEndChange}
                disabled={isSubmitting}
                title={String(metEndSeconds || '')}
                onKeyDown={(e) => handleEnterSearchFromTimeField(e, "endMet")}
              />
            </div>
          </div>
        </div>

          </div>
        </div>

        {/* Optional criteria accordion */}
        <div className="accordion mb-3" id="optionalCriteriaAccordion">

          {/* Energy Search */}
          <div className="accordion-item">
            <h2 className="accordion-header" id="headingEnergy">
              <button className="accordion-button collapsed" type="button"
                      data-bs-toggle="collapse" data-bs-target="#collapseEnergy"
                      aria-expanded="false" aria-controls="collapseEnergy">
                Energy Search
                {energyUsed && <span className="badge bg-success ms-2">Active</span>}
                {!energyUsed && energyHasAny && <span className="badge bg-secondary ms-2">Filled</span>}
              </button>
            </h2>
            <div id="collapseEnergy" className="accordion-collapse collapse"
                 aria-labelledby="headingEnergy" >
              <div className="accordion-body">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="useEnergySwitch"
                         checked={useEnergySearch} onChange={() => setUseEnergySearch(v => !v)} />
                  <label className="form-check-label" htmlFor="useEnergySwitch">Use Energy Search</label>
                </div>

                <div className="row g-2">
                  <div className="col-md-6">
                    <label className="form-label">Energy min</label>
                    <input type="number" className="form-control"
                           value={energyMin} onChange={(e) => setEnergyMin(e.target.value)}
                           disabled={isSubmitting} />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Energy max</label>
                    <input type="number" className="form-control"
                           value={energyMax} onChange={(e) => setEnergyMax(e.target.value)}
                           disabled={isSubmitting} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Observation Configuration */}
          <div className="accordion-item">
            <h2 className="accordion-header" id="headingObsConfig">
              <button className="accordion-button collapsed" type="button"
                      data-bs-toggle="collapse" data-bs-target="#collapseObsConfig"
                      aria-expanded="false" aria-controls="collapseObsConfig">
                Observation Configuration
                {obsConfigActive && <span className="badge bg-success ms-2">Active</span>}
              </button>
            </h2>
            <div id="collapseObsConfig" className="accordion-collapse collapse"
                 aria-labelledby="headingObsConfig" >
              <div className="accordion-body">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="useObsConfigSwitch"
                         checked={useObsConfig} onChange={() => setUseObsConfig(v => !v)} />
                  <label className="form-check-label" htmlFor="useObsConfigSwitch">Use Observation Configuration</label>
                </div>

                <div className="row g-2">
                  <div className="col-md-4">
                    <label className="form-label">Telescope Tracking Mode</label>
                    <select
                      className="form-select"
                      value={trackingMode}
                      onChange={(e) => { setTrackingMode(e.target.value); setUseObsConfig(true); }}
                      disabled={isSubmitting}
                    >
                      <option value="">(Any)</option>
                      <option value="sidereal">Sidereal</option>
                    </select>
                  </div>

                  <div className="col-md-4">
                    <label className="form-label">Array Pointing Mode</label>
                    <select
                      className="form-select"
                      value={pointingMode}
                      onChange={(e) => { setPointingMode(e.target.value); setUseObsConfig(true); }}
                      disabled={isSubmitting}
                    >
                      <option value="">(Any)</option>
                      <option value="parallel">Parallel</option>
                    </select>
                  </div>

                  <div className="col-md-4">
                    <label className="form-label">Observation Mode</label>
                    <select
                      className="form-select"
                      value={obsMode}
                      onChange={(e) => { setObsMode(e.target.value); setUseObsConfig(true); }}
                      disabled={isSubmitting}
                    >
                      <option value="">(Any)</option>
                      <option value="default">Default</option>
                      <option value="Wobble">Wobble</option>
                      <option value="On/Off">On/Off</option>
                      <option value="Grid-Scan Mode">Grid-Scan Mode</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Observation Program */}
          <div className="accordion-item">
            <h2 className="accordion-header" id="headingObsProgram">
              <button className="accordion-button collapsed" type="button"
                      data-bs-toggle="collapse" data-bs-target="#collapseObsProgram"
                      aria-expanded="false" aria-controls="collapseObsProgram">
                Observation Program
                {obsProgramActive && <span className="badge bg-success ms-2">Active</span>}
              </button>
            </h2>
            <div id="collapseObsProgram" className="accordion-collapse collapse"
                 aria-labelledby="headingObsProgram" >
              <div className="accordion-body">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="useObsProgramSwitch"
                         checked={useObsProgram} onChange={() => setUseObsProgram(v => !v)} />
                  <label className="form-check-label" htmlFor="useObsProgramSwitch">Use Observation Program</label>
                </div>

                <div className="row g-2">
                  <div className="col-md-6">
                    <label className="form-label">Proposal ID</label>
                    <input type="text" className="form-control"
                           value={proposalId} onChange={(e) => { setProposalId(e.target.value); setUseObsProgram(true); }}
                           disabled={isSubmitting} />
                  </div>

                  <div className="col-md-6">
                    <label className="form-label">Proposal type</label>
                    <select className="form-select"
                            value={proposalType} onChange={(e) => { setProposalType(e.target.value); setUseObsProgram(true); }}
                            disabled={isSubmitting}>
                      <option value="">(Any)</option>
                      <option value="ToO">ToO</option>
                    </select>
                  </div>

                  <div className="col-md-6">
                    <label className="form-label">Proposal title</label>
                    <input type="text" className="form-control"
                           value={proposalTitle} onChange={(e) => { setProposalTitle(e.target.value); setUseObsProgram(true); }}
                           disabled={isSubmitting} />
                  </div>

                  <div className="col-md-6">
                    <label className="form-label">Proposal contact person</label>
                    <input type="text" className="form-control"
                           value={proposalContact} onChange={(e) => { setProposalContact(e.target.value); setUseObsProgram(true); }}
                           disabled={isSubmitting} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Observation Conditions */}
          <div className="accordion-item">
            <h2 className="accordion-header" id="headingObsConditions">
              <button className="accordion-button collapsed" type="button"
                      data-bs-toggle="collapse" data-bs-target="#collapseObsConditions"
                      aria-expanded="false" aria-controls="collapseObsConditions">
                Observation Conditions
                {obsConditionsActive && <span className="badge bg-success ms-2">Active</span>}
              </button>
            </h2>
            <div id="collapseObsConditions" className="accordion-collapse collapse"
                 aria-labelledby="headingObsConditions" >
              <div className="accordion-body">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="useObsConditionsSwitch"
                         checked={useObsConditions} onChange={() => setUseObsConditions(v => !v)} />
                  <label className="form-check-label" htmlFor="useObsConditionsSwitch">Use Observation Conditions</label>
                </div>

                <div className="row g-2">
                  <div className="col-md-6">
                    <label className="form-label">Moon level</label>
                    <select className="form-select"
                            value={moonLevel} onChange={(e) => { setMoonLevel(e.target.value); setUseObsConditions(true); }}
                            disabled={isSubmitting}>
                      <option value="None">None</option>
                      <option value="Dark">Dark</option>
                      <option value="Moderate">Moderate</option>
                    </select>
                  </div>

                  <div className="col-md-6">
                    <label className="form-label">Sky brightness</label>
                    <select className="form-select"
                            value={skyBrightness} onChange={(e) => { setSkyBrightness(e.target.value); setUseObsConditions(true); }}
                            disabled={isSubmitting}>
                      <option value="None">None</option>
                      <option value="Dark">Dark</option>
                      <option value="Moderate">Moderate</option>
                    </select>
                  </div>
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
            <button
              type="button"
              className="btn btn-ctao-galaxy me-2"
              onClick={handleClearForm}
              disabled={isSubmitting}
            >
              Clear Form
            </button>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                  Searching...
                </>
              ) : (
                "Search"
              )}
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
