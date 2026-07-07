import axios from 'axios';
import { AUTH_PREFIX } from '../config';

function filenameFromUrl(url) {
  try {
    const parsed = new URL(url);
    const last = parsed.pathname.split('/').filter(Boolean).pop();
    return last || 'download';
  } catch {
    const last = String(url || '').split('/').filter(Boolean).pop();
    return last || 'download';
  }
}

function filenameFromContentDisposition(headerValue) {
  if (!headerValue) return null;

  const match = headerValue.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  if (!match) return null;

  try {
    return decodeURIComponent(match[1].replace(/^"|"$/g, '').trim());
  } catch {
    return match[1].replace(/^"|"$/g, '').trim();
  }
}

function triggerBlobDownload(blob, filename) {
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = objectUrl;
  link.download = filename || 'download';
  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(objectUrl);
}

export async function requestDownloadDescriptor(fileRef) {
  const response = await axios.post(
    `${AUTH_PREFIX}/download/signed-urls`,
    {
      files: [fileRef],
      validity: 'PT1H',
    },
    {
      withCredentials: true,
    }
  );

  const descriptors = response.data?.signed_urls || [];
  if (!descriptors.length) {
    const firstError = response.data?.errors?.[0];
    throw new Error(firstError?.message || 'No downloadable file was returned.');
  }

  return descriptors[0];
}

export async function downloadWithBearerDescriptor(descriptor) {
  const storageUrl = descriptor.storage_url;
  const accessToken = descriptor.access_token;

  if (!storageUrl || !accessToken) {
    throw new Error('Download descriptor is missing storage_url or access_token.');
  }

  const response = await axios.get(storageUrl, {
    responseType: 'blob',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const contentDisposition = response.headers?.['content-disposition'];
  const filename =
    filenameFromContentDisposition(contentDisposition) ||
    filenameFromUrl(storageUrl) ||
    filenameFromUrl(descriptor.original);

  triggerBlobDownload(response.data, filename);
}

export async function prepareAndDownloadFile(fileRef) {
  const descriptor = await requestDownloadDescriptor(fileRef);
  await downloadWithBearerDescriptor(descriptor);
  return descriptor;
}
