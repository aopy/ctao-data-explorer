import { apiClient } from "../apiClients";

export async function submitQuickLook(p) {
  const { data } = await apiClient.post(`/opus/jobs`, p);
  // => { job_id, location }
  return data;
}

export async function listJobs() {
  const { data } = await apiClient.get(`/opus/jobs`);
  return data;
}

export async function jobDetails(jobId) {
  const { data } = await apiClient.get(`/opus/jobs/${encodeURIComponent(jobId)}`);
  return data;
}

export async function jobResults(jobId) {
  const { data } = await apiClient.get(`/opus/jobs/${encodeURIComponent(jobId)}/results`);
  return data;
}

export async function getOpusConfig() {
  const { data } = await apiClient.get(`/opus/_debug_base`);
  // -> { OPUS_ROOT, OPUS_SERVICE }
  return data;
}
