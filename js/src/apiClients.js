import axios from "axios";
import { AUTH_PREFIX, DATAACCESS_PREFIX, API_PREFIX } from "./config";

/**
 * Auth service client:
 * - cookies (session) only
 * - /auth/me, /auth/oidc/*, /auth/logout_session, etc.
 */
export const authClient = axios.create({
  baseURL: AUTH_PREFIX,
  withCredentials: true,
});

/**
 * Protected API client:
 * - goes through auth token relay (adds Bearer from session server-side)
 * - use for endpoints that require auth (basket, query-history, opus, etc.)
 */
export const apiClient = axios.create({
  baseURL: DATAACCESS_PREFIX,
  withCredentials: true,
});

/**
 * Public API client:
 * - goes directly to the API service
 * - use for endpoints that allow anonymous access (search, resolve, suggest, parse/convert, etc.)
 */
export const publicApiClient = axios.create({
  baseURL: API_PREFIX,
  withCredentials: true,
});
