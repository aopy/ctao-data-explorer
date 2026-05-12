import axios from "axios";
import { AUTH_PREFIX, DATAACCESS_PREFIX, API_PREFIX } from "./config";

function getCookie(name) {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1];
}

function attachXsrfHeader(config) {
  const method = (config.method || "get").toLowerCase();
  const mutating = ["post", "put", "patch", "delete"].includes(method);

  if (mutating) {
    const xsrf = getCookie("XSRF-TOKEN");
    if (xsrf) {
      config.headers = config.headers || {};
      config.headers["X-XSRF-TOKEN"] = decodeURIComponent(xsrf);
    }
  }

  return config;
}

export const authClient = axios.create({
  baseURL: AUTH_PREFIX,
  withCredentials: true,
  xsrfCookieName: "XSRF-TOKEN",
  xsrfHeaderName: "X-XSRF-TOKEN",
});

export const apiClient = axios.create({
  baseURL: DATAACCESS_PREFIX,
  withCredentials: true,
  xsrfCookieName: "XSRF-TOKEN",
  xsrfHeaderName: "X-XSRF-TOKEN",
});

export const publicApiClient = axios.create({
  baseURL: API_PREFIX,
  withCredentials: true,
  xsrfCookieName: "XSRF-TOKEN",
  xsrfHeaderName: "X-XSRF-TOKEN",
});

authClient.interceptors.request.use(attachXsrfHeader);
apiClient.interceptors.request.use(attachXsrfHeader);
publicApiClient.interceptors.request.use(attachXsrfHeader);
