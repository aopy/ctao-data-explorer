import { apiClient } from "../apiClients";

export async function saveQueryHistoryIfLoggedIn({ isLoggedIn, queryParams, results }) {
  if (!isLoggedIn) return;
  try {
    await apiClient.post("/query-history", {
      query_params: queryParams,
      results,
    });
  } catch (e) {
    if (e?.response?.status === 401) return;
    throw e;
  }
}