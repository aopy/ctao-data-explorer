import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import OpusJobDetailPage from "./components/OpusJobDetailPage";
import 'bootstrap/dist/css/bootstrap.min.css'; // Import Bootstrap CSS
import 'bootstrap/dist/js/bootstrap.bundle.min.js'; // Bootstrap's JS components
import './index.css';
import App from './App';
import './components/axiosSetup';
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import reportWebVitals from './reportWebVitals';
import axios from 'axios';

export const API_PREFIX = '/api';
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);

axios.defaults.baseURL = isLocal
  ? 'http://localhost:8000'
  : '';

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

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
