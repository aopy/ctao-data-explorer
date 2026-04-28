// Detect local dev
export const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

// Auth service base
export const AUTH_PREFIX = isLocal ? "http://localhost:8001/auth" : "/auth";

// API direct (public)
export const API_PREFIX = isLocal ? "http://localhost:8000/api" : "/api";

// API through auth relay ("dataaccess" service)
export const DATAACCESS_PREFIX = `${AUTH_PREFIX}/dataaccess/api`;
