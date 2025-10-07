import axios from "axios";
import { API_PREFIX } from "../index";

export async function submitQuickLook(p) {
  const { data } = await axios.post(`${API_PREFIX}/opus/jobs`, p);
  // => { job_id, location }
  return data;
}

export async function listJobs() {
  const { data } = await axios.get(`${API_PREFIX}/opus/jobs`);
  return data;
}

export async function jobDetails(jobId) {
  const { data } = await axios.get(`${API_PREFIX}/opus/jobs/${encodeURIComponent(jobId)}`);
  return data;
}

export async function jobResults(jobId) {
  const { data } = await axios.get(`${API_PREFIX}/opus/jobs/${encodeURIComponent(jobId)}/results`);
  return data;
}

export async function getOpusConfig() {
  const { data } = await axios.get(`${API_PREFIX}/opus/_debug_base`);
  // -> { OPUS_ROOT, OPUS_SERVICE }
  return data;
}
