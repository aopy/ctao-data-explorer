import { toast } from "react-toastify";

/**
 * mode:
 *  - "default": show session-expired toast on generic 401s
 *  - "public": do not show session-expired toast (public endpoints may be used by anon users)
 */
export function installAuthInterceptors(client, { mode = "default" } = {}) {
  if (!client || !client.interceptors?.response?.use) return;

  client.interceptors.response.use(
    (r) => r,
    (error) => {
      const { response, config } = error || {};

      if (config?.skipAuthErrorHandling) return Promise.reject(error);

      if (response?.status === 401) {
        const detail = response?.data?.detail;

        // Special relay signal: session exists but must reauth
        if (detail === "reauth_required") {
          window.dispatchEvent(new Event("reauth-required"));
          return Promise.reject(error);
        }

        // For public clients: don't show "session expired" toast
        if (mode === "public") return Promise.reject(error);

        const hadSession = localStorage.getItem("hadSession") === "true";
        const hasCookie = document.cookie.includes("ctao_session_main=");

        if (hadSession || hasCookie) {
          toast.dismiss("session-expired");
          toast.error(
            "Your session expired — please click the Login button to sign in again.",
            { toastId: "session-expired", autoClose: false }
          );
          localStorage.removeItem("hadSession");
          window.dispatchEvent(new Event("session-lost"));
        }
      }

      return Promise.reject(error);
    }
  );
}
