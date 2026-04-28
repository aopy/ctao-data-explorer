import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter as Router } from "react-router-dom";
import "@fontsource/inter/400.css";
import "@fontsource/inter/700.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js";
import "bootstrap-icons/font/bootstrap-icons.css";
import "./index.css";
import "./ctao-theme.css";
import App from "./App";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import reportWebVitals from "./reportWebVitals";
import axios from "axios";

// Detect local dev
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

// future: if we mount the app under a subpath
// e.g. REACT_APP_BASENAME=/apps/data-explorer (https://ctao.org/apps/data-explorer/)
// js/.env: REACT_APP_BASENAME=/apps/data-explorer
const BASENAME = process.env.REACT_APP_BASENAME || "/";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Router basename={BASENAME}>
      <App />
    </Router>
    <ToastContainer position="top-center" newestOnTop draggable={false} />
  </React.StrictMode>
);

reportWebVitals();
