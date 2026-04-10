import axios from "axios";
import { toast } from "react-toastify";

// Always send cookies (needed for session-cookie auth)
axios.defaults.withCredentials = true;

// detect the new relay "reauth required" response
function isReauthRequired(response) {
  if (!response) return false;
  // { detail: "reauth_required", reason: "no_access_token" }
  if (response.status === 401 && response.data?.detail === "reauth_required") {
    return true;
  }
  // fallback: detect via WWW-Authenticate header
  const www =
    response.headers?.["www-authenticate"] || response.headers?.["WWW-Authenticate"];
  if (
    response.status === 401 &&
    typeof www === "string" &&
    www.includes("reauth_required")
  ) {
    return true;
  }
  return false;
}

// Intercept all responses
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const response = error?.response;
    const config = error?.config;

    // Allow callers to opt out
    if (config?.skipAuthErrorHandling) {
      return Promise.reject(error);
    }

    // logged-in session exists but IAM token missing -> reauth-required
    if (isReauthRequired(response)) {
      toast.dismiss("reauth-required");

      toast.error(
        "Your IAM token expired — please click Login to sign in again.",
        { toastId: "reauth-required", autoClose: false }
      );

      localStorage.removeItem("hadSession");
      window.dispatchEvent(new Event("reauth-required"));
      return Promise.reject(error);
    }

    // Generic 401 handling
    if (response?.status === 401) {
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
