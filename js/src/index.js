import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import OpusJobDetailPage from "./components/OpusJobDetailPage";
import "@fontsource/inter/400.css";
import "@fontsource/inter/700.css";
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import './index.css';
import './ctao-theme.css';
import App from './App';
import './components/axiosSetup';
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import reportWebVitals from './reportWebVitals';
import axios from 'axios';

// Detect local dev
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);

// Data Explorer backend API (same origin as the frontend)
export const API_PREFIX = '/api';

// Auth service base:
//  in local dev: talk directly to auth_service on port 8001
//  in prod: use '/auth' so reverse proxy can route it
export const AUTH_PREFIX = isLocal
  ? 'http://localhost:8001/api'
  : '/auth';

// Axios base URL for *relative* API calls (Data Explorer backend)
axios.defaults.baseURL = isLocal
  ? 'http://localhost:8000'
  : '';

// Always send cookies
axios.defaults.withCredentials = true;

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Router>
      <Routes>
        <Route path="/opus/jobs/:jobId" element={<OpusJobDetailPage />} />
        <Route path="/*" element={<App />} />
      </Routes>
    </Router>
    <ToastContainer position="top-center" newestOnTop draggable={false} />
  </React.StrictMode>
);

reportWebVitals();
