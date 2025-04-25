import { format, parse, isValid } from 'date-fns';

// Converts MJD to UTC Date object
export function mjdToDate(mjd) {
  if (mjd === null || mjd === undefined || isNaN(mjd)) {
    return null;
  }
  try {
    const jd = parseFloat(mjd) + 2400000.5;
    // Formula to convert Julian Date to timestamp
    const unixEpochJD = 2440587.5; // JD for 1970-01-01T00:00:00Z
    const msPerDay = 86400000;
    const timestamp = (jd - unixEpochJD) * msPerDay;
    return new Date(timestamp);
  } catch (e) {
    console.error("Error converting MJD to Date:", e);
    return null;
  }
}

// Converts a Date object (UTC) to MJD
 export function dateToMjd(date) {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return null;
  }
  try {
    const unixEpochJD = 2440587.5;
    const msPerDay = 86400000;
    const timestamp = date.getTime();
    const jd = (timestamp / msPerDay) + unixEpochJD;
    const mjd = jd - 2400000.5;
    return parseFloat(mjd.toFixed(8));
  } catch (e) {
    console.error("Error converting Date to MJD:", e);
    return null;
  }
}


// Parses "dd/MM/yyyy" and "HH:mm:ss" into a Date object using date-fns
// returns null if format is invalid, assumes input is UTC intent
export function parseDateTimeStrings(dateStr, timeStr) {
  if (!dateStr || !timeStr) return null;
  const dateTimeString = `${dateStr} ${timeStr}`;
  // 'dd/MM/yyyy HH:mm:ss' is the format string for date-fns parse

  const dateRegex = /^(\d{2})\/(\d{2})\/(\d{4})$/;
  const timeRegex = /^(\d{2}):(\d{2}):(\d{2})$/;

  const dateMatch = dateStr.match(dateRegex);
  const timeMatch = timeStr.match(timeRegex);

  if (!dateMatch || !timeMatch) return null;

  const day = parseInt(dateMatch[1], 10);
  const month = parseInt(dateMatch[2], 10) - 1; // JS months are 0-indexed
  const year = parseInt(dateMatch[3], 10);
  const hours = parseInt(timeMatch[1], 10);
  const minutes = parseInt(timeMatch[2], 10);
  const seconds = parseInt(timeMatch[3], 10);

  // Basic validation
  if (month < 0 || month > 11 || day < 1 || day > 31 || hours < 0 || hours > 23 || minutes < 0 || minutes > 59 || seconds < 0 || seconds > 59) {
      return null;
  }
  // Create date object using UTC values to avoid timezone issues
  const date = new Date(Date.UTC(year, month, day, hours, minutes, seconds));

  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month || date.getUTCDate() !== day ||
      date.getUTCHours() !== hours || date.getUTCMinutes() !== minutes || date.getUTCSeconds() !== seconds) {
      return null; // Invalid date components (e.g., Feb 30)
  }
  return date;
}

// Formats a Date object into "dd/MM/yyyy" and "HH:mm:ss" UTC strings using date-fns
export function formatDateTimeStrings(date) {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return { dateStr: '', timeStr: '' };
  }
  try {
      // Ensure formatting uses UTC values
      const dateStr = format(date, 'dd/MM/yyyy', { timeZone: 'UTC' });
      const timeStr = format(date, 'HH:mm:ss', { timeZone: 'UTC' });
      return { dateStr, timeStr };
  } catch(e) {
      console.error("Error formatting date:", e);
      return { dateStr: '', timeStr: '' };
  }
}

// Constants used within parseCoords
export const COORD_SYS_EQ_DEG = 'equatorial_deg';
export const COORD_SYS_EQ_HMS = 'equatorial_hms';
export const COORD_SYS_GAL = 'galactic';
