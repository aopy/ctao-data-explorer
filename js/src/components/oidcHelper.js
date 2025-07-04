export function launchOidcLogin({ API_PREFIX, searchFormRef, results, coords, ids }) {
  // save UI state
  try {
    searchFormRef?.current?.saveState?.();
    if (results) sessionStorage.setItem("SavedResults", JSON.stringify(results));
    if (coords)  sessionStorage.setItem("SavedCoords",  JSON.stringify(coords));
    if (ids)     sessionStorage.setItem("SavedIds",     JSON.stringify(ids));
  } catch (e) {
    console.warn("Could not cache UI state:", e);
  }
  window.location.href = `${API_PREFIX}/oidc/login?ts=${Date.now()}`;
}
