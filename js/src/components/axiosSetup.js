import axios from "axios";
import { toast } from "react-toastify";

// Always send cookies on cross-site requests
axios.defaults.withCredentials = true;

// Intercept all responses
axios.interceptors.response.use(
  (response) => response,

  (error) => {
    const { response, config } = error;

    if (config?.skipAuthErrorHandling) {
      return Promise.reject(error);
    }

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
