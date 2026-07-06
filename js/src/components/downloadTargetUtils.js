import { publicApiClient } from "../apiClients";

function normalizeDatalinkPath(url) {
  if (!url) return url;

  try {
    const u = new URL(url, window.location.origin);
    const p = u.pathname.startsWith("/api/") ? u.pathname.slice(4) : u.pathname;
    return p + (u.search || "");
  } catch {
    return url.startsWith("/api/") ? url.slice(4) : url;
  }
}

function looksLikeDatalinkUrl(value) {
  if (!value) return false;
  const s = String(value).toLowerCase();
  return s.includes("/datalink/") || s.includes("dlmeta");
}

export function getDatalinkUrl(row) {
  if (row.datalink_url) return row.datalink_url;
  if (row.datalink) return row.datalink;
  if (looksLikeDatalinkUrl(row.access_url)) return row.access_url;
  return null;
}

function looksLikeLfn(value) {
  return typeof value === "string" && value.trim().startsWith("lfn:/");
}

export function getDirectDownloadUrl(row) {
  /*
   * Prefer the ObsCore LFN when available.
   *
   * For the SDC table, access_url may point to DataLink metadata while the
   * actual storage-independent file reference is in the lfn column.
   * The download service resolves lfn:/... through its configured prefix map.
   */
  if (looksLikeLfn(row.lfn)) return row.lfn.trim();

  return (
    row.storage_url ||
    row.surl ||
    row.download_url ||
    row.access_url_this ||
    null
  );
}

function getFieldNames(xmlDoc) {
  return Array.from(xmlDoc.getElementsByTagName("FIELD")).map(
    field => field.getAttribute("name") || field.getAttribute("ID") || ""
  );
}

function rowObjectFromTr(tr, fieldNames) {
  const tdElements = Array.from(tr.getElementsByTagName("TD"));
  const row = {};

  fieldNames.forEach((name, index) => {
    if (name) {
      row[name] = tdElements[index]?.textContent?.trim() || "";
    }
  });

  return row;
}

function scoreDatalinkRow(row) {
  const semantics = String(row.semantics || "").toLowerCase();
  const contentType = String(row.content_type || "").toLowerCase();
  const description = String(row.description || "").toLowerCase();

  if (!row.access_url || row.error_message) return -1;

  // prefer main science data / package-like files
  if (semantics === "#this") return 100;
  if (semantics === "#package") return 90;

  // FITS-like data is a better download candidate than preview PNGs
  if (contentType.includes("fits")) return 80;

  // avoid selecting preview images as the primary download
  if (semantics.includes("preview") || contentType.startsWith("image/png")) return 20;

  // fallback for minimal app-generated DataLink responses with only access_url
  if (description.includes("download")) return 60;

  return 50;
}

export async function resolveDownloadUrlFromDatalink(datalinkUrl) {
  const normalizedUrl = normalizeDatalinkPath(datalinkUrl);
  const res = await publicApiClient.get(normalizedUrl, { responseType: "text" });

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(res.data, "application/xml");

  const fieldNames = getFieldNames(xmlDoc);
  const tabledata = xmlDoc.getElementsByTagName("TABLEDATA")[0];

  if (!tabledata) {
    throw new Error("No DataLink TABLEDATA found.");
  }

  const rows = Array.from(tabledata.getElementsByTagName("TR")).map(tr =>
    rowObjectFromTr(tr, fieldNames)
  );

  const candidates = rows
    .map(row => ({ row, score: scoreDatalinkRow(row) }))
    .filter(item => item.score >= 0)
    .sort((a, b) => b.score - a.score);

  if (!candidates.length) {
    throw new Error("No downloadable DataLink access_url found.");
  }

  return candidates[0].row.access_url;
}

export async function resolveDownloadUrlForRow(row) {
  const directUrl = getDirectDownloadUrl(row);
  if (directUrl) {
    return directUrl;
  }

  const datalinkUrl = getDatalinkUrl(row);
  if (datalinkUrl) {
    return resolveDownloadUrlFromDatalink(datalinkUrl);
  }

  throw new Error("No LFN, download URL, or DataLink URL found for this row.");
}
