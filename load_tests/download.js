import http from 'k6/http';
import { check } from 'k6';

const bff = JSON.parse(open(__ENV.BFF_SESSION_FILE || '/shared/bff-session.json'));
const baseUrl = __ENV.FRONTEND_URL || 'https://ctao-data-explorer.test.example';
const recordCount = Number(__ENV.MOCK_TAP_RECORD_COUNT || 1000);
const tileCount = Math.max(1, Math.ceil(recordCount / 100));
const full = __ENV.K6_PROFILE === 'full';
const stages = full
  ? [{ duration: '2m', target: 1 }, { duration: '3m', target: 2 }, { duration: '5m', target: 3 }, { duration: '15m', target: 3 }, { duration: '5m', target: 0 }]
  : [{ duration: '1m', target: 5 }, { duration: '1m', target: 0 }];

export const options = {
  insecureSkipTLSVerify: true,
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  thresholds: {
    checks: ['rate==1'],
    http_req_failed: ['rate<0.01'],
    'http_req_failed{name:catalog_search}': ['rate<0.01'],
    'http_req_duration{name:catalog_search}': ['p(95)<200', 'p(99)<500', 'max<2000'],
  },
  scenarios: {
    catalog: { executor: 'ramping-vus', exec: 'catalog', stages: full ? stages.map((s, i) => ({ ...s, target: [2, 5, 10, 10, 0][i] })) : stages },
    show_all: { executor: 'per-vu-iterations', exec: 'showAll', vus: 1, iterations: 1 },
    descriptor: { executor: 'ramping-vus', exec: 'descriptor', stages: full ? stages.map((s, i) => ({ ...s, target: [2, 5, 10, 10, 0][i] })) : stages },
    download: { executor: 'ramping-vus', exec: 'download', stages: full ? stages.map((s, i) => ({ ...s, target: [6, 15, 30, 30, 0][i] })) : stages },
  },
};

const headers = {
  Cookie: `ctao_session_main=${bff.session}; XSRF-TOKEN=${bff.xsrf}`,
  'X-XSRF-TOKEN': bff.xsrf,
  'Content-Type': 'application/json',
};

function fileRef() {
  return `https://localhost:9999/objects/${5000000001 + ((__VU * 1000 + __ITER) % Number(__ENV.MOCK_TAP_RECORD_COUNT || 1000))}`;
}

export function setup() {
  const response = http.get(`${baseUrl}/auth/me`, { headers, tags: { name: 'auth_me' } });
  check(response, { 'BFF session is authenticated': (r) => r.status === 200 });
}

export function catalog() {
  const tile = (__VU * 1000 + __ITER) % tileCount;
  const ra = tile === 0 ? 83.63 : (tile % 25) * 14 + 7;
  const dec = tile === 0 ? 22.01 : -70 + Math.floor(tile / 25) * 7;
  const response = http.get(`${baseUrl}/api/search_coords?coordinate_system=equatorial_deg&ra=${ra}&dec=${dec}&search_radius=3`, { responseType: 'text', tags: { name: 'catalog_search' } });
  check(response, { 'catalog result is valid': (r) => r.status === 200 && JSON.parse(r.body).data.length > 0 });
}

export function showAll() {
  const response = http.get(`${baseUrl}/api/search_coords?show_all=true`, { responseType: 'text', tags: { name: 'catalog_show_all' } });
  check(response, {
    'Show All returns the complete mock catalog': (r) => {
      if (r.status !== 200) return false;
      const payload = JSON.parse(r.body);
      return payload.data.length === recordCount && payload.total_rows === recordCount;
    },
  });
}

function requestDescriptor() {
  return http.post(`${baseUrl}/auth/download/signed-urls`, JSON.stringify({ files: [fileRef()], validity: 'PT1H' }), { headers, responseType: 'text', tags: { name: 'signed_descriptor' } });
}

export function descriptor() {
  const response = requestDescriptor();
  check(response, { 'BFF relays a signed descriptor': (r) => r.status === 200 && JSON.parse(r.body).signed_urls.length === 1 });
}

export function download() {
  const signed = requestDescriptor();
  const ok = check(signed, { 'descriptor is available for download': (r) => r.status === 200 });
  if (!ok) return;
  const entry = JSON.parse(signed.body).signed_urls[0];
  const objectId = Number(entry.storage_url.match(/objects\/(\d+)/)[1]);
  const expectedBlobSize = [1024, 8192, 65536][objectId % 3];
  const response = http.get(entry.storage_url, { headers: { Authorization: `Bearer ${entry.access_token}` }, tags: { name: 'storage_download' } });
  check(response, {
    'storage blob is downloaded': (r) => r.status === 200 && Number(r.headers['X-Mock-Blob-Size']) === expectedBlobSize,
  });
}
