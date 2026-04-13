import { formatInTimeZone } from 'date-fns-tz';

// Converts MJD to UTC Date object
export function mjdToDate(mjd) {
  if (mjd === null || mjd === undefined) return null;
  const mjdNum = parseFloat(mjd);

  if (isNaN(mjdNum)) {
    console.warn("mjdToDate: Input MJD is not a number:", mjd);
    return null;
  }
  const JS_MIN_MJD_APPROX = -678999; // approx 0000-01-01
  const JS_MAX_MJD_APPROX = 1507000; // approx 9999-12-31

  if (mjdNum < JS_MIN_MJD_APPROX || mjdNum > JS_MAX_MJD_APPROX) {
    console.warn("mjdToDate: MJD value is outside the representable range for JS Date:", mjdNum);
    return null;
  }

  try {
    const jd = mjdNum + 2400000.5;
    const unixEpochJD = 2440587.5;
    const msPerDay = 86400000;
    const timestamp = (jd - unixEpochJD) * msPerDay;

    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
        console.warn("mjdToDate: Resulting date is invalid for MJD:", mjdNum);
        return null;
    }
    return date;
  } catch (e) {
    console.error("Error converting MJD to Date:", e);
    return null;
  }
}

// Formats a Date object into "dd/MM/yyyy" and "HH:mm:ss" UTC strings using date-fns
export function formatDateTimeStrings(date) {
  if (!date || isNaN(date.getTime())) {
    return { dateStr: '', timeStr: '' };
  }
  return {
    dateStr: formatInTimeZone(date, 'UTC', 'dd/MM/yyyy'),
    timeStr: formatInTimeZone(date, 'UTC', 'HH:mm:ss'),
  };
}

// Function to convert decimal RA (degrees) to HMS string
export function degToHMS(deg) {
  if (isNaN(deg) || deg === null) return 'N/A';
  let ra = deg;
  if (ra < 0) ra += 360;
  ra /= 15;

  const h = Math.floor(ra);
  const m = Math.floor((ra - h) * 60);
  const s = (((ra - h) * 60 - m) * 60).toFixed(1);

  return `${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s}s`;
}

// Function to convert decimal Dec (degrees) to DMS string
export function degToDMS(deg) {
  if (isNaN(deg) || deg === null) return 'N/A';
  const sign = deg >= 0 ? '+' : '-';
  const absDeg = Math.abs(deg);

  const d = Math.floor(absDeg);
  const m = Math.floor((absDeg - d) * 60);
  const s = (((absDeg - d) * 60 - m) * 60).toFixed(0);

  return `${sign}${d.toString().padStart(2, '0')}° ${m.toString().padStart(2, '0')}' ${s}"`;
}

// Constants used within parseCoords
export const COORD_SYS_EQ_DEG = 'equatorial_deg';
export const COORD_SYS_EQ_HMS = 'equatorial_hms';
export const COORD_SYS_GAL = 'galactic';
